"""Limpieza y normalización de valores (funciones puras, fáciles de probar).

Cada función devuelve el valor ya limpio y con el tipo correcto, o lanza
ErrorValidacion con el motivo por el que el dato no sirve.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional

from etl.modelos import ErrorValidacion

_ESPACIOS = re.compile(r"\s+")
_INT_MAX = 2_147_483_647
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")

_TIPOS_FUENTE = {"csv": "CSV", "web": "Web", "red social": "Red Social", "redsocial": "Red Social"}
_PLATAFORMAS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "Twitter",
    "x": "Twitter",
}


def limpiar_texto(valor) -> str:
    """Quita caracteres de control e invisibles, unifica espacios y recorta."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFC", str(valor)).replace("�", "")
    texto = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in texto
    )
    return _ESPACIOS.sub(" ", texto).strip()


def texto_obligatorio(valor, campo: str, largo_max: int) -> str:
    texto = limpiar_texto(valor)
    if not texto:
        raise ErrorValidacion(f"{campo} es obligatorio")
    if len(texto) > largo_max:
        raise ErrorValidacion(f"{campo} excede {largo_max} caracteres")
    return texto


def normalizar_id(valor, prefijo: str, campo: str, obligatorio: bool) -> Optional[int]:
    """Convierte 'C007' o '7' en el entero 7. Vacío -> None si no es obligatorio."""
    texto = limpiar_texto(valor)
    if not texto:
        if obligatorio:
            raise ErrorValidacion(f"{campo} es obligatorio")
        return None
    coincide = re.fullmatch(rf"(?i)(?:{re.escape(prefijo)})?\s*0*(\d+)", texto)
    if not coincide:
        raise ErrorValidacion(f"{campo} con formato inválido")
    numero = int(coincide.group(1))
    if numero < 1 or numero > _INT_MAX:
        raise ErrorValidacion(f"{campo} fuera de rango")
    return numero


def normalizar_fecha(valor, campo: str = "Fecha") -> date:
    texto = limpiar_texto(valor)
    if not texto:
        raise ErrorValidacion(f"{campo} es obligatoria")
    texto = texto.split(" ")[0].split("T")[0]  # descarta la hora si viene
    fecha = None
    for formato in _FORMATOS_FECHA:
        try:
            fecha = datetime.strptime(texto, formato).date()
            break
        except ValueError:
            continue
    if fecha is None:
        raise ErrorValidacion(f"{campo} con formato inválido")
    if fecha > date.today():
        raise ErrorValidacion(f"{campo} es una fecha futura")
    if fecha.year < 1990:
        raise ErrorValidacion(f"{campo} fuera de rango")
    return fecha


def normalizar_puntaje(valor, campo: str) -> int:
    """Entero entre 1 y 5 (acepta '4' y '4.0')."""
    texto = limpiar_texto(valor)
    if not texto:
        raise ErrorValidacion(f"{campo} es obligatorio")
    coincide = re.fullmatch(r"([-+]?\d+)(?:[.,]0+)?", texto)
    if not coincide:
        raise ErrorValidacion(f"{campo} no es un número entero válido")
    numero = int(coincide.group(1))
    if not 1 <= numero <= 5:
        raise ErrorValidacion(f"{campo} fuera del rango 1 a 5")
    return numero


def normalizar_email(valor) -> str:
    email = limpiar_texto(valor).lower()
    if not email:
        raise ErrorValidacion("Email es obligatorio")
    if len(email) > 150:
        raise ErrorValidacion("Email excede 150 caracteres")
    if not _EMAIL.fullmatch(email):
        raise ErrorValidacion("Email con formato inválido")
    return email


def normalizar_codigo_fuente(valor) -> str:
    """'f1' o 'F001' -> 'F001'."""
    texto = limpiar_texto(valor)
    if not texto:
        raise ErrorValidacion("IdFuente es obligatorio")
    coincide = re.fullmatch(r"(?i)F\s*0*(\d+)", texto)
    if not coincide:
        raise ErrorValidacion("IdFuente con formato inválido")
    return f"F{int(coincide.group(1)):03d}"


def normalizar_tipo_fuente(valor) -> str:
    texto = limpiar_texto(valor).lower()
    if not texto:
        raise ErrorValidacion("TipoFuente es obligatorio")
    if texto not in _TIPOS_FUENTE:
        raise ErrorValidacion("TipoFuente no válido")
    return _TIPOS_FUENTE[texto]


def normalizar_plataforma(valor) -> str:
    texto = limpiar_texto(valor).lower()
    if not texto:
        raise ErrorValidacion("Plataforma es obligatoria")
    if texto not in _PLATAFORMAS:
        raise ErrorValidacion("Plataforma no válida")
    return _PLATAFORMAS[texto]
