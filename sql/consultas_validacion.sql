-- ============================================================
-- CONSULTAS DE VALIDACIÓN DE LA CARGA
-- Ejecutar DESPUÉS de correr el ETL (python main.py).
-- Cada consulta indica el resultado esperado con los CSV del proyecto.
-- Ejecutar de una en una (seleccionar la consulta y pulsar F5) para
-- sacar una captura de cada resultado.
-- ============================================================

USE AnalisisOpinionesTransaccional;
GO


-- ------------------------------------------------------------
-- CONSULTA 1: Cantidad de registros cargados en cada tabla
-- Esperado: Clientes 500, Productos 200, FuenteDatos 100,
--           Encuestas 6, ResenasWeb 200, ComentariosSociales 200
-- ------------------------------------------------------------
SELECT 'Clientes' AS Tabla, COUNT(*) AS Registros FROM dbo.Clientes
UNION ALL SELECT 'Productos', COUNT(*) FROM dbo.Productos
UNION ALL SELECT 'FuenteDatos', COUNT(*) FROM dbo.FuenteDatos
UNION ALL SELECT 'Encuestas', COUNT(*) FROM dbo.Encuestas
UNION ALL SELECT 'ResenasWeb', COUNT(*) FROM dbo.ResenasWeb
UNION ALL SELECT 'ComentariosSociales', COUNT(*) FROM dbo.ComentariosSociales;
GO


-- ------------------------------------------------------------
-- CONSULTA 2: Integridad referencial - registros huérfanos
-- Busca opiniones cuyo cliente, producto o fuente no existe.
-- Esperado: 0 en las 9 filas
-- ------------------------------------------------------------
SELECT 'Encuestas sin cliente' AS Comprobacion, COUNT(*) AS Huerfanos
FROM dbo.Encuestas e LEFT JOIN dbo.Clientes c ON c.IdCliente = e.IdCliente
WHERE c.IdCliente IS NULL
UNION ALL
SELECT 'Encuestas sin producto', COUNT(*)
FROM dbo.Encuestas e LEFT JOIN dbo.Productos p ON p.IdProducto = e.IdProducto
WHERE p.IdProducto IS NULL
UNION ALL
SELECT 'Encuestas sin fuente', COUNT(*)
FROM dbo.Encuestas e LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = e.IdFuente
WHERE f.IdFuente IS NULL
UNION ALL
SELECT 'Reseñas con cliente inexistente', COUNT(*)
FROM dbo.ResenasWeb r LEFT JOIN dbo.Clientes c ON c.IdCliente = r.IdCliente
WHERE r.IdCliente IS NOT NULL AND c.IdCliente IS NULL
UNION ALL
SELECT 'Reseñas sin producto', COUNT(*)
FROM dbo.ResenasWeb r LEFT JOIN dbo.Productos p ON p.IdProducto = r.IdProducto
WHERE p.IdProducto IS NULL
UNION ALL
SELECT 'Reseñas sin fuente', COUNT(*)
FROM dbo.ResenasWeb r LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = r.IdFuente
WHERE f.IdFuente IS NULL
UNION ALL
SELECT 'Comentarios con cliente inexistente', COUNT(*)
FROM dbo.ComentariosSociales s LEFT JOIN dbo.Clientes c ON c.IdCliente = s.IdCliente
WHERE s.IdCliente IS NOT NULL AND c.IdCliente IS NULL
UNION ALL
SELECT 'Comentarios sin producto', COUNT(*)
FROM dbo.ComentariosSociales s LEFT JOIN dbo.Productos p ON p.IdProducto = s.IdProducto
WHERE p.IdProducto IS NULL
UNION ALL
SELECT 'Comentarios sin fuente', COUNT(*)
FROM dbo.ComentariosSociales s LEFT JOIN dbo.FuenteDatos f ON f.IdFuente = s.IdFuente
WHERE f.IdFuente IS NULL;
GO


