"""Conexión a SQL Server y utilidades para ejecutar consultas."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime

import config
from etl.modelos import ErrorConexion

log = logging.getLogger(__name__)


class Database:
    """Envuelve la conexión para que el resto del ETL no dependa del driver."""

    def __init__(self, conexion, es_sqlserver: bool = True):
        self.conexion = conexion
        self.es_sqlserver = es_sqlserver

    # -- consultas ------------------------------------------------------
    def _params(self, params):
        # SQL Server recibe objetos date; el modo de pruebas (SQLite) texto
        if self.es_sqlserver:
            return tuple(params)
        return tuple(p.isoformat() if isinstance(p, (date, datetime)) else p for p in params)

    def ejecutar(self, sql: str, params=()):
        cursor = self.conexion.cursor()
        cursor.execute(sql, self._params(params))
        return cursor

    def ejecutar_muchos(self, sql: str, filas) -> None:
        filas = [self._params(f) for f in filas]
        if not filas:
            return
        cursor = self.conexion.cursor()
        cursor.executemany(sql, filas)

    def consultar(self, sql: str, params=()) -> list:
        cursor = self.ejecutar(sql, params)
        return cursor.fetchall()

    def escalar(self, sql: str, params=()):
        fila = self.ejecutar(sql, params).fetchone()
        return fila[0] if fila else None

    @contextmanager
    def identity_insert(self, tabla: str):
        """Permite insertar valores explícitos en una columna IDENTITY.

        Así los catálogos conservan los IDs de los CSV y las demás tablas
        pueden referenciarlos (por ejemplo C007 -> 7).
        """
        if not self.es_sqlserver:
            yield
            return
        self.ejecutar(f"SET IDENTITY_INSERT {tabla} ON")
        try:
            yield
        finally:
            self.ejecutar(f"SET IDENTITY_INSERT {tabla} OFF")

    # -- transacciones --------------------------------------------------
    def commit(self) -> None:
        self.conexion.commit()

    def rollback(self) -> None:
        self.conexion.rollback()

    def cerrar(self) -> None:
        self.conexion.close()


def _elegir_driver(pyodbc) -> str:
    if config.DB_DRIVER:
        return config.DB_DRIVER
    instalados = [d for d in pyodbc.drivers() if "SQL Server" in d]
    modernos = sorted((d for d in instalados if d.startswith("ODBC Driver")), reverse=True)
    if modernos:
        return modernos[0]
    if instalados:
        return instalados[0]
    raise ErrorConexion(
        "No se encontró ningún driver ODBC de SQL Server. "
        "Instala 'ODBC Driver 17 (o 18) for SQL Server' desde Microsoft."
    )


def conectar() -> Database:
    """Abre la conexión a SQL Server usando la configuración de config.py."""
    try:
        import pyodbc
    except ImportError as exc:
        raise ErrorConexion(
            "Falta la librería pyodbc. Instálala con: pip install pyodbc"
        ) from exc

    driver = _elegir_driver(pyodbc)
    partes = [
        f"DRIVER={{{driver}}}",
        f"SERVER={config.DB_SERVER}",
        f"DATABASE={config.DB_NAME}",
    ]
    if config.DB_USER:
        partes += [f"UID={config.DB_USER}", f"PWD={config.DB_PASSWORD}"]
    else:
        partes.append("Trusted_Connection=yes")
    if driver.startswith("ODBC Driver"):
        partes.append("TrustServerCertificate=yes")

    log.info("Conectando a %s / %s con el driver '%s'", config.DB_SERVER, config.DB_NAME, driver)
    try:
        conexion = pyodbc.connect(";".join(partes), autocommit=False, timeout=15)
    except pyodbc.Error as exc:
        raise ErrorConexion(
            f"No se pudo conectar a SQL Server ({config.DB_SERVER}, base {config.DB_NAME}).\n"
            "Revisa que el servidor esté encendido, que el nombre del servidor sea el de SSMS "
            "(variable ETL_SERVER) y que hayas ejecutado sql/01_script_base_datos.sql.\n"
            f"Detalle: {exc}"
        ) from exc
    return Database(conexion, es_sqlserver=True)
