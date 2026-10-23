"""Configuración del proceso ETL.

Los valores se pueden cambiar aquí o con variables de entorno, sin tocar
el código. Las credenciales nunca se escriben en el código: si ETL_USER
está vacío se usa la autenticación de Windows (la que usa SSMS).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Carpetas
DATA_DIR = Path(os.getenv("ETL_DATA_DIR", BASE_DIR / "data"))
LOG_DIR = BASE_DIR / "logs"

# Conexión a SQL Server
DB_SERVER = os.getenv("ETL_SERVER", "") # En las comillas vacías, escribir el nombre de su servidor para que pueda funcionar sin problemas
DB_NAME = os.getenv("ETL_DATABASE", "AnalisisOpinionesTransaccional")
DB_USER = os.getenv("ETL_USER", "")          # vacío = autenticación de Windows
DB_PASSWORD = os.getenv("ETL_PASSWORD", "")
DB_DRIVER = os.getenv("ETL_DRIVER", "")      # vacío = detecta el más reciente
