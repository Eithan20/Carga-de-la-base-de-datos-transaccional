"""CAPA 2 - Transformación y carga: staging (stg) -> transaccional (dbo).

Para cada registro de staging se hace, en este orden:
  1. Validar formato, obligatorios, tipos y longitudes (validate.py).
  2. Detectar duplicados (por ID de origen y por contenido).
  3. Verificar integridad referencial: el cliente, el producto y la fuente
     deben existir ya en la base transaccional.
  4. Insertar. Lo que falla se anota con su motivo en la lista de rechazos.

Se cargan primero los catálogos (Clientes, Productos, FuenteDatos) y luego
las opiniones, para respetar las claves foráneas.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from etl import validate
from etl.database import Database
from etl.extract import ENTIDADES, Entidad
from etl.modelos import ErrorValidacion, Rechazo, ResultadoEntidad

log = logging.getLogger(__name__)

_POR_NOMBRE = {e.nombre: e for e in ENTIDADES}

# Tipo de FuenteDatos que corresponde a cada canal de opinión
_TIPO_FUENTE_CANAL = {
    "Encuestas": "CSV",
    "ResenasWeb": "Web",
    "ComentariosSociales": "Red Social",
}

TABLAS_TRANSACCIONALES_HIJAS_PRIMERO = [
    "dbo.ComentariosSociales", "dbo.ResenasWeb", "dbo.Encuestas",
    "dbo.FuenteDatos", "dbo.Productos", "dbo.Clientes",
]


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def reiniciar_transaccional(db: Database) -> None:
    """Vacía la capa 2 (hijas primero) para que cada ejecución parta de cero.

    Así el proceso se puede repetir sin duplicar datos.
    """
    for tabla in TABLAS_TRANSACCIONALES_HIJAS_PRIMERO:
        db.ejecutar(f"DELETE FROM {tabla}")
    if db.es_sqlserver:
        # Reinicia el contador de IDs para que cada carga empiece en 1.
        # Solo si la tabla ya generó algún ID: en una tabla nueva, RESEED 0
        # haría que el primer ID fuera 0.
        for tabla in ("dbo.Encuestas", "dbo.ResenasWeb", "dbo.ComentariosSociales"):
            db.ejecutar(
                "IF EXISTS (SELECT 1 FROM sys.identity_columns "
                f"WHERE object_id = OBJECT_ID('{tabla}') AND last_value IS NOT NULL) "
                f"DBCC CHECKIDENT ('{tabla}', RESEED, 0) WITH NO_INFOMSGS"
            )


def _filas_staging(db: Database, entidad: Entidad) -> List[Tuple[dict, str, int]]:
    columnas = entidad.columnas_staging
    sql = (
        f"SELECT {', '.join(columnas)}, ArchivoOrigen, NumFila "
        f"FROM {entidad.tabla_staging} ORDER BY IdStg"
    )
    filas = []
    for registro in db.consultar(sql):
        datos = {col: (registro[i] if registro[i] is not None else "") for i, col in enumerate(columnas)}
        filas.append((datos, registro[len(columnas)], registro[len(columnas) + 1]))
    return filas


def _rechazar(
    entidad: Entidad, resultado: ResultadoEntidad, rechazos: List[Rechazo],
    datos: dict, archivo: str, fila: int, motivo: str,
) -> None:
    resultado.rechazar(motivo)
    primera = entidad.columnas_staging[0]
    rechazos.append(Rechazo(
        entidad.nombre, archivo, fila, str(datos.get(primera, "")), motivo,
        " | ".join(str(v) for v in datos.values())[:2000],
    ))


def guardar_rechazos(db: Database, rechazos: List[Rechazo]) -> None:
    db.ejecutar_muchos(
        "INSERT INTO stg.RegistrosRechazados "
        "(Entidad, ArchivoOrigen, NumFila, IdOrigen, Motivo, DatoOriginal) VALUES (?, ?, ?, ?, ?, ?)",
        [(r.entidad, r.archivo, r.fila, r.id_origen, r.motivo, r.dato_original) for r in rechazos],
    )


# ----------------------------------------------------------------------
# Catálogos
# ----------------------------------------------------------------------
def _cargar_catalogo(
    db: Database, entidad: Entidad, resultado: ResultadoEntidad, rechazos: List[Rechazo],
    validar: Callable[[dict], dict], clave_unica: Callable[[dict], Tuple],
    texto_duplicado: Tuple[Tuple[str, Callable[[dict], object]], ...],
    tabla: str, columnas_insert: str, valores: Callable[[dict], tuple],
    id_fijo: bool,
) -> dict:
    """Carga un catálogo. Devuelve {id: registro} de los que se insertaron."""
    vistos: Dict[str, set] = {nombre: set() for nombre, _ in texto_duplicado}
    aceptados: dict = {}
    filas_insert = []

    for datos, archivo, num_fila in _filas_staging(db, entidad):
        try:
            limpio = validar(datos)
            # duplicados (ID o campo único repetido)
            for nombre, extraer in texto_duplicado:
                valor = extraer(limpio)
                if valor in vistos[nombre]:
                    raise ErrorValidacion(f"{nombre} duplicado")
            for nombre, extraer in texto_duplicado:
                vistos[nombre].add(extraer(limpio))
        except ErrorValidacion as error:
            _rechazar(entidad, resultado, rechazos, datos, archivo, num_fila, str(error))
            continue
        aceptados[clave_unica(limpio)] = limpio
        filas_insert.append(valores(limpio))

    marcadores = ", ".join("?" for _ in columnas_insert.split(","))
    sql = f"INSERT INTO {tabla} ({columnas_insert}) VALUES ({marcadores})"
    if id_fijo:
        with db.identity_insert(tabla):
            db.ejecutar_muchos(sql, filas_insert)
    else:
        db.ejecutar_muchos(sql, filas_insert)
    resultado.insertados = len(filas_insert)
    return aceptados


def cargar_clientes(db, resultado, rechazos) -> set:
    aceptados = _cargar_catalogo(
        db, _POR_NOMBRE["Clientes"], resultado, rechazos,
        validar=validate.validar_cliente,
        clave_unica=lambda c: c["id"],
        texto_duplicado=(("IdCliente", lambda c: c["id"]), ("Email", lambda c: c["email"])),
        tabla="dbo.Clientes", columnas_insert="IdCliente, Nombre, Email",
        valores=lambda c: (c["id"], c["nombre"], c["email"]),
        id_fijo=True,
    )
    return set(aceptados)


def cargar_productos(db, resultado, rechazos) -> set:
    aceptados = _cargar_catalogo(
        db, _POR_NOMBRE["Productos"], resultado, rechazos,
        validar=validate.validar_producto,
        clave_unica=lambda p: p["id"],
        texto_duplicado=(("IdProducto", lambda p: p["id"]),),
        tabla="dbo.Productos", columnas_insert="IdProducto, Nombre, Categoria",
        valores=lambda p: (p["id"], p["nombre"], p["categoria"]),
        id_fijo=True,
    )
    return set(aceptados)


def cargar_fuentes(db, resultado, rechazos) -> Dict[str, List[Tuple[int, date]]]:
    """Carga FuenteDatos. IdFuente = parte numérica del código (F001 -> 1).

    Devuelve {tipo: [(IdFuente, FechaCarga), ...]} para asignar fuentes
    a las opiniones.
    """
    aceptados = _cargar_catalogo(
        db, _POR_NOMBRE["FuenteDatos"], resultado, rechazos,
        validar=lambda fila: {**validate.validar_fuente(fila)},
        clave_unica=lambda f: f["codigo"],
        texto_duplicado=(("IdFuente", lambda f: f["codigo"]),),
        tabla="dbo.FuenteDatos", columnas_insert="IdFuente, CodigoFuente, TipoFuente, FechaCarga",
        valores=lambda f: (int(f["codigo"][1:]), f["codigo"], f["tipo"], f["fecha_carga"]),
        id_fijo=True,
    )
    por_tipo: Dict[str, List[Tuple[int, date]]] = {}
    for codigo, f in aceptados.items():
        por_tipo.setdefault(f["tipo"], []).append((int(codigo[1:]), f["fecha_carga"]))
    return por_tipo


def _fuente_mas_cercana(fuentes: List[Tuple[int, date]], fecha: date) -> int:
    """La fuente cuya fecha de carga está más cerca de la fecha de la opinión."""
    return min(fuentes, key=lambda f: (abs((f[1] - fecha).days), f[0]))[0]


# ----------------------------------------------------------------------
# Opiniones
# ----------------------------------------------------------------------
def _motivo_referencia(cliente_ok: bool, producto_ok: bool) -> Optional[str]:
    if cliente_ok and producto_ok:
        return None
    if not cliente_ok and not producto_ok:
        return "Integridad referencial: el cliente y el producto no existen en los catálogos"
    if not cliente_ok:
        return "Integridad referencial: el cliente no existe en el catálogo de clientes"
    return "Integridad referencial: el producto no existe en el catálogo de productos"


def _cargar_opiniones(
    db: Database, nombre: str, resultado: ResultadoEntidad, rechazos: List[Rechazo],
    clientes: set, productos: set, fuentes: Dict[str, List[Tuple[int, date]]],
    validar: Callable[[dict], dict], tabla: str, columnas: str,
    valores: Callable[[dict, int], tuple], clave_contenido: Callable[[dict], tuple],
) -> None:
    entidad = _POR_NOMBRE[nombre]
    tipo_fuente = _TIPO_FUENTE_CANAL[nombre]
    fuentes_canal = fuentes.get(tipo_fuente, [])
    id_origen_col = entidad.columnas_staging[0]
    ids_vistos: set = set()
    contenido_visto: set = set()
    filas_insert = []

    for datos, archivo, num_fila in _filas_staging(db, entidad):
        try:
            limpio = validar(datos)

            # duplicado por ID de origen (IdOpinion / IdReview / IdComment)
            id_origen = datos[id_origen_col].strip()
            if id_origen:
                if id_origen in ids_vistos:
                    raise ErrorValidacion(f"{id_origen_col} duplicado")
                ids_vistos.add(id_origen)

            # integridad referencial
            motivo = _motivo_referencia(
                limpio["id_cliente"] is None or limpio["id_cliente"] in clientes,
                limpio["id_producto"] in productos,
            )
            if motivo:
                raise ErrorValidacion(motivo)
            if not fuentes_canal:
                raise ErrorValidacion(
                    f"Integridad referencial: no hay fuentes de datos de tipo {tipo_fuente}"
                )

            # duplicado por contenido (misma opinión registrada dos veces)
            clave = clave_contenido(limpio)
            if clave in contenido_visto:
                raise ErrorValidacion("Registro duplicado (mismo cliente, producto, fecha y comentario)")
            contenido_visto.add(clave)
        except ErrorValidacion as error:
            _rechazar(entidad, resultado, rechazos, datos, archivo, num_fila, str(error))
            continue

        id_fuente = _fuente_mas_cercana(fuentes_canal, limpio["fecha"])
        filas_insert.append(valores(limpio, id_fuente))

    marcadores = ", ".join("?" for _ in columnas.split(","))
    db.ejecutar_muchos(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcadores})", filas_insert)
    resultado.insertados = len(filas_insert)


def cargar_encuestas(db, resultado, rechazos, clientes, productos, fuentes) -> None:
    _cargar_opiniones(
        db, "Encuestas", resultado, rechazos, clientes, productos, fuentes,
        validar=validate.validar_encuesta,
        tabla="dbo.Encuestas",
        columnas="IdCliente, IdProducto, IdFuente, Fecha, Comentario, PuntajeSatisfaccion",
        valores=lambda o, f: (o["id_cliente"], o["id_producto"], f, o["fecha"], o["comentario"], o["puntaje"]),
        clave_contenido=lambda o: (o["id_cliente"], o["id_producto"], o["fecha"], o["comentario"].lower()),
    )


def cargar_resenas(db, resultado, rechazos, clientes, productos, fuentes) -> None:
    _cargar_opiniones(
        db, "ResenasWeb", resultado, rechazos, clientes, productos, fuentes,
        validar=validate.validar_resena,
        tabla="dbo.ResenasWeb",
        columnas="IdCliente, IdProducto, IdFuente, Fecha, Comentario, Rating",
        valores=lambda o, f: (o["id_cliente"], o["id_producto"], f, o["fecha"], o["comentario"], o["rating"]),
        clave_contenido=lambda o: (o["id_cliente"], o["id_producto"], o["fecha"], o["comentario"].lower()),
    )


def cargar_comentarios_sociales(db, resultado, rechazos, clientes, productos, fuentes) -> None:
    _cargar_opiniones(
        db, "ComentariosSociales", resultado, rechazos, clientes, productos, fuentes,
        validar=validate.validar_comentario_social,
        tabla="dbo.ComentariosSociales",
        columnas="IdCliente, IdProducto, IdFuente, Plataforma, Fecha, Comentario",
        valores=lambda o, f: (o["id_cliente"], o["id_producto"], f, o["plataforma"], o["fecha"], o["comentario"]),
        clave_contenido=lambda o: (
            o["id_cliente"], o["id_producto"], o["plataforma"], o["fecha"], o["comentario"].lower()
        ),
    )


# ----------------------------------------------------------------------
# Orquestación de la capa 2
# ----------------------------------------------------------------------
def cargar_transaccional(
    db: Database, resultados: Dict[str, ResultadoEntidad], rechazos: List[Rechazo]
) -> None:
    """Carga la capa 2 completa. Si algo falla, el llamador hace rollback."""
    reiniciar_transaccional(db)

    clientes = cargar_clientes(db, resultados["Clientes"], rechazos)
    productos = cargar_productos(db, resultados["Productos"], rechazos)
    fuentes = cargar_fuentes(db, resultados["FuenteDatos"], rechazos)

    cargar_encuestas(db, resultados["Encuestas"], rechazos, clientes, productos, fuentes)
    cargar_resenas(db, resultados["ResenasWeb"], rechazos, clientes, productos, fuentes)
    cargar_comentarios_sociales(db, resultados["ComentariosSociales"], rechazos, clientes, productos, fuentes)

    for nombre, resultado in resultados.items():
        log.info(
            "[Capa 2] %-20s %4d insertados, %d rechazados",
            nombre, resultado.insertados, resultado.rechazados,
        )
