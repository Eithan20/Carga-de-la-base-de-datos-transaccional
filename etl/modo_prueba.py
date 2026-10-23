"""Base de datos de prueba en memoria (SQLite) para las pruebas automáticas.

Replica las dos capas (esquemas stg y dbo) con las mismas claves primarias,
foráneas y restricciones del script de SQL Server, para poder probar las
validaciones del ETL sin tocar la base real. Solo la usan los tests.
"""
from __future__ import annotations

import sqlite3

from etl.database import Database

_DDL = """
CREATE TABLE dbo.Clientes (
    IdCliente INTEGER PRIMARY KEY,
    Nombre TEXT NOT NULL,
    Email TEXT NOT NULL UNIQUE
);
CREATE TABLE dbo.Productos (
    IdProducto INTEGER PRIMARY KEY,
    Nombre TEXT NOT NULL,
    Categoria TEXT NOT NULL
);
CREATE TABLE dbo.FuenteDatos (
    IdFuente INTEGER PRIMARY KEY,
    CodigoFuente TEXT NOT NULL UNIQUE,
    TipoFuente TEXT NOT NULL CHECK (TipoFuente IN ('CSV', 'Web', 'Red Social')),
    FechaCarga TEXT NOT NULL
);
CREATE TABLE dbo.Encuestas (
    IdEncuesta INTEGER PRIMARY KEY AUTOINCREMENT,
    IdCliente INTEGER NOT NULL REFERENCES Clientes(IdCliente),
    IdProducto INTEGER NOT NULL REFERENCES Productos(IdProducto),
    IdFuente INTEGER NOT NULL REFERENCES FuenteDatos(IdFuente),
    Fecha TEXT NOT NULL,
    Comentario TEXT NOT NULL,
    PuntajeSatisfaccion INTEGER NOT NULL CHECK (PuntajeSatisfaccion BETWEEN 1 AND 5)
);
CREATE TABLE dbo.ResenasWeb (
    IdResena INTEGER PRIMARY KEY AUTOINCREMENT,
    IdCliente INTEGER NULL REFERENCES Clientes(IdCliente),
    IdProducto INTEGER NOT NULL REFERENCES Productos(IdProducto),
    IdFuente INTEGER NOT NULL REFERENCES FuenteDatos(IdFuente),
    Fecha TEXT NOT NULL,
    Comentario TEXT NOT NULL,
    Rating INTEGER NOT NULL CHECK (Rating BETWEEN 1 AND 5)
);
CREATE TABLE dbo.ComentariosSociales (
    IdComentario INTEGER PRIMARY KEY AUTOINCREMENT,
    IdCliente INTEGER NULL REFERENCES Clientes(IdCliente),
    IdProducto INTEGER NOT NULL REFERENCES Productos(IdProducto),
    IdFuente INTEGER NOT NULL REFERENCES FuenteDatos(IdFuente),
    Plataforma TEXT NOT NULL CHECK (Plataforma IN ('Instagram', 'Facebook', 'Twitter')),
    Fecha TEXT NOT NULL,
    Comentario TEXT NOT NULL
);

CREATE TABLE stg.Clientes (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdCliente TEXT, Nombre TEXT, Email TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.Productos (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdProducto TEXT, Nombre TEXT, Categoria TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.FuenteDatos (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdFuente TEXT, TipoFuente TEXT, FechaCarga TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.Encuestas (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdOpinion TEXT, IdCliente TEXT, IdProducto TEXT, Fecha TEXT, Comentario TEXT,
    Clasificacion TEXT, PuntajeSatisfaccion TEXT, Fuente TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.ResenasWeb (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdReview TEXT, IdCliente TEXT, IdProducto TEXT, Fecha TEXT, Comentario TEXT, Rating TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.ComentariosSociales (
    IdStg INTEGER PRIMARY KEY AUTOINCREMENT,
    IdComment TEXT, IdCliente TEXT, IdProducto TEXT, Fuente TEXT, Fecha TEXT, Comentario TEXT,
    ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    FechaExtraccion TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE stg.RegistrosRechazados (
    IdRechazo INTEGER PRIMARY KEY AUTOINCREMENT,
    Entidad TEXT NOT NULL, ArchivoOrigen TEXT NOT NULL, NumFila INTEGER NOT NULL,
    IdOrigen TEXT, Motivo TEXT NOT NULL, DatoOriginal TEXT,
    FechaRechazo TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def crear_base_prueba() -> Database:
    """Crea una base SQLite en memoria con los esquemas dbo y stg."""
    conexion = sqlite3.connect(":memory:")
    conexion.execute("ATTACH DATABASE ':memory:' AS stg")
    conexion.execute("ATTACH DATABASE ':memory:' AS dbo")
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(_DDL)
    conexion.commit()
    return Database(conexion, es_sqlserver=False)
