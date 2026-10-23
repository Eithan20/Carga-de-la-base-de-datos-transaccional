"""Pruebas automáticas de las validaciones del ETL.

Usan una base SQLite en memoria (etl/modo_prueba.py), así que no tocan SQL Server.

Ejecutar desde la carpeta del proyecto:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from etl import extract, load, resumen, transform as t  # noqa: E402
from etl.modelos import (  # noqa: E402
    ErrorValidacion, EstructuraInvalidaError, ResultadoEntidad,
)
from etl.modo_prueba import crear_base_prueba  # noqa: E402

ENCABEZADOS = {
    "clients.csv": "IdCliente,Nombre,Email",
    "products.csv": "IdProducto,Nombre,Categoría",
    "fuente_datos.csv": "IdFuente,TipoFuente,FechaCarga",
    "surveys_part1.csv": "IdOpinion,IdCliente,IdProducto,Fecha,Comentario,Clasificación,PuntajeSatisfacción,Fuente",
    "web_reviews.csv": "IdReview,IdCliente,IdProducto,Fecha,Comentario,Rating",
    "social_comments.csv": "IdComment,IdCliente,IdProducto,Fuente,Fecha,Comentario",
}


def escribir_csv(carpeta: Path, nombre: str, filas: list[str]) -> None:
    (carpeta / nombre).write_text(
        "\n".join([ENCABEZADOS[nombre], *filas]) + "\n", encoding="utf-8"
    )


def correr_etl(carpeta: Path, db=None):
    """Ejecuta las dos capas igual que main.py y devuelve (db, resultados, rechazos)."""
    db = db or crear_base_prueba()
    resultados = {e.nombre: ResultadoEntidad(e.nombre) for e in extract.ENTIDADES}
    rechazos: list = []
    extract.extraer_a_staging(db, carpeta, resultados, rechazos)
    db.commit()
    load.cargar_transaccional(db, resultados, rechazos)
    load.guardar_rechazos(db, rechazos)
    db.commit()
    return db, resultados, rechazos


class TestTransformaciones(unittest.TestCase):
    def test_id_con_prefijo_y_sin_prefijo(self):
        self.assertEqual(t.normalizar_id("C007", "C", "IdCliente", True), 7)
        self.assertEqual(t.normalizar_id("7", "C", "IdCliente", True), 7)
        self.assertEqual(t.normalizar_id(" p016 ", "P", "IdProducto", True), 16)

    def test_id_vacio_segun_sea_obligatorio(self):
        self.assertIsNone(t.normalizar_id("", "C", "IdCliente", False))
        with self.assertRaises(ErrorValidacion):
            t.normalizar_id("", "C", "IdCliente", True)

    def test_id_con_formato_invalido(self):
        for malo in ("abc", "C-7", "0", "-3"):
            with self.assertRaises(ErrorValidacion, msg=malo):
                t.normalizar_id(malo, "C", "IdCliente", True)

    def test_email_se_normaliza_y_se_valida(self):
        self.assertEqual(t.normalizar_email("  Ana@Mail.COM "), "ana@mail.com")
        for malo in ("", "sin-arroba", "a@b", "a b@c.com"):
            with self.assertRaises(ErrorValidacion, msg=malo):
                t.normalizar_email(malo)

    def test_fechas_en_varios_formatos(self):
        esperada = date(2025, 4, 10)
        for texto in ("2025-04-10", "10/04/2025", "2025/04/10", "10-04-2025", "2025-04-10 08:30:00"):
            self.assertEqual(t.normalizar_fecha(texto), esperada, texto)

    def test_fechas_invalidas(self):
        futura = (date.today() + timedelta(days=5)).isoformat()
        for malo in ("", "no es fecha", "2025-13-45", futura, "1980-01-01"):
            with self.assertRaises(ErrorValidacion, msg=malo):
                t.normalizar_fecha(malo)

    def test_puntaje_entre_1_y_5(self):
        self.assertEqual(t.normalizar_puntaje("4", "Puntaje"), 4)
        self.assertEqual(t.normalizar_puntaje("4.0", "Puntaje"), 4)
        for malo in ("0", "6", "-1", "3.5", "abc", ""):
            with self.assertRaises(ErrorValidacion, msg=malo):
                t.normalizar_puntaje(malo, "Puntaje")

    def test_catalogos_de_fuente_y_plataforma(self):
        self.assertEqual(t.normalizar_codigo_fuente("f1"), "F001")
        self.assertEqual(t.normalizar_tipo_fuente("red social"), "Red Social")
        self.assertEqual(t.normalizar_plataforma("X"), "Twitter")
        with self.assertRaises(ErrorValidacion):
            t.normalizar_tipo_fuente("Satélite")
        with self.assertRaises(ErrorValidacion):
            t.normalizar_plataforma("TikTok")

    def test_texto_obligatorio_y_longitud(self):
        self.assertEqual(t.texto_obligatorio("  hola   mundo ", "Campo", 50), "hola mundo")
        with self.assertRaises(ErrorValidacion):
            t.texto_obligatorio("   ", "Campo", 50)
        with self.assertRaises(ErrorValidacion):
            t.texto_obligatorio("x" * 51, "Campo", 50)


class TestCargaConDatosSucios(unittest.TestCase):
    """Un lote pequeño con errores a propósito: cada error debe rechazarse con su motivo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._tmp.name)
        futura = (date.today() + timedelta(days=30)).isoformat()

        escribir_csv(self.carpeta, "fuente_datos.csv", [
            "F001,Web,2025-04-10",
            "F002,CSV,2025-01-01",
            "F003,Red Social,2025-03-01",
            "F001,Web,2025-05-01",          # código duplicado
            "F004,Satélite,2025-05-01",     # tipo no permitido
        ])
        escribir_csv(self.carpeta, "clients.csv", [
            "1,Ana,ana@mail.com",
            "2,Luis,luis@mail.com",
            "3,Copia,ANA@mail.com",         # correo duplicado
            "C002,Otro,otro@mail.com",      # ID duplicado
            "4,,sinnombre@mail.com",        # nombre vacío
            "5,Mala,correo-malo",           # correo inválido
        ])
        escribir_csv(self.carpeta, "products.csv", [
            "1,Producto_1,Hogar",
            "2,Producto_2,Juguetes",
            "3,Producto_3,",                # categoría vacía
        ])
        escribir_csv(self.carpeta, "surveys_part1.csv", [
            "1,1,1,2025-06-01,Muy bueno,Positiva,5,EncuestaInterna",
            "2,99,1,2025-06-02,Cliente inexistente,Neutra,3,EncuestaInterna",
            "3,1,99,2025-06-03,Producto inexistente,Neutra,3,EncuestaInterna",
            "4,99,99,2025-06-04,Ambos inexistentes,Neutra,3,EncuestaInterna",
            "5,2,2,2025-06-05,Puntaje fuera de rango,Positiva,9,EncuestaInterna",
            f"6,2,2,{futura},Fecha futura,Neutra,3,EncuestaInterna",
            "7,2,1,2025-06-07,Normal,Neutra,3,EncuestaInterna",
            "7,2,2,2025-06-08,Mismo IdOpinion,Neutra,3,EncuestaInterna",   # ID repetido
            "8,2,1,2025-06-07,normal,Neutra,3,EncuestaInterna",           # mismo contenido
        ])
        escribir_csv(self.carpeta, "web_reviews.csv", [
            "W1,C001,P001,2025-06-01,Excelente,4",
            "W2,,P002,2025-06-02,Reseña anónima,3",
            "W3,C001,P001,2025-06-03,Rating inválido,0",
        ])
        escribir_csv(self.carpeta, "social_comments.csv", [
            "T1,,P001,Instagram,2025-06-01,Comentario anónimo",
            "T2,C002,P002,facebook,2025-06-02,Comentario con cliente",
            "T3,C001,P001,TikTok,2025-06-03,Plataforma inválida",
        ])
        self.db, self.res, self.rechazos = correr_etl(self.carpeta)

    def tearDown(self):
        self.db.cerrar()
        self._tmp.cleanup()

    def contar(self, tabla: str) -> int:
        return self.db.escalar(f"SELECT COUNT(*) FROM {tabla}")

    def test_fuentes_duplicadas_y_tipo_invalido(self):
        r = self.res["FuenteDatos"]
        self.assertEqual((r.leidos, r.insertados, r.rechazados), (5, 3, 2))
        self.assertEqual(self.contar("dbo.FuenteDatos"), 3)

    def test_clientes_rechazados_por_correo_id_nombre_y_formato(self):
        r = self.res["Clientes"]
        self.assertEqual((r.leidos, r.insertados, r.rechazados), (6, 2, 4))
        motivos = " | ".join(r.motivos)
        for esperado in ("Email duplicado", "IdCliente duplicado", "Nombre es obligatorio",
                         "Email con formato inválido"):
            self.assertIn(esperado, motivos)

    def test_el_id_con_prefijo_se_guarda_como_numero(self):
        ids = [f[0] for f in self.db.consultar("SELECT IdCliente FROM dbo.Clientes ORDER BY 1")]
        self.assertEqual(ids, [1, 2])

    def test_producto_con_categoria_vacia(self):
        r = self.res["Productos"]
        self.assertEqual((r.insertados, r.rechazados), (2, 1))

    def test_encuestas_integridad_referencial_y_duplicados(self):
        r = self.res["Encuestas"]
        self.assertEqual((r.leidos, r.insertados, r.rechazados), (9, 2, 7))
        motivos = " | ".join(r.motivos)
        self.assertIn("el cliente no existe", motivos)
        self.assertIn("el producto no existe", motivos)
        self.assertIn("el cliente y el producto no existen", motivos)
        self.assertIn("fuera del rango 1 a 5", motivos)
        self.assertIn("fecha futura", motivos)
        self.assertIn("IdOpinion duplicado", motivos)
        self.assertIn("Registro duplicado", motivos)

    def test_resenas_con_cliente_opcional(self):
        r = self.res["ResenasWeb"]
        self.assertEqual((r.insertados, r.rechazados), (2, 1))
        anonimas = self.db.escalar("SELECT COUNT(*) FROM dbo.ResenasWeb WHERE IdCliente IS NULL")
        self.assertEqual(anonimas, 1)

    def test_comentarios_sociales_anonimos_y_plataforma(self):
        r = self.res["ComentariosSociales"]
        self.assertEqual((r.insertados, r.rechazados), (2, 1))
        plataformas = {f[0] for f in self.db.consultar("SELECT Plataforma FROM dbo.ComentariosSociales")}
        self.assertEqual(plataformas, {"Instagram", "Facebook"})

    def test_procesados_igual_a_insertados_mas_rechazados(self):
        for r in self.res.values():
            self.assertEqual(r.leidos, r.insertados + r.rechazados, r.entidad)

    def test_staging_guarda_todo_lo_leido(self):
        for entidad, r in self.res.items():
            self.assertEqual(self.contar(f"stg.{entidad}"), r.leidos, entidad)

    def test_los_rechazos_quedan_registrados_con_su_motivo(self):
        total_rechazados = sum(r.rechazados for r in self.res.values())
        self.assertEqual(self.contar("stg.RegistrosRechazados"), total_rechazados)
        sin_motivo = self.db.escalar(
            "SELECT COUNT(*) FROM stg.RegistrosRechazados WHERE Motivo IS NULL OR Motivo = ''"
        )
        self.assertEqual(sin_motivo, 0)

    def test_no_quedan_registros_huerfanos(self):
        verificacion = resumen.verificar_base(self.db, self.res)
        self.assertFalse(verificacion["diferencias"])
        self.assertFalse(any(verificacion["huerfanos"].values()))

    def test_repetir_el_etl_no_duplica_datos(self):
        antes = {e: self.contar(f"dbo.{e}") for e in self.res}
        _, res2, _ = correr_etl(self.carpeta, db=self.db)
        despues = {e: self.contar(f"dbo.{e}") for e in res2}
        self.assertEqual(antes, despues)
        self.assertEqual(self.contar("stg.Clientes"), 6)


