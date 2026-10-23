"""Validación de cada entidad: formato, obligatorios, tipos y longitudes.

Cada función recibe una fila de staging (diccionario con texto crudo) y
devuelve un diccionario con los valores limpios y con su tipo final. Si
algo no cumple, lanza ErrorValidacion con el motivo.

La integridad referencial y los duplicados se validan en load.py, porque
necesitan comparar contra lo que ya está en la base de datos.
"""
from __future__ import annotations

from etl import transform as t


def validar_cliente(fila: dict) -> dict:
    return {
        "id": t.normalizar_id(fila["IdCliente"], "C", "IdCliente", obligatorio=True),
        "nombre": t.texto_obligatorio(fila["Nombre"], "Nombre", 100),
        "email": t.normalizar_email(fila["Email"]),
    }


def validar_producto(fila: dict) -> dict:
    return {
        "id": t.normalizar_id(fila["IdProducto"], "P", "IdProducto", obligatorio=True),
        "nombre": t.texto_obligatorio(fila["Nombre"], "Nombre", 100),
        "categoria": t.texto_obligatorio(fila["Categoria"], "Categoria", 50),
    }


def validar_fuente(fila: dict) -> dict:
    return {
        "codigo": t.normalizar_codigo_fuente(fila["IdFuente"]),
        "tipo": t.normalizar_tipo_fuente(fila["TipoFuente"]),
        "fecha_carga": t.normalizar_fecha(fila["FechaCarga"], "FechaCarga"),
    }


def validar_encuesta(fila: dict) -> dict:
    return {
        "id_cliente": t.normalizar_id(fila["IdCliente"], "C", "IdCliente", obligatorio=True),
        "id_producto": t.normalizar_id(fila["IdProducto"], "P", "IdProducto", obligatorio=True),
        "fecha": t.normalizar_fecha(fila["Fecha"]),
        "comentario": t.texto_obligatorio(fila["Comentario"], "Comentario", 500),
        "puntaje": t.normalizar_puntaje(fila["PuntajeSatisfaccion"], "PuntajeSatisfaccion"),
    }


def validar_resena(fila: dict) -> dict:
    return {
        # En reseñas web el cliente es opcional
        "id_cliente": t.normalizar_id(fila["IdCliente"], "C", "IdCliente", obligatorio=False),
        "id_producto": t.normalizar_id(fila["IdProducto"], "P", "IdProducto", obligatorio=True),
        "fecha": t.normalizar_fecha(fila["Fecha"]),
        "comentario": t.texto_obligatorio(fila["Comentario"], "Comentario", 500),
        "rating": t.normalizar_puntaje(fila["Rating"], "Rating"),
    }


def validar_comentario_social(fila: dict) -> dict:
    return {
        # En comentarios sociales hay comentarios anónimos (sin cliente)
        "id_cliente": t.normalizar_id(fila["IdCliente"], "C", "IdCliente", obligatorio=False),
        "id_producto": t.normalizar_id(fila["IdProducto"], "P", "IdProducto", obligatorio=True),
        "plataforma": t.normalizar_plataforma(fila["Fuente"]),
        "fecha": t.normalizar_fecha(fila["Fecha"]),
        "comentario": t.texto_obligatorio(fila["Comentario"], "Comentario", 500),
    }
