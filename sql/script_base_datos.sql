-- ============================================================
-- SISTEMA DE ANÁLISIS DE OPINIONES DE CLIENTES
-- Script de base de datos para el proceso ETL (SQL Server)
--
-- Arquitectura de 2 capas:
--   Capa 1  esquema stg : staging, copia cruda de los CSV
--   Capa 2  esquema dbo : base de datos transaccional
--
-- Contenido:
--   1. Creación de la base de datos y del esquema stg
--   2. Capa 2: tablas transaccionales (PK, FK, CHECK, UNIQUE, índices)
--   3. Capa 1: tablas de staging y tabla de rechazados
--   4. Vistas
--   5. Procedimientos almacenados
--
-- Se puede ejecutar varias veces: recrea las tablas (borra los datos).
-- Ejecutar el script completo con F5.
-- ============================================================

USE master;
GO

IF DB_ID(N'AnalisisOpinionesTransaccional') IS NULL
    CREATE DATABASE AnalisisOpinionesTransaccional;
GO

USE AnalisisOpinionesTransaccional;
GO

IF SCHEMA_ID(N'stg') IS NULL
    EXEC (N'CREATE SCHEMA stg');
GO


-- ============================================================
-- LIMPIEZA PREVIA (hijas primero, padres después)
-- ============================================================

DROP TABLE IF EXISTS dbo.ComentariosSociales;
DROP TABLE IF EXISTS dbo.ResenasWeb;
DROP TABLE IF EXISTS dbo.Encuestas;
DROP TABLE IF EXISTS dbo.FuenteDatos;
DROP TABLE IF EXISTS dbo.Productos;
DROP TABLE IF EXISTS dbo.Clientes;

DROP TABLE IF EXISTS stg.RegistrosRechazados;
DROP TABLE IF EXISTS stg.ComentariosSociales;
DROP TABLE IF EXISTS stg.ResenasWeb;
DROP TABLE IF EXISTS stg.Encuestas;
DROP TABLE IF EXISTS stg.FuenteDatos;
DROP TABLE IF EXISTS stg.Productos;
DROP TABLE IF EXISTS stg.Clientes;
GO


-- ============================================================
-- CAPA 2: BASE DE DATOS TRANSACCIONAL (esquema dbo)
-- ============================================================

CREATE TABLE dbo.Clientes
(
    IdCliente INT IDENTITY(1,1) NOT NULL,
    Nombre NVARCHAR(100) NOT NULL,
    Email NVARCHAR(150) NOT NULL,

    CONSTRAINT PK_Clientes
        PRIMARY KEY (IdCliente),

    CONSTRAINT UQ_Clientes_Email
        UNIQUE (Email)
);
GO

CREATE TABLE dbo.Productos
(
    IdProducto INT IDENTITY(1,1) NOT NULL,
    Nombre NVARCHAR(100) NOT NULL,
    Categoria NVARCHAR(50) NOT NULL,

    CONSTRAINT PK_Productos
        PRIMARY KEY (IdProducto)
);
GO

CREATE TABLE dbo.FuenteDatos
(
    IdFuente INT IDENTITY(1,1) NOT NULL,
    CodigoFuente VARCHAR(10) NOT NULL,
    TipoFuente VARCHAR(20) NOT NULL,
    FechaCarga DATE NOT NULL,

    CONSTRAINT PK_FuenteDatos
        PRIMARY KEY (IdFuente),

    CONSTRAINT UQ_FuenteDatos_Codigo
        UNIQUE (CodigoFuente),

    CONSTRAINT CK_FuenteDatos_Tipo
        CHECK (TipoFuente IN ('CSV', 'Web', 'Red Social'))
);
GO

CREATE TABLE dbo.Encuestas
(
    IdEncuesta BIGINT IDENTITY(1,1) NOT NULL,
    IdCliente INT NOT NULL,
    IdProducto INT NOT NULL,
    IdFuente INT NOT NULL,
    Fecha DATE NOT NULL,
    Comentario NVARCHAR(500) NOT NULL,
    PuntajeSatisfaccion TINYINT NOT NULL,

    CONSTRAINT PK_Encuestas
        PRIMARY KEY (IdEncuesta),

    CONSTRAINT FK_Encuestas_Clientes
        FOREIGN KEY (IdCliente)
        REFERENCES dbo.Clientes(IdCliente),

    CONSTRAINT FK_Encuestas_Productos
        FOREIGN KEY (IdProducto)
        REFERENCES dbo.Productos(IdProducto),

    CONSTRAINT FK_Encuestas_FuenteDatos
        FOREIGN KEY (IdFuente)
        REFERENCES dbo.FuenteDatos(IdFuente),

    CONSTRAINT CK_Encuestas_Puntaje
        CHECK (PuntajeSatisfaccion BETWEEN 1 AND 5)
);
GO

