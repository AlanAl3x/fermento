"""Pruebas de la comparación de versiones (`actualizaciones.py`).

Va aparte de `test_dinero.py` a propósito: aquel prueba las cuentas, que es
lo que decide si la caja cuadra. Esto es otra cosa, pero merece pruebas por
un motivo puntual -- **el error de comparar versiones como texto no se
manifiesta hasta la décima versión**. "1.10.0" < "1.9.0" alfabéticamente, así
que una app que compare mal funciona perfecto durante nueve versiones y
después deja de avisar para siempre, en silencio y en la máquina de otro.

No se prueba la red: no hay que depender de GitHub ni de que haya internet
para poder correr las pruebas. Lo que se verifica es la lógica pura, que es
donde puede haber un error que nadie note.

    python -m unittest test_actualizaciones
"""

import unittest

import actualizaciones as act


class Numeros(unittest.TestCase):
    def test_formato_normal(self):
        self.assertEqual(act.numeros("1.2.3"), (1, 2, 3))

    def test_con_prefijo_v(self):
        """Los tags de git se nombran "v1.0.0", así viene de la API."""
        self.assertEqual(act.numeros("v1.0.0"), (1, 0, 0))

    def test_incompleta_se_completa_con_ceros(self):
        self.assertEqual(act.numeros("v2"), (2, 0, 0))
        self.assertEqual(act.numeros("v2.5"), (2, 5, 0))

    def test_sufijo_ignorado(self):
        self.assertEqual(act.numeros("v1.2.3-beta"), (1, 2, 3))

    def test_espacios(self):
        self.assertEqual(act.numeros("  v1.2.3  "), (1, 2, 3))

    def test_basura_devuelve_none(self):
        """Ante la duda hay que callar, no avisar de una versión inventada."""
        for malo in ("", None, "estable", "vX.Y.Z", "latest"):
            self.assertIsNone(act.numeros(malo), f"deberia ser None: {malo!r}")


class EsMasNueva(unittest.TestCase):
    def test_parche_mayor(self):
        self.assertTrue(act.es_mas_nueva("v1.0.1", "1.0.0"))

    def test_menor_mayor(self):
        self.assertTrue(act.es_mas_nueva("v1.1.0", "1.0.9"))

    def test_igual_no_es_mas_nueva(self):
        self.assertFalse(act.es_mas_nueva("v1.0.0", "1.0.0"))

    def test_anterior_no_avisa(self):
        """Si la panadería tiene una versión MÁS nueva que la publicada
        (por ejemplo una de prueba), no hay que mandarla a "actualizar"
        hacia atrás."""
        self.assertFalse(act.es_mas_nueva("v1.0.0", "1.1.0"))

    def test_dos_digitos_no_se_comparan_como_texto(self):
        """El error clásico: "1.10.0" < "1.9.0" si se comparan como cadenas.
        Esta es la prueba por la que existe este archivo."""
        self.assertTrue(act.es_mas_nueva("v1.10.0", "1.9.0"))
        self.assertFalse(act.es_mas_nueva("v1.9.0", "1.10.0"))

    def test_version_2_contra_1_9(self):
        self.assertTrue(act.es_mas_nueva("v2.0.0", "1.9.9"))

    def test_etiqueta_ilegible_no_avisa(self):
        """Si GitHub devuelve algo que no se entiende, mejor no decir nada
        que mandar a alguien a reinstalar sin motivo."""
        self.assertFalse(act.es_mas_nueva("latest", "1.0.0"))
        self.assertFalse(act.es_mas_nueva(None, "1.0.0"))

    def test_usa_la_version_del_programa_por_defecto(self):
        """Sin segundo argumento compara contra version.VERSION."""
        from version import VERSION
        self.assertFalse(act.es_mas_nueva(VERSION))
        self.assertTrue(act.es_mas_nueva("v999.0.0"))


if __name__ == "__main__":
    unittest.main()