-- ------------------------------------------------------------
-- CONSULTA 3: Registros duplicados
-- Correos repetidos, códigos de fuente repetidos y opiniones
-- repetidas (mismo cliente, producto, fecha y comentario).
-- Esperado: 0 en las 5 filas (no deben salir duplicados)
-- ------------------------------------------------------------
SELECT 'Correos repetidos en Clientes' AS Comprobacion, COUNT(*) AS Duplicados
FROM (SELECT Email FROM dbo.Clientes GROUP BY Email HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'Códigos de fuente repetidos', COUNT(*)
FROM (SELECT CodigoFuente FROM dbo.FuenteDatos GROUP BY CodigoFuente HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'Encuestas repetidas', COUNT(*)
FROM (SELECT IdCliente, IdProducto, Fecha, Comentario FROM dbo.Encuestas
      GROUP BY IdCliente, IdProducto, Fecha, Comentario HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'Reseñas repetidas', COUNT(*)
FROM (SELECT IdCliente, IdProducto, Fecha, Comentario FROM dbo.ResenasWeb
      GROUP BY IdCliente, IdProducto, Fecha, Comentario HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'Comentarios sociales repetidos', COUNT(*)
FROM (SELECT IdCliente, IdProducto, Plataforma, Fecha, Comentario FROM dbo.ComentariosSociales
      GROUP BY IdCliente, IdProducto, Plataforma, Fecha, Comentario HAVING COUNT(*) > 1) x;
GO


-- ------------------------------------------------------------
-- CONSULTA 4: Cuadre del proceso: procesados = cargados + rechazados
-- Compara lo que entró a staging con lo que quedó en la base
-- transaccional y con lo rechazado.
-- Esperado: la columna Cuadra = 'SI' en las 6 filas
-- ------------------------------------------------------------
SELECT
    r.Entidad,
    r.EnStaging AS Procesados,
    r.EnTransaccional AS Cargados,
    r.Rechazados,
    CASE WHEN r.EnStaging = r.EnTransaccional + r.Rechazados THEN 'SI' ELSE 'NO' END AS Cuadra
FROM
(
    SELECT 'Clientes' AS Entidad,
           (SELECT COUNT(*) FROM stg.Clientes) AS EnStaging,
           (SELECT COUNT(*) FROM dbo.Clientes) AS EnTransaccional,
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Clientes') AS Rechazados
    UNION ALL
    SELECT 'Productos',
           (SELECT COUNT(*) FROM stg.Productos),
           (SELECT COUNT(*) FROM dbo.Productos),
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Productos')
    UNION ALL
    SELECT 'FuenteDatos',
           (SELECT COUNT(*) FROM stg.FuenteDatos),
           (SELECT COUNT(*) FROM dbo.FuenteDatos),
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'FuenteDatos')
    UNION ALL
    SELECT 'Encuestas',
           (SELECT COUNT(*) FROM stg.Encuestas),
           (SELECT COUNT(*) FROM dbo.Encuestas),
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'Encuestas')
    UNION ALL
    SELECT 'ResenasWeb',
           (SELECT COUNT(*) FROM stg.ResenasWeb),
           (SELECT COUNT(*) FROM dbo.ResenasWeb),
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'ResenasWeb')
    UNION ALL
    SELECT 'ComentariosSociales',
           (SELECT COUNT(*) FROM stg.ComentariosSociales),
           (SELECT COUNT(*) FROM dbo.ComentariosSociales),
           (SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Entidad = 'ComentariosSociales')
) r;
GO


-- ------------------------------------------------------------
-- CONSULTA 5: Motivos de los registros rechazados (vista)
-- Esperado: 3 filas de Encuestas por integridad referencial
--           (386 + 87 + 21 = 494)
-- ------------------------------------------------------------
SELECT * FROM dbo.vw_ResumenRechazos ORDER BY Cantidad DESC;
GO


-- ------------------------------------------------------------
-- CONSULTA 6: Cada canal usa fuentes de su tipo
-- Encuestas -> CSV, Reseñas -> Web, Comentarios -> Red Social
-- Esperado: 0 en las 3 filas
-- ------------------------------------------------------------
SELECT 'Encuestas con fuente que no es CSV' AS Comprobacion, COUNT(*) AS Incorrectas
FROM dbo.Encuestas e INNER JOIN dbo.FuenteDatos f ON f.IdFuente = e.IdFuente
WHERE f.TipoFuente <> 'CSV'
UNION ALL
SELECT 'Reseñas con fuente que no es Web', COUNT(*)
FROM dbo.ResenasWeb r INNER JOIN dbo.FuenteDatos f ON f.IdFuente = r.IdFuente
WHERE f.TipoFuente <> 'Web'
UNION ALL
SELECT 'Comentarios con fuente que no es Red Social', COUNT(*)
FROM dbo.ComentariosSociales s INNER JOIN dbo.FuenteDatos f ON f.IdFuente = s.IdFuente
WHERE f.TipoFuente <> 'Red Social';
GO


-- ------------------------------------------------------------
-- CONSULTA 7: Valores dentro de los rangos permitidos
-- Esperado: 0 en las 3 filas
-- ------------------------------------------------------------
SELECT 'Encuestas con puntaje fuera de 1-5' AS Comprobacion, COUNT(*) AS FueraDeRango
FROM dbo.Encuestas WHERE PuntajeSatisfaccion NOT BETWEEN 1 AND 5
UNION ALL
SELECT 'Reseñas con rating fuera de 1-5', COUNT(*)
FROM dbo.ResenasWeb WHERE Rating NOT BETWEEN 1 AND 5
UNION ALL
SELECT 'Comentarios con plataforma no válida', COUNT(*)
FROM dbo.ComentariosSociales WHERE Plataforma NOT IN ('Instagram', 'Facebook', 'Twitter');
GO


-- ------------------------------------------------------------
-- CONSULTA 8: Relación entre tablas (JOIN de las 4 tablas)
-- Muestra reseñas web con el nombre del cliente, el producto y la fuente.
-- Esperado: 10 filas con todos los nombres completos
--           (las reseñas anónimas, si salen, tienen el cliente vacío)
-- ------------------------------------------------------------
SELECT TOP 10
    r.IdResena,
    c.Nombre AS Cliente,
    p.Nombre AS Producto,
    p.Categoria,
    f.CodigoFuente,
    f.TipoFuente,
    r.Fecha,
    r.Rating
FROM dbo.ResenasWeb r
LEFT JOIN dbo.Clientes c ON c.IdCliente = r.IdCliente
INNER JOIN dbo.Productos p ON p.IdProducto = r.IdProducto
INNER JOIN dbo.FuenteDatos f ON f.IdFuente = r.IdFuente
ORDER BY r.IdResena;
GO


-- ------------------------------------------------------------
-- CONSULTA 9: Prueba de que la base protege la integridad
-- Este INSERT DEBE FALLAR con un error de FOREIGN KEY
-- (el cliente 99999 no existe). Se ejecuta dentro de una
-- transacción que se deshace, por lo que no deja datos.
-- Esperado: Error 547 "The INSERT statement conflicted with
--           the FOREIGN KEY constraint ..."
-- ------------------------------------------------------------
BEGIN TRANSACTION;
    INSERT INTO dbo.ResenasWeb (IdCliente, IdProducto, IdFuente, Fecha, Comentario, Rating)
    VALUES (99999, 1, 1, '2025-01-01', N'Prueba de integridad', 3);
ROLLBACK TRANSACTION;
GO


-- ------------------------------------------------------------
-- CONSULTA 10: Vistas y procedimientos almacenados
-- Esperado: opiniones y satisfacción del producto 1
-- ------------------------------------------------------------
EXEC dbo.usp_SatisfaccionPorProducto @IdProducto = 1;
EXEC dbo.usp_OpinionesPorProducto @IdProducto = 1;
SELECT TOP 10 * FROM dbo.vw_SatisfaccionPorProducto ORDER BY TotalOpiniones DESC;
EXEC dbo.usp_ResumenCarga;
GO