CREATE TABLE dbo.ResenasWeb
(
    IdResena BIGINT IDENTITY(1,1) NOT NULL,
    IdCliente INT NULL,
    IdProducto INT NOT NULL,
    IdFuente INT NOT NULL,
    Fecha DATE NOT NULL,
    Comentario NVARCHAR(500) NOT NULL,
    Rating TINYINT NOT NULL,

    CONSTRAINT PK_ResenasWeb
        PRIMARY KEY (IdResena),

    CONSTRAINT FK_ResenasWeb_Clientes
        FOREIGN KEY (IdCliente)
        REFERENCES dbo.Clientes(IdCliente),

    CONSTRAINT FK_ResenasWeb_Productos
        FOREIGN KEY (IdProducto)
        REFERENCES dbo.Productos(IdProducto),

    CONSTRAINT FK_ResenasWeb_FuenteDatos
        FOREIGN KEY (IdFuente)
        REFERENCES dbo.FuenteDatos(IdFuente),

    CONSTRAINT CK_ResenasWeb_Rating
        CHECK (Rating BETWEEN 1 AND 5)
);
GO

CREATE TABLE dbo.ComentariosSociales
(
    IdComentario BIGINT IDENTITY(1,1) NOT NULL,
    IdCliente INT NULL,
    IdProducto INT NOT NULL,
    IdFuente INT NOT NULL,
    Plataforma VARCHAR(30) NOT NULL,
    Fecha DATE NOT NULL,
    Comentario NVARCHAR(500) NOT NULL,

    CONSTRAINT PK_ComentariosSociales
        PRIMARY KEY (IdComentario),

    CONSTRAINT FK_ComentariosSociales_Clientes
        FOREIGN KEY (IdCliente)
        REFERENCES dbo.Clientes(IdCliente),

    CONSTRAINT FK_ComentariosSociales_Productos
        FOREIGN KEY (IdProducto)
        REFERENCES dbo.Productos(IdProducto),

    CONSTRAINT FK_ComentariosSociales_FuenteDatos
        FOREIGN KEY (IdFuente)
        REFERENCES dbo.FuenteDatos(IdFuente),

    CONSTRAINT CK_ComentariosSociales_Plataforma
        CHECK (Plataforma IN ('Instagram', 'Facebook', 'Twitter'))
);
GO

CREATE INDEX IX_Encuestas_Producto_Fecha
ON dbo.Encuestas (IdProducto, Fecha);
GO

CREATE INDEX IX_ResenasWeb_Producto_Fecha
ON dbo.ResenasWeb (IdProducto, Fecha);
GO

CREATE INDEX IX_ComentariosSociales_Producto_Fecha
ON dbo.ComentariosSociales (IdProducto, Fecha);
GO


-- ============================================================
-- CAPA 1: STAGING (esquema stg)
-- Copia cruda de los CSV: todo el contenido como texto y sin
-- claves foráneas, para que la extracción nunca falle por datos
-- sucios. La validación ocurre al pasar a la capa transaccional.
-- ============================================================

CREATE TABLE stg.Clientes
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdCliente NVARCHAR(100) NULL,
    Nombre NVARCHAR(1000) NULL,
    Email NVARCHAR(1000) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_Clientes_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_Clientes PRIMARY KEY (IdStg)
);
GO

CREATE TABLE stg.Productos
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdProducto NVARCHAR(100) NULL,
    Nombre NVARCHAR(1000) NULL,
    Categoria NVARCHAR(1000) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_Productos_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_Productos PRIMARY KEY (IdStg)
);
GO

CREATE TABLE stg.FuenteDatos
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdFuente NVARCHAR(100) NULL,
    TipoFuente NVARCHAR(100) NULL,
    FechaCarga NVARCHAR(100) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_FuenteDatos_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_FuenteDatos PRIMARY KEY (IdStg)
);
GO

CREATE TABLE stg.Encuestas
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdOpinion NVARCHAR(100) NULL,
    IdCliente NVARCHAR(100) NULL,
    IdProducto NVARCHAR(100) NULL,
    Fecha NVARCHAR(100) NULL,
    Comentario NVARCHAR(1000) NULL,
    Clasificacion NVARCHAR(100) NULL,
    PuntajeSatisfaccion NVARCHAR(100) NULL,
    Fuente NVARCHAR(100) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_Encuestas_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_Encuestas PRIMARY KEY (IdStg)
);
GO