class TestEstructuraDeArchivos(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._tmp.name)
        escribir_csv(self.carpeta, "fuente_datos.csv", ["F001,Web,2025-04-10", "F002,CSV,2025-01-01",
                                                        "F003,Red Social,2025-03-01"])
        escribir_csv(self.carpeta, "clients.csv", ["1,Ana,ana@mail.com"])
        escribir_csv(self.carpeta, "products.csv", ["1,Producto_1,Hogar"])
        escribir_csv(self.carpeta, "surveys_part1.csv", ["1,1,1,2025-06-01,Bien,Positiva,5,EncuestaInterna"])
        escribir_csv(self.carpeta, "web_reviews.csv", ["W1,C001,P001,2025-06-01,Bien,4"])
        escribir_csv(self.carpeta, "social_comments.csv", ["T1,,P001,Instagram,2025-06-01,Bien"])

    def tearDown(self):
        self._tmp.cleanup()

    def test_con_archivos_correctos_todo_se_carga(self):
        db, res, _ = correr_etl(self.carpeta)
        self.assertEqual(sum(r.insertados for r in res.values()), 8)  # 3 fuentes + 5 filas
        self.assertEqual(sum(r.rechazados for r in res.values()), 0)

    def test_archivo_faltante(self):
        (self.carpeta / "clients.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            correr_etl(self.carpeta)

    def test_archivo_vacio(self):
        (self.carpeta / "products.csv").write_text("", encoding="utf-8")
        with self.assertRaises(EstructuraInvalidaError):
            correr_etl(self.carpeta)

    def test_columna_faltante_en_el_encabezado(self):
        (self.carpeta / "clients.csv").write_text("IdCliente,Nombre\n1,Ana\n", encoding="utf-8")
        with self.assertRaises(EstructuraInvalidaError) as ctx:
            correr_etl(self.carpeta)
        self.assertIn("Email", str(ctx.exception))

    def test_fila_con_columnas_de_mas_se_rechaza(self):
        escribir_csv(self.carpeta, "clients.csv", ["1,Ana,ana@mail.com", "2,Luis,luis@mail.com,sobra"])
        _, res, _ = correr_etl(self.carpeta)
        self.assertEqual((res["Clientes"].insertados, res["Clientes"].rechazados), (1, 1))
        self.assertIn("Número de columnas incorrecto", res["Clientes"].motivos)


class TestRestriccionesDeLaBase(unittest.TestCase):
    """Aunque el ETL falle, la propia base debe impedir datos inválidos."""

    def setUp(self):
        self.db = crear_base_prueba()
        self.db.ejecutar("INSERT INTO dbo.Clientes VALUES (1, 'Ana', 'ana@mail.com')")
        self.db.ejecutar("INSERT INTO dbo.Productos VALUES (1, 'P1', 'Hogar')")
        self.db.ejecutar("INSERT INTO dbo.FuenteDatos VALUES (1, 'F001', 'CSV', '2025-01-01')")

    def tearDown(self):
        self.db.cerrar()

    def test_la_clave_foranea_rechaza_un_cliente_inexistente(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.ejecutar(
                "INSERT INTO dbo.Encuestas (IdCliente, IdProducto, IdFuente, Fecha, Comentario, "
                "PuntajeSatisfaccion) VALUES (99999, 1, 1, '2025-01-01', 'x', 3)"
            )

    def test_check_rechaza_un_puntaje_fuera_de_rango(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.ejecutar(
                "INSERT INTO dbo.Encuestas (IdCliente, IdProducto, IdFuente, Fecha, Comentario, "
                "PuntajeSatisfaccion) VALUES (1, 1, 1, '2025-01-01', 'x', 9)"
            )

    def test_unique_rechaza_un_correo_repetido(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.ejecutar("INSERT INTO dbo.Clientes VALUES (2, 'Otra', 'ana@mail.com')")


@unittest.skipUnless((RAIZ / "data" / "clients.csv").exists(), "no está la carpeta data/")
class TestConLosCsvReales(unittest.TestCase):
    def test_resultado_con_los_6_csv_del_proyecto(self):
        db, res, _ = correr_etl(RAIZ / "data")
        try:
            insertados = {n: r.insertados for n, r in res.items()}
            self.assertEqual(insertados, {
                "Clientes": 500, "Productos": 200, "FuenteDatos": 100,
                "Encuestas": 6, "ResenasWeb": 200, "ComentariosSociales": 200,
            })
            self.assertEqual(sum(r.leidos for r in res.values()), 1700)
            self.assertEqual(sum(r.rechazados for r in res.values()), 494)
            verificacion = resumen.verificar_base(db, res)
            self.assertFalse(any(verificacion["huerfanos"].values()))
        finally:
            db.cerrar()


if __name__ == "__main__":
    unittest.main(verbosity=2)
