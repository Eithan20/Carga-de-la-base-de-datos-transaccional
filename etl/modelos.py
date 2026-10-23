"""Excepciones y estructuras de datos compartidas por todo el ETL."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


# ----------------------------------------------------------------------
# Excepciones
# ----------------------------------------------------------------------
class ErrorETL(Exception):
    """Error que detiene la ejecución del proceso."""


class ErrorConexion(ErrorETL):
    """No se pudo conectar con SQL Server."""


class EstructuraInvalidaError(ErrorETL):
    """Un archivo CSV no tiene la estructura esperada."""


class ErrorValidacion(Exception):
    """Un registro no es válido. El mensaje es el motivo del rechazo."""


# ----------------------------------------------------------------------
# Resultados del proceso
# ----------------------------------------------------------------------
@dataclass
class Rechazo:
    """Un registro que no se pudo cargar, con su motivo."""

    entidad: str
    archivo: str
    fila: int
    id_origen: str
    motivo: str
    dato_original: str


@dataclass
class ResultadoEntidad:
    """Contadores de una entidad (Clientes, Productos, etc.)."""

    entidad: str
    leidos: int = 0          # filas de datos leídas de los CSV
    en_staging: int = 0      # filas copiadas a la capa 1
    insertados: int = 0      # filas cargadas a la capa 2
    motivos: Counter = field(default_factory=Counter)

    @property
    def rechazados(self) -> int:
        return sum(self.motivos.values())

    def rechazar(self, motivo: str) -> None:
        self.motivos[motivo] += 1
