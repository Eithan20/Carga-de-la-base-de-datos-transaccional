"""CAPA 1 - Extracción: CSV -> tablas de staging (esquema stg).

Se lee cada archivo, se valida su estructura (encabezados y cantidad de
columnas) y se copia tal cual a staging. No se limpia ni se convierte nada
aquí: eso ocurre al pasar a la capa transaccional.
"""
from __future__ import annotations

import csv
import io
import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from etl.database import Database
from etl.modelos import EstructuraInvalidaError, Rechazo, ResultadoEntidad

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entidad:
    nombre: str                         # nombre lógico (coincide con la tabla)
    patron: str                         # archivo(s) CSV de origen
    tabla_staging: str
    columnas: Tuple[Tuple[str, str], ...]  # (encabezado del CSV, columna de staging)

    @property
    def columnas_staging(self) -> List[str]:
        return [c[1] for c in self.columnas]


# Orden de carga: primero los catálogos y luego las opiniones
ENTIDADES: Tuple[Entidad, ...] = (
    Entidad("Clientes", "clients.csv", "stg.Clientes", (
        ("IdCliente", "IdCliente"), ("Nombre", "Nombre"), ("Email", "Email"),
    )),
    Entidad("Productos", "products.csv", "stg.Productos", (
        ("IdProducto", "IdProducto"), ("Nombre", "Nombre"), ("Categoría", "Categoria"),
    )),
    Entidad("FuenteDatos", "fuente_datos.csv", "stg.FuenteDatos", (
        ("IdFuente", "IdFuente"), ("TipoFuente", "TipoFuente"), ("FechaCarga", "FechaCarga"),
    )),
    Entidad("Encuestas", "surveys*.csv", "stg.Encuestas", (
        ("IdOpinion", "IdOpinion"), ("IdCliente", "IdCliente"), ("IdProducto", "IdProducto"),
        ("Fecha", "Fecha"), ("Comentario", "Comentario"), ("Clasificación", "Clasificacion"),
        ("PuntajeSatisfacción", "PuntajeSatisfaccion"), ("Fuente", "Fuente"),
    )),
    Entidad("ResenasWeb", "web_reviews*.csv", "stg.ResenasWeb", (
        ("IdReview", "IdReview"), ("IdCliente", "IdCliente"), ("IdProducto", "IdProducto"),
        ("Fecha", "Fecha"), ("Comentario", "Comentario"), ("Rating", "Rating"),
    )),
    Entidad("ComentariosSociales", "social_comments*.csv", "stg.ComentariosSociales", (
        ("IdComment", "IdComment"), ("IdCliente", "IdCliente"), ("IdProducto", "IdProducto"),
        ("Fuente", "Fuente"), ("Fecha", "Fecha"), ("Comentario", "Comentario"),
    )),
)

TABLAS_STAGING = [e.tabla_staging for e in ENTIDADES] + ["stg.RegistrosRechazados"]


def _clave_encabezado(texto: str) -> str:
    """Compara encabezados sin importar tildes, mayúsculas ni espacios."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sin_tildes.strip().lower().replace(" ", "")


def _leer_texto(ruta: Path) -> str:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return ruta.read_text(encoding=codificacion)
        except UnicodeDecodeError:
            continue
    raise EstructuraInvalidaError(f"{ruta.name}: no se pudo leer (codificación desconocida)")


def _lector_csv(ruta: Path):
    contenido = _leer_texto(ruta)
    primera_linea = contenido.splitlines()[0] if contenido.strip() else ""
    delimitador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    return csv.reader(io.StringIO(contenido, newline=""), delimiter=delimitador)


def limpiar_staging(db: Database) -> None:
    """Vacía la capa 1 para que cada ejecución parta de cero."""
    for tabla in TABLAS_STAGING:
        db.ejecutar(f"DELETE FROM {tabla}")


def _extraer_archivo(
    db: Database, entidad: Entidad, ruta: Path,
    resultado: ResultadoEntidad, rechazos: List[Rechazo],
) -> None:
    lector = _lector_csv(ruta)

    encabezado = next((fila for fila in lector if any(c.strip() for c in fila)), None)
    if encabezado is None:
        raise EstructuraInvalidaError(f"{ruta.name}: el archivo está vacío")

    posiciones = {_clave_encabezado(h): i for i, h in enumerate(encabezado)}
    indices, faltantes = [], []
    for csv_col, _ in entidad.columnas:
        posicion = posiciones.get(_clave_encabezado(csv_col))
        if posicion is None:
            faltantes.append(csv_col)
        indices.append(posicion)
    if faltantes:
        raise EstructuraInvalidaError(
            f"{ruta.name}: faltan las columnas {faltantes}. "
            f"Encabezados encontrados: {[h.strip() for h in encabezado]}"
        )

    filas_ok = []
    for fila in lector:
        if not any(c.strip() for c in fila):
            continue  # línea en blanco
        resultado.leidos += 1
        if len(fila) != len(encabezado):
            motivo = "Número de columnas incorrecto"
            resultado.rechazar(motivo)
            rechazos.append(Rechazo(
                entidad.nombre, ruta.name, lector.line_num,
                fila[0].strip() if fila else "", motivo, " | ".join(fila)[:2000],
            ))
            continue
        valores = [fila[i] for i in indices]
        filas_ok.append(tuple(valores) + (ruta.name, lector.line_num))

    columnas = ", ".join(entidad.columnas_staging + ["ArchivoOrigen", "NumFila"])
    marcadores = ", ".join("?" for _ in range(len(entidad.columnas) + 2))
    db.ejecutar_muchos(
        f"INSERT INTO {entidad.tabla_staging} ({columnas}) VALUES ({marcadores})", filas_ok
    )
    resultado.en_staging += len(filas_ok)


def extraer_a_staging(
    db: Database, carpeta: Path,
    resultados: dict, rechazos: List[Rechazo],
) -> None:
    """Capa 1: lee todos los CSV y los copia a staging."""
    # Primero se comprueba que existan todos los archivos
    archivos = {}
    for entidad in ENTIDADES:
        encontrados = sorted(carpeta.glob(entidad.patron))
        if not encontrados:
            raise FileNotFoundError(
                f"No se encontró '{entidad.patron}' en la carpeta {carpeta}"
            )
        archivos[entidad.nombre] = encontrados

    limpiar_staging(db)

    for entidad in ENTIDADES:
        resultado = resultados[entidad.nombre]
        for ruta in archivos[entidad.nombre]:
            _extraer_archivo(db, entidad, ruta, resultado, rechazos)
        log.info(
            "[Capa 1] %-20s %4d leídos -> %4d en staging, %d rechazados",
            entidad.nombre, resultado.leidos, resultado.en_staging, resultado.rechazados,
        )
