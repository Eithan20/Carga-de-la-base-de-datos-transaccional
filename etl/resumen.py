"""Verificación final contra la base de datos y resumen del proceso."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List

from etl.database import Database
from etl.modelos import Rechazo, ResultadoEntidad

log = logging.getLogger(__name__)

# Consultas que deben devolver 0 si la integridad referencial se mantiene
_CONSULTAS_HUERFANOS = {
    "Encuestas sin cliente": (
        "SELECT COUNT(*) FROM dbo.Encuestas e "
        "LEFT JOIN dbo.Clientes c ON c.IdCliente = e.IdCliente WHERE c.IdCliente IS NULL"
    ),
    "Encuestas sin producto": (
        "SELECT COUNT(*) FROM dbo.Encuestas e "
        "LEFT JOIN dbo.Productos p ON p.IdProducto = e.IdProducto WHERE p.IdProducto IS NULL"
    ),
    "Encuestas sin fuente": (
        "SELECT COUNT(*) FROM dbo.Encuestas e "
        "LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = e.IdFuente WHERE f.IdFuente IS NULL"
    ),
    "Reseñas con cliente inexistente": (
        "SELECT COUNT(*) FROM dbo.ResenasWeb r "
        "LEFT JOIN dbo.Clientes c ON c.IdCliente = r.IdCliente "
        "WHERE r.IdCliente IS NOT NULL AND c.IdCliente IS NULL"
    ),
    "Reseñas sin producto": (
        "SELECT COUNT(*) FROM dbo.ResenasWeb r "
        "LEFT JOIN dbo.Productos p ON p.IdProducto = r.IdProducto WHERE p.IdProducto IS NULL"
    ),
    "Reseñas sin fuente": (
        "SELECT COUNT(*) FROM dbo.ResenasWeb r "
        "LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = r.IdFuente WHERE f.IdFuente IS NULL"
    ),
    "Comentarios con cliente inexistente": (
        "SELECT COUNT(*) FROM dbo.ComentariosSociales s "
        "LEFT JOIN dbo.Clientes c ON c.IdCliente = s.IdCliente "
        "WHERE s.IdCliente IS NOT NULL AND c.IdCliente IS NULL"
    ),
    "Comentarios sin producto": (
        "SELECT COUNT(*) FROM dbo.ComentariosSociales s "
        "LEFT JOIN dbo.Productos p ON p.IdProducto = s.IdProducto WHERE p.IdProducto IS NULL"
    ),
    "Comentarios sin fuente": (
        "SELECT COUNT(*) FROM dbo.ComentariosSociales s "
        "LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = s.IdFuente WHERE f.IdFuente IS NULL"
    ),
}


def verificar_base(db: Database, resultados: Dict[str, ResultadoEntidad]) -> dict:
    """Cuenta lo realmente guardado en la base y busca registros huérfanos."""
    en_base = {nombre: db.escalar(f"SELECT COUNT(*) FROM dbo.{nombre}") for nombre in resultados}
    diferencias = {
        n: (resultados[n].insertados, en_base[n])
        for n in resultados if resultados[n].insertados != en_base[n]
    }
    huerfanos = {nombre: db.escalar(sql) for nombre, sql in _CONSULTAS_HUERFANOS.items()}
    return {"en_base": en_base, "diferencias": diferencias, "huerfanos": huerfanos}


def imprimir_resumen(
    resultados: Dict[str, ResultadoEntidad], rechazos: List[Rechazo],
    verificacion: dict, inicio: datetime, fin: datetime,
) -> str:
    L = []
    L.append("")
    L.append("=" * 78)
    L.append("RESUMEN DEL PROCESO ETL")
    L.append("=" * 78)
    L.append(f"Inicio: {inicio:%Y-%m-%d %H:%M:%S}   Fin: {fin:%Y-%m-%d %H:%M:%S}   "
             f"Duración: {(fin - inicio).total_seconds():.1f} s")
    L.append("")
    cab = f"{'Entidad':<22}{'Procesados':>11}{'Staging':>10}{'Insertados':>12}{'Rechazados':>12}"
    L.append(cab)
    L.append("-" * len(cab))
    tot = [0, 0, 0, 0]
    for r in resultados.values():
        L.append(f"{r.entidad:<22}{r.leidos:>11}{r.en_staging:>10}{r.insertados:>12}{r.rechazados:>12}")
        for i, v in enumerate((r.leidos, r.en_staging, r.insertados, r.rechazados)):
            tot[i] += v
    L.append("-" * len(cab))
    L.append(f"{'TOTAL':<22}{tot[0]:>11}{tot[1]:>10}{tot[2]:>12}{tot[3]:>12}")

    L.append("")
    L.append("Motivos de rechazo:")
    hay = False
    for r in resultados.values():
        for motivo, cantidad in r.motivos.most_common():
            hay = True
            L.append(f"  [{r.entidad}] {motivo}: {cantidad}")
    if not hay:
        L.append("  (ninguno)")

    L.append("")
    L.append("Verificación en la base de datos:")
    cuadra = all(r.leidos == r.insertados + r.rechazados for r in resultados.values())
    L.append(f"  Procesados = insertados + rechazados en todas las entidades: {'SÍ' if cuadra else 'NO'}")
    if verificacion["diferencias"]:
        for n, (esperado, real) in verificacion["diferencias"].items():
            L.append(f"  ¡DIFERENCIA en {n}: se insertaron {esperado} pero la tabla tiene {real}!")
    else:
        L.append("  Los registros guardados en las 6 tablas coinciden con los insertados: SÍ")
    huerf = {k: v for k, v in verificacion["huerfanos"].items() if v}
    if huerf:
        for k, v in huerf.items():
            L.append(f"  ¡REGISTROS HUÉRFANOS! {k}: {v}")
    else:
        L.append(f"  Registros huérfanos (integridad referencial): 0 en {len(verificacion['huerfanos'])} comprobaciones")

    L.append("")
    ok = cuadra and not verificacion["diferencias"] and not huerf
    L.append("RESULTADO: " + ("CARGA COMPLETADA CORRECTAMENTE" if ok else "CARGA CON INCONSISTENCIAS, REVISAR"))
    if tot[3]:
        L.append(f"Hay {tot[3]} registros rechazados; el detalle está en la tabla stg.RegistrosRechazados.")
    L.append("=" * 78)
    texto = "\n".join(L)
    print(texto)
    for linea in L:
        log.debug(linea)
    return texto
