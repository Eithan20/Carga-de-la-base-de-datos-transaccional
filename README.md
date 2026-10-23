# Proceso ETL: Sistema de Análisis de Opiniones de Clientes

Carga de la base de datos transaccional. Un proceso en Python lee 6 archivos CSV,
los valida y limpia, y los inserta en SQL Server respetando las claves primarias
y foráneas. Al terminar muestra cuántos registros se procesaron, insertaron y rechazaron.

- Autor: Eithan Samir Pérez Valera
- Materia: Electiva 1
- Docente: Francis Ramírez

## Cómo funciona

El proceso trabaja en dos capas:

```
CSV  ──►  Capa 1: staging (stg)  ──►  Capa 2: transaccional (dbo)
          copia cruda de los CSV      datos validados, con PK y FK
                                      + rechazos con su motivo
```

Lo que no pasa las validaciones (campos vacíos, formatos incorrectos, duplicados,
referencias a clientes o productos que no existen) se guarda en `stg.RegistrosRechazados`
con el motivo. Cada ejecución limpia las dos capas y recarga, así que repetirla no duplica datos.

## Requisitos

- Python 3
- SQL Server y SSMS
- ODBC Driver 17 (o 18) for SQL Server
- Librería pyodbc (`pip install -r requirements.txt`)

## Cómo ejecutarlo

1. Abrir `sql/script_base_datos.sql` en SSMS y ejecutarlo completo (F5).
2. Instalar la dependencia: `pip install -r requirements.txt`
3. Abrir `config.py` y escribir en las comillas vacías de `DB_SERVER` el nombre de su
   servidor de SQL Server (el que aparece en SSMS al conectarse).
4. Ejecutar: `python main.py`
5. En SSMS, correr una por una las consultas de `sql/consultas_validacion.sql`.

## Pruebas automáticas

Las pruebas validan las reglas del ETL sin usar SQL Server (usan una base SQLite en memoria):

```
python -m unittest discover -s tests -v
```

Debe terminar con `Ran 30 tests` y `OK`.

## Resultado esperado con los CSV incluidos

| Entidad | Procesados | Insertados | Rechazados |
|---|---|---|---|
| Clientes | 500 | 500 | 0 |
| Productos | 200 | 200 | 0 |
| FuenteDatos | 100 | 100 | 0 |
| Encuestas | 500 | 6 | 494 |
| ResenasWeb | 200 | 200 | 0 |
| ComentariosSociales | 200 | 200 | 0 |
| **Total** | **1700** | **1206** | **494** |

Las 494 encuestas rechazadas referencian clientes o productos que no existen en los
catálogos (clientes del 1 al 500 y productos del 1 al 200), por eso no pasan la integridad referencial.

## Estructura del proyecto

```
ETL_Opiniones/
├── main.py                punto de entrada
├── config.py              servidor y base de datos
├── requirements.txt       dependencias
├── data/                  los 6 CSV
├── sql/                   script de la base de datos y consultas de validación
├── etl/                   módulos del proceso (extracción, validación, carga, resumen)
├── tests/                 pruebas automáticas
├── logs/                  registros que genera el programa (no se suben)
└── evidencias/            log final, capturas e informe
```
