"""Punto de entrada del proceso ETL (2 capas).

    Capa 1: CSV  ->  staging (esquema stg)
    Capa 2: staging  ->  base de datos transaccional (esquema dbo)

Uso:
    python main.py                      carga a SQL Server (ver config.py)
    python main.py --data-dir RUTA      usa otra carpeta de CSV
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import config
from etl import extract, load, resumen
from etl.database import Database, conectar
from etl.modelos import (
    ErrorConexion, ErrorETL, EstructuraInvalidaError, Rechazo, ResultadoEntidad,
)

log = logging.getLogger("etl")


def configurar_logging() -> Path:
    config.LOG_DIR.mkdir(exist_ok=True)
    archivo = config.LOG_DIR / f"etl_{datetime.now():%Y%m%d_%H%M%S}.log"
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG)
    consola = logging.StreamHandler(sys.stdout)
    consola.setLevel(logging.INFO)
    consola.setFormatter(formato)
    fichero = logging.FileHandler(archivo, encoding="utf-8")
    fichero.setFormatter(formato)
    raiz.addHandler(consola)
    raiz.addHandler(fichero)
    return archivo


def ejecutar(db: Database, carpeta: Path) -> int:
    inicio = datetime.now()
    resultados = {e.nombre: ResultadoEntidad(e.nombre) for e in extract.ENTIDADES}
    rechazos: list[Rechazo] = []

    # ---- CAPA 1: CSV -> staging -------------------------------------
    log.info("=== CAPA 1: extracción de los CSV a staging ===")
    try:
        extract.extraer_a_staging(db, carpeta, resultados, rechazos)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # ---- CAPA 2: staging -> transaccional ---------------------------
    log.info("=== CAPA 2: validación y carga a la base transaccional ===")
    try:
        load.cargar_transaccional(db, resultados, rechazos)
        load.guardar_rechazos(db, rechazos)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ErrorETL(
            f"La carga a la base transaccional falló y se deshicieron los cambios: {exc}"
        ) from exc

    verificacion = resumen.verificar_base(db, resultados)
    resumen.imprimir_resumen(resultados, rechazos, verificacion, inicio, datetime.now())

    consistente = (
        all(r.leidos == r.insertados + r.rechazados for r in resultados.values())
        and not verificacion["diferencias"]
        and not any(verificacion["huerfanos"].values())
    )
    return 0 if consistente else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL de opiniones de clientes (2 capas)")
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR,
                        help="carpeta con los archivos CSV")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    archivo_log = configurar_logging()
    log.info("Proceso ETL iniciado. Registro en %s", archivo_log)

    db = None
    try:
        db = conectar()
        return ejecutar(db, args.data_dir)
    except ErrorConexion as exc:
        log.error("Error de conexión: %s", exc)
    except EstructuraInvalidaError as exc:
        log.error("Estructura de datos inválida: %s", exc)
    except FileNotFoundError as exc:
        log.error("Archivo no encontrado: %s", exc)
    except ErrorETL as exc:
        log.error("%s", exc)
    except Exception:
        log.exception("Error inesperado")
    finally:
        if db is not None:
            db.cerrar()
    return 2


if __name__ == "__main__":
    sys.exit(main())