CREATE TABLE stg.ResenasWeb
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdReview NVARCHAR(100) NULL,
    IdCliente NVARCHAR(100) NULL,
    IdProducto NVARCHAR(100) NULL,
    Fecha NVARCHAR(100) NULL,
    Comentario NVARCHAR(1000) NULL,
    Rating NVARCHAR(100) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_ResenasWeb_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_ResenasWeb PRIMARY KEY (IdStg)
);
GO

CREATE TABLE stg.ComentariosSociales
(
    IdStg INT IDENTITY(1,1) NOT NULL,
    IdComment NVARCHAR(100) NULL,
    IdCliente NVARCHAR(100) NULL,
    IdProducto NVARCHAR(100) NULL,
    Fuente NVARCHAR(100) NULL,
    Fecha NVARCHAR(100) NULL,
    Comentario NVARCHAR(1000) NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    FechaExtraccion DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_Sociales_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_ComentariosSociales PRIMARY KEY (IdStg)
);
GO

-- Registros que el ETL no pudo cargar, con el motivo del rechazo
CREATE TABLE stg.RegistrosRechazados
(
    IdRechazo INT IDENTITY(1,1) NOT NULL,
    Entidad VARCHAR(30) NOT NULL,
    ArchivoOrigen NVARCHAR(260) NOT NULL,
    NumFila INT NOT NULL,
    IdOrigen NVARCHAR(100) NULL,
    Motivo NVARCHAR(300) NOT NULL,
    DatoOriginal NVARCHAR(2000) NULL,
    FechaRechazo DATETIME2(0) NOT NULL
        CONSTRAINT DF_stg_Rechazados_Fecha DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_stg_RegistrosRechazados PRIMARY KEY (IdRechazo)
);
GO


-- ============================================================
-- VISTAS
-- ============================================================

-- Las tres fuentes de opinión en un solo conjunto de resultados
CREATE OR ALTER VIEW dbo.vw_OpinionesUnificadas
AS
SELECT
    CAST('Encuesta' AS VARCHAR(20)) AS Canal,
    e.IdEncuesta AS IdRegistro,
    e.IdCliente,
    e.IdProducto,
    e.IdFuente,
    CAST('EncuestaInterna' AS VARCHAR(30)) AS Plataforma,
    e.Fecha,
    e.Comentario,
    e.PuntajeSatisfaccion AS Puntaje
FROM dbo.Encuestas e

UNION ALL

SELECT
    'ResenaWeb',
    r.IdResena,
    r.IdCliente,
    r.IdProducto,
    r.IdFuente,
    'SitioWeb',
    r.Fecha,
    r.Comentario,
    r.Rating
FROM dbo.ResenasWeb r

UNION ALL

SELECT
    'ComentarioSocial',
    c.IdComentario,
    c.IdCliente,
    c.IdProducto,
    c.IdFuente,
    c.Plataforma,
    c.Fecha,
    c.Comentario,
    CAST(NULL AS TINYINT)
FROM dbo.ComentariosSociales c;
GO

-- Cantidad de opiniones y satisfacción por producto.
-- PorcentajeSatisfaccion = % de opiniones con puntaje 4 o 5
-- (los comentarios sociales no traen puntaje y no entran en el cálculo).
CREATE OR ALTER VIEW dbo.vw_SatisfaccionPorProducto
AS
SELECT
    p.IdProducto,
    p.Nombre AS Producto,
    p.Categoria,
    COUNT(o.IdRegistro) AS TotalOpiniones,
    COUNT(o.Puntaje) AS OpinionesConPuntaje,
    CAST(AVG(CAST(o.Puntaje AS DECIMAL(5,2))) AS DECIMAL(4,2)) AS PuntajePromedio,
    CAST(
        100.0 * SUM(CASE WHEN o.Puntaje >= 4 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(o.Puntaje), 0)
        AS DECIMAL(5,2)
    ) AS PorcentajeSatisfaccion
FROM dbo.Productos p
LEFT JOIN dbo.vw_OpinionesUnificadas o
    ON o.IdProducto = p.IdProducto
GROUP BY p.IdProducto, p.Nombre, p.Categoria;
GO

-- Tendencia de satisfacción por producto y mes
CREATE OR ALTER VIEW dbo.vw_TendenciaSatisfaccionMensual
AS
SELECT
    o.IdProducto,
    p.Nombre AS Producto,
    YEAR(o.Fecha) AS Anio,
    MONTH(o.Fecha) AS Mes,
    COUNT(*) AS TotalOpiniones,
    CAST(AVG(CAST(o.Puntaje AS DECIMAL(5,2))) AS DECIMAL(4,2)) AS PuntajePromedio
FROM dbo.vw_OpinionesUnificadas o
INNER JOIN dbo.Productos p
    ON p.IdProducto = o.IdProducto
WHERE o.Puntaje IS NOT NULL
GROUP BY o.IdProducto, p.Nombre, YEAR(o.Fecha), MONTH(o.Fecha);
GO

-- Registros rechazados por el ETL agrupados por motivo
CREATE OR ALTER VIEW dbo.vw_ResumenRechazos
AS
SELECT
    Entidad,
    Motivo,
    COUNT(*) AS Cantidad
FROM stg.RegistrosRechazados
GROUP BY Entidad, Motivo;
GO


-- ============================================================
-- PROCEDIMIENTOS ALMACENADOS
-- ============================================================

-- Opiniones de un producto, con filtro opcional por rango de fechas
CREATE OR ALTER PROCEDURE dbo.usp_OpinionesPorProducto
    @IdProducto INT,
    @FechaDesde DATE = NULL,
    @FechaHasta DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        o.Canal,
        o.Plataforma,
        o.IdRegistro,
        o.IdCliente,
        o.Fecha,
        o.Comentario,
        o.Puntaje
    FROM dbo.vw_OpinionesUnificadas o
    WHERE o.IdProducto = @IdProducto
      AND (@FechaDesde IS NULL OR o.Fecha >= @FechaDesde)
      AND (@FechaHasta IS NULL OR o.Fecha <= @FechaHasta)
    ORDER BY o.Fecha, o.Canal, o.IdRegistro;
END
GO

-- Satisfacción de un producto (o de todos si no se indica ninguno)
CREATE OR ALTER PROCEDURE dbo.usp_SatisfaccionPorProducto
    @IdProducto INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        IdProducto,
        Producto,
        Categoria,
        TotalOpiniones,
        OpinionesConPuntaje,
        PuntajePromedio,
        PorcentajeSatisfaccion
    FROM dbo.vw_SatisfaccionPorProducto
    WHERE @IdProducto IS NULL OR IdProducto = @IdProducto
    ORDER BY TotalOpiniones DESC, IdProducto;
END
GO

-- Resumen de la última carga: registros en staging, rechazados y
-- registros actualmente en la base transaccional
CREATE OR ALTER PROCEDURE dbo.usp_ResumenCarga
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        'Clientes' AS Entidad,
        (SELECT COUNT(*) FROM stg.Clientes) AS EnStaging,
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Clientes') AS Rechazados,
        (SELECT COUNT(*) FROM dbo.Clientes) AS EnTransaccional
    UNION ALL
    SELECT
        'Productos',
        (SELECT COUNT(*) FROM stg.Productos),
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Productos'),
        (SELECT COUNT(*) FROM dbo.Productos)
    UNION ALL
    SELECT
        'FuenteDatos',
        (SELECT COUNT(*) FROM stg.FuenteDatos),
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'FuenteDatos'),
        (SELECT COUNT(*) FROM dbo.FuenteDatos)
    UNION ALL
    SELECT
        'Encuestas',
        (SELECT COUNT(*) FROM stg.Encuestas),
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Encuestas'),
        (SELECT COUNT(*) FROM dbo.Encuestas)
    UNION ALL
    SELECT
        'ResenasWeb',
        (SELECT COUNT(*) FROM stg.ResenasWeb),
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'ResenasWeb'),
        (SELECT COUNT(*) FROM dbo.ResenasWeb)
    UNION ALL
    SELECT
        'ComentariosSociales',
        (SELECT COUNT(*) FROM stg.ComentariosSociales),
        (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'ComentariosSociales'),
        (SELECT COUNT(*) FROM dbo.ComentariosSociales);
END
GO

-- Vacía las dos capas respetando el orden de las claves foráneas
CREATE OR ALTER PROCEDURE dbo.usp_ReiniciarCarga
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.ComentariosSociales;
        DELETE FROM dbo.ResenasWeb;
        DELETE FROM dbo.Encuestas;
        DELETE FROM dbo.FuenteDatos;
        DELETE FROM dbo.Productos;
        DELETE FROM dbo.Clientes;

        DELETE FROM stg.RegistrosRechazados;
        DELETE FROM stg.ComentariosSociales;
        DELETE FROM stg.ResenasWeb;
        DELETE FROM stg.Encuestas;
        DELETE FROM stg.FuenteDatos;
        DELETE FROM stg.Productos;
        DELETE FROM stg.Clientes;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END
GO


-- ============================================================
-- VERIFICACIÓN: objetos creados
-- ============================================================

SELECT s.name AS Esquema, t.name AS Tabla
FROM sys.tables t
INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name IN ('dbo', 'stg')
ORDER BY s.name, t.name;

SELECT s.name AS Esquema, o.name AS Objeto, o.type_desc AS Tipo
FROM sys.objects o
INNER JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE s.name = 'dbo' AND o.type IN ('V', 'P')
ORDER BY o.type_desc, o.name;
GO
