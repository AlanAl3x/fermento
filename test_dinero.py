"""Pruebas de la matemática de la plata.

Qué cubre: las cuentas de las que depende que la caja cuadre -- el total de
una venta contra sus líneas, el de un corte contra las ventas que incluye,
que anular devuelva EXACTAMENTE el stock que se descontó y ni una unidad
más, y que lo que se congela en la venta (precio, costo, precio de lista)
no se mueva después. No cubre la interfaz: acá no se abre ninguna ventana.

Por qué existe: el resto de la app se prueba usándola, pero un error de un
peso en un corte no se ve mirando la pantalla -- se descubre meses después,
cuando ya no hay con qué reconstruir qué pasó. Estas son las cuentas donde
un error es caro y silencioso a la vez.

Correr:  python -m unittest test_dinero -v     (desde la carpeta del proyecto)

Sin dependencias nuevas: `unittest` viene con Python. Se prefirió a pytest
por lo mismo que se descartó `tkcalendar` -- no sumar nada al proyecto por
algo que la biblioteca estándar ya resuelve.

**Estas pruebas NUNCA tocan `panaderia.db`**: cada test corre contra una
base temporal y vacía que se borra al terminar (ver `_BaseDinero`).
"""

import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

# Para poder correr el archivo directamente desde otra carpeta.
sys.path.insert(0, str(Path(__file__).parent))

import database as db
import registro


class _BaseDinero(unittest.TestCase):
    """Base con una base de datos temporal y vacía por cada test.

    Lo más importante del archivo: `db.DB_PATH` se apunta a un archivo
    descartable ANTES de tocar nada. `database.py` lee esa variable en cada
    `_conn()`, así que alcanza con pisarla -- sin esto, las pruebas
    escribirían ventas y cortes inventados en la base real.

    Se hace lo mismo con `registro.LOG_PATH` para que un error provocado a
    propósito acá no ensucie el log de la app.
    """

    def setUp(self):
        self._carpeta = Path(tempfile.mkdtemp(prefix="fermento_test_"))
        self._db_original = db.DB_PATH
        self._log_original = registro.LOG_PATH
        db.DB_PATH = self._carpeta / "prueba.db"
        registro.LOG_PATH = self._carpeta / "prueba.log"
        # `_FK_ACTIVAS` es global del módulo y se quedaría pegado de la prueba
        # anterior: sin esto, la que verifica el fallo de la migración vería
        # las claves foráneas encendidas por otra prueba y daría un falso OK.
        db._FK_ACTIVAS = False
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._db_original
        registro.LOG_PATH = self._log_original
        db._FK_ACTIVAS = False
        # El log deja el archivo abierto, y en Windows un archivo abierto no
        # se puede borrar: sin cerrarlo, la carpeta temporal quedaría colgada.
        for h in list(registro._log.handlers):
            h.close()
            registro._log.removeHandler(h)
        registro._iniciado = False
        shutil.rmtree(self._carpeta, ignore_errors=True)

    # ── Atajos para armar el escenario ───────────────────────────────────────

    def _producto(self, nombre="Pan", precio=100.0, stock=10, costo=40.0):
        """Crea un producto con su primera tanda (horneada hoy) y devuelve su id."""
        db.add_producto(nombre, precio, stock, costo)
        return next(p["id"] for p in db.get_productos() if p["nombre"] == nombre)

    def _lote(self, producto_id, indice=0):
        """id del lote `indice` del producto (van del más viejo al más nuevo)."""
        return db.get_lotes(producto_id)[indice]["id"]

    def _item(self, producto_id, lote_id, cantidad, precio):
        """Una línea de carrito como la arma Nueva Venta."""
        return {"producto_id": producto_id, "lote_id": lote_id, "cantidad": cantidad,
                "precio_unitario": precio, "subtotal": precio * cantidad}

    def _consultar(self, sql, params=()):
        """SQL directo, para mirar lo que quedó guardado sin pasar por las
        mismas funciones que se están probando (si `hacer_corte()` calculara
        mal, `get_cortes()` devolvería el mismo número mal y el test pasaría)."""
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            return c.execute(sql, params).fetchall()

    def _un_valor(self, sql, params=()):
        return self._consultar(sql, params)[0][0]


class Ventas(_BaseDinero):

    def test_el_total_de_la_venta_es_la_suma_de_sus_lineas(self):
        p1 = self._producto("Pan", 25.50)
        p2 = self._producto("Factura", 33.33)
        venta_id = db.registrar_venta([
            self._item(p1, self._lote(p1), 3, 25.50),
            self._item(p2, self._lote(p2), 2, 33.33),
        ])
        total = self._un_valor("SELECT total FROM ventas WHERE id=?", (venta_id,))
        suma = self._un_valor(
            "SELECT SUM(subtotal) FROM detalle_venta WHERE venta_id=?", (venta_id,))
        # places=2 y no igualdad exacta: los montos son REAL (float) en SQLite,
        # así que se comparan al centavo, que es la unidad que existe de verdad.
        self.assertAlmostEqual(total, suma, places=2)
        self.assertAlmostEqual(total, 3 * 25.50 + 2 * 33.33, places=2)

    def test_la_venta_descuenta_del_lote_que_se_eligio(self):
        """Vender de la tanda vieja no puede tocar la nueva: cada una tiene su
        propio stock y su propio precio (ver el modelo de lotes)."""
        p = self._producto("Pan", 100.0, stock=10)  # tanda de hoy
        db.agregar_lote(p, 8, (date.today() - timedelta(days=2)).isoformat())
        viejo, nuevo = db.get_lotes(p)  # get_lotes ordena por fecha_horneado
        db.registrar_venta([self._item(p, viejo["id"], 5, 60.0)])
        self.assertEqual(db.get_lote(viejo["id"])["stock"], 3)
        self.assertEqual(db.get_lote(nuevo["id"])["stock"], 10)

    def test_hornear_de_nuevo_el_mismo_dia_suma_a_la_tanda_existente(self):
        """`agregar_lote()` fusiona por fecha en vez de crear una tanda
        duplicada. La cuenta tiene que ser una suma exacta: si se duplicara o
        se pisara, el mostrador vería un stock que no existe."""
        p = self._producto("Pan", 100.0, stock=10)
        db.agregar_lote(p, 6)  # segunda horneada del mismo día
        lotes = db.get_lotes(p)
        self.assertEqual(len(lotes), 1)
        self.assertEqual(lotes[0]["stock"], 16)

    def test_vender_mas_de_lo_que_hay_no_deja_nada_a_medias(self):
        """El caso feo: la primera línea entra y la segunda no alcanza. Si el
        rollback fallara quedaría una venta cobrada de más y stock descontado
        de un producto que nunca se entregó."""
        p1 = self._producto("Pan", 100.0, stock=10)
        p2 = self._producto("Factura", 50.0, stock=2)
        with self.assertRaises(db.DBError):
            db.registrar_venta([
                self._item(p1, self._lote(p1), 4, 100.0),  # entra
                self._item(p2, self._lote(p2), 5, 50.0),   # no alcanza
            ])
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM ventas"), 0)
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM detalle_venta"), 0)
        self.assertEqual(db.get_lote(self._lote(p1))["stock"], 10)
        self.assertEqual(db.get_lote(self._lote(p2))["stock"], 2)


class Anulacion(_BaseDinero):

    def _venta_de_prueba(self, cantidad=4):
        p = self._producto("Pan", 100.0, stock=10)
        lote = self._lote(p)
        venta_id = db.registrar_venta([self._item(p, lote, cantidad, 100.0)])
        return venta_id, lote

    def test_anular_devuelve_exactamente_lo_que_se_habia_descontado(self):
        venta_id, lote = self._venta_de_prueba(4)
        self.assertEqual(db.get_lote(lote)["stock"], 6)
        db.anular_venta(venta_id, "el cliente se arrepintió")
        self.assertEqual(db.get_lote(lote)["stock"], 10)

    def test_anular_dos_veces_no_devuelve_el_stock_dos_veces(self):
        """Sin la guarda de `anulada`, el segundo intento inventaría
        mercadería: el stock quedaría en 14 de un lote que arrancó en 10."""
        venta_id, lote = self._venta_de_prueba(4)
        db.anular_venta(venta_id, "primera")
        with self.assertRaises(db.DBError):
            db.anular_venta(venta_id, "segunda")
        self.assertEqual(db.get_lote(lote)["stock"], 10)

    def test_no_se_puede_anular_una_venta_ya_incluida_en_un_corte(self):
        """Y el rechazo no puede dejar efectos a medias: si devolviera el
        stock antes de fallar, el corte quedaría cuadrando contra mercadería
        que volvió al estante."""
        venta_id, lote = self._venta_de_prueba(4)
        db.hacer_corte()
        with self.assertRaises(db.DBError):
            db.anular_venta(venta_id, "tarde")
        self.assertEqual(db.get_lote(lote)["stock"], 6)
        self.assertEqual(
            self._un_valor("SELECT anulada FROM ventas WHERE id=?", (venta_id,)), 0)

    def test_anular_devuelve_al_lote_correcto_y_no_toca_los_otros(self):
        """Con dos tandas conviviendo, la devolución tiene que ir a la que
        salió la venta -- si fuera a la otra, el total del producto cuadraría
        igual pero la antigüedad (y con ella el precio) quedaría mal."""
        p = self._producto("Pan", 100.0, stock=10)  # tanda de hoy
        db.agregar_lote(p, 8, (date.today() - timedelta(days=2)).isoformat())
        viejo, nuevo = db.get_lotes(p)
        venta_id = db.registrar_venta([self._item(p, viejo["id"], 5, 60.0)])
        db.anular_venta(venta_id, "se arrepintió")
        self.assertEqual(db.get_lote(viejo["id"])["stock"], 8)
        self.assertEqual(db.get_lote(nuevo["id"])["stock"], 10)

    def test_una_venta_anulada_no_se_borra(self):
        """Anular es baja lógica: la fila queda, con motivo y fecha."""
        venta_id, _ = self._venta_de_prueba(2)
        db.anular_venta(venta_id, "producto en mal estado")
        fila = self._consultar(
            "SELECT anulada, motivo_anulacion, fecha_anulacion FROM ventas WHERE id=?",
            (venta_id,))[0]
        self.assertEqual(fila[0], 1)
        self.assertEqual(fila[1], "producto en mal estado")
        self.assertIsNotNone(fila[2])


class Cortes(_BaseDinero):

    def test_el_corte_suma_exactamente_las_ventas_pendientes(self):
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 3, 100.0)])
        db.registrar_venta([self._item(p, lote, 2, 80.0)])
        corte_id = db.hacer_corte()
        total, cantidad = self._consultar(
            "SELECT total_ventas, cantidad_ventas FROM cortes WHERE id=?", (corte_id,))[0]
        self.assertAlmostEqual(total, 300.0 + 160.0, places=2)
        self.assertEqual(cantidad, 2)

    def test_el_corte_ignora_las_ventas_anuladas(self):
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 3, 100.0)])
        anulada = db.registrar_venta([self._item(p, lote, 5, 100.0)])
        db.anular_venta(anulada, "error de carga")
        corte_id = db.hacer_corte()
        total, cantidad = self._consultar(
            "SELECT total_ventas, cantidad_ventas FROM cortes WHERE id=?", (corte_id,))[0]
        self.assertAlmostEqual(total, 300.0, places=2)
        self.assertEqual(cantidad, 1)

    def test_el_desglose_por_producto_suma_el_total_del_corte(self):
        """La tabla de arriba y el detalle de abajo tienen que dar lo mismo:
        son la misma plata contada de dos maneras."""
        p1 = self._producto("Pan", 25.50, stock=20)
        p2 = self._producto("Factura", 33.33, stock=20)
        db.registrar_venta([
            self._item(p1, self._lote(p1), 3, 25.50),
            self._item(p2, self._lote(p2), 2, 33.33),
        ])
        db.registrar_venta([self._item(p1, self._lote(p1), 4, 25.50)])
        corte_id = db.hacer_corte()
        total = self._un_valor("SELECT total_ventas FROM cortes WHERE id=?", (corte_id,))
        desglose = db.get_corte_detalle(corte_id)
        self.assertAlmostEqual(sum(d["total"] for d in desglose), total, places=2)
        # Y las cantidades por producto también, no solo la plata.
        por_nombre = {d["nombre_producto"]: d["cantidad"] for d in desglose}
        self.assertEqual(por_nombre["Pan"], 7)
        self.assertEqual(por_nombre["Factura"], 2)

    def test_un_segundo_corte_no_vuelve_a_contar_lo_del_primero(self):
        """Si `corte_id IS NULL` dejara de filtrar, cada corte del día
        acumularía todo lo anterior y la caja daría de más sin que se note."""
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 3, 100.0)])
        primero = db.hacer_corte()
        db.registrar_venta([self._item(p, lote, 2, 100.0)])
        segundo = db.hacer_corte()
        self.assertAlmostEqual(
            self._un_valor("SELECT total_ventas FROM cortes WHERE id=?", (primero,)),
            300.0, places=2)
        self.assertAlmostEqual(
            self._un_valor("SELECT total_ventas FROM cortes WHERE id=?", (segundo,)),
            200.0, places=2)

    def test_no_se_crea_un_corte_sin_ventas(self):
        self.assertIsNone(db.hacer_corte())
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM cortes"), 0)

    def test_deshacer_un_corte_reabre_sus_ventas_con_el_mismo_total(self):
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 3, 100.0)])
        db.registrar_venta([self._item(p, lote, 2, 80.0)])
        primero = db.hacer_corte()
        total_original = self._un_valor(
            "SELECT total_ventas FROM cortes WHERE id=?", (primero,))

        db.deshacer_ultimo_corte()
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM cortes"), 0)
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM corte_detalle"), 0)
        self.assertEqual(
            self._un_valor("SELECT COUNT(*) FROM ventas WHERE corte_id IS NULL"), 2)

        rehecho = db.hacer_corte()
        self.assertAlmostEqual(
            self._un_valor("SELECT total_ventas FROM cortes WHERE id=?", (rehecho,)),
            total_original, places=2)

    def test_deshacer_no_devuelve_stock(self):
        """Deshacer un corte no es anular sus ventas: la mercadería salió
        igual, lo único que se reabre es el cierre de caja."""
        p = self._producto("Pan", 100.0, stock=10)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 4, 100.0)])
        db.hacer_corte()
        db.deshacer_ultimo_corte()
        self.assertEqual(db.get_lote(lote)["stock"], 6)


class DatosCongelados(_BaseDinero):
    """Precio, costo y precio de lista se congelan en la venta. Cambiarlos
    después no puede mover ni una venta ni un corte ya hechos."""

    def test_cambiar_el_costo_no_mueve_lo_ya_vendido(self):
        p = self._producto("Pan", 100.0, stock=20, costo=40.0)
        lote = self._lote(p)
        venta_id = db.registrar_venta([self._item(p, lote, 3, 100.0)])
        corte_id = db.hacer_corte()

        db.update_producto(p, "Pan", 100.0, 90.0)  # el costo se duplica largo

        self.assertAlmostEqual(
            self._un_valor("SELECT costo_unitario FROM detalle_venta WHERE venta_id=?",
                           (venta_id,)), 40.0, places=2)
        self.assertAlmostEqual(
            self._un_valor("SELECT costo_total FROM cortes WHERE id=?", (corte_id,)),
            120.0, places=2)

    def test_cambiar_el_costo_entre_la_venta_y_el_corte_tampoco_lo_mueve(self):
        """El caso que decide dónde se congela el costo: si `hacer_corte()`
        volviera a consultar `productos.costo` en vez de sumar lo ya guardado
        en la venta, el corte mezclaría el precio de cuando se vendió con el
        costo de cuando se cortó."""
        p = self._producto("Pan", 100.0, stock=20, costo=40.0)
        venta_id = db.registrar_venta([self._item(p, self._lote(p), 3, 100.0)])

        db.update_producto(p, "Pan", 100.0, 90.0)  # cambia ANTES de cortar
        corte_id = db.hacer_corte()

        self.assertAlmostEqual(
            self._un_valor("SELECT costo_unitario FROM detalle_venta WHERE venta_id=?",
                           (venta_id,)), 40.0, places=2)
        self.assertAlmostEqual(
            self._un_valor("SELECT costo_total FROM cortes WHERE id=?", (corte_id,)),
            120.0, places=2)

    def test_cambiar_el_precio_no_mueve_lo_ya_vendido(self):
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        venta_id = db.registrar_venta([self._item(p, lote, 3, 100.0)])

        db.update_producto(p, "Pan", 500.0, 40.0)

        precio, lista = self._consultar(
            "SELECT precio_unitario, precio_lista FROM detalle_venta WHERE venta_id=?",
            (venta_id,))[0]
        self.assertAlmostEqual(precio, 100.0, places=2)
        self.assertAlmostEqual(lista, 100.0, places=2)
        self.assertAlmostEqual(
            self._un_valor("SELECT total FROM ventas WHERE id=?", (venta_id,)),
            300.0, places=2)

    def test_lo_rematado_sale_de_la_resta_del_par_no_del_total(self):
        """El error que ya pasó una vez con la base real (dio $-5.452, -605%):
        restarle `lista_total` al total del corte da cualquier cosa en cuanto
        el corte mezcla líneas con y sin precio de lista guardado. La resta
        válida es `lista_total - lista_cobrado`, que suman exactamente las
        mismas líneas.

        Acá se arma esa mezcla a mano: una venta rematada (con el dato) y una
        de "antes de la columna", con el precio de lista en blanco.
        """
        p = self._producto("Pan", 100.0, stock=20)
        lote = self._lote(p)
        db.registrar_venta([self._item(p, lote, 2, 60.0)])   # rematado: lista 100, cobrado 60
        vieja = db.registrar_venta([self._item(p, lote, 3, 100.0)])
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            c.execute("UPDATE detalle_venta SET precio_lista=0, lista_subtotal=0 "
                      "WHERE venta_id=?", (vieja,))
            c.commit()

        db.hacer_corte()
        r = db.get_resumen_analisis()
        self.assertAlmostEqual(r["total"], 120.0 + 300.0, places=2)
        self.assertAlmostEqual(r["lista_total"], 200.0, places=2)
        self.assertAlmostEqual(r["lista_cobrado"], 120.0, places=2)
        self.assertAlmostEqual(r["rematado"], 80.0, places=2)
        # Lo que fallaba: `total - lista_total` habría dado 220.
        self.assertGreaterEqual(r["rematado"], 0)


class ClavesForaneas(_BaseDinero):
    """Las claves foráneas están encendidas (`PRAGMA foreign_keys=ON` en cada
    conexión). Estas pruebas cuidan las dos caras: que la base rechace lo que
    no cierra, y que NO rompa lo que la app hace legítimamente."""

    def test_la_base_rechaza_referencias_que_no_existen(self):
        """Si esto empezara a pasar, el PRAGMA se apagó: las declaraciones
        REFERENCES de las tablas volvieron a ser decorativas."""
        casos = [
            ("línea de venta de un producto inexistente",
             "INSERT INTO detalle_venta (venta_id, producto_id, cantidad, precio_unitario,"
             " subtotal) VALUES (1, 99999, 1, 1, 1)"),
            ("detalle colgado de un corte que no existe",
             "INSERT INTO corte_detalle (corte_id, nombre_producto, cantidad, total)"
             " VALUES (99999, 'x', 1, 1)"),
            ("tanda de un producto inexistente",
             "INSERT INTO lotes (producto_id, fecha_horneado, stock)"
             " VALUES (99999, '2026-01-01', 5)"),
        ]
        for descripcion, sql in casos:
            with self.subTest(descripcion):
                with closing(sqlite3.connect(db.DB_PATH)) as c:
                    c.execute("PRAGMA foreign_keys = ON")
                    with self.assertRaises(sqlite3.IntegrityError):
                        c.execute(sql)

    def test_se_puede_borrar_una_tanda_que_ya_tuvo_ventas(self):
        """El motivo de todo el `ON DELETE SET NULL`: `eliminar_lote()` borra
        la tanda físicamente, y con las claves foráneas encendidas eso pasaría
        a fallar en cuanto la tanda tuviera una venta -- o sea, casi siempre.
        La venta tiene que sobrevivir intacta, con su línea apuntando a NULL.
        """
        p = self._producto("Pan", 100.0, stock=10)
        lote = self._lote(p)
        venta_id = db.registrar_venta([self._item(p, lote, 4, 100.0)])

        db.eliminar_lote(lote)

        self.assertEqual(
            self._un_valor("SELECT lote_id FROM detalle_venta WHERE venta_id=?", (venta_id,)),
            None)
        self.assertAlmostEqual(
            self._un_valor("SELECT total FROM ventas WHERE id=?", (venta_id,)),
            400.0, places=2)

    def test_anular_una_venta_de_una_tanda_borrada_no_inventa_stock(self):
        """Sin tanda a la que devolverle la mercadería, se omite en vez de
        inventar un destino -- el mismo caso que las ventas anteriores a los
        lotes. Lo que no puede es reventar ni crear un lote de la nada."""
        p = self._producto("Pan", 100.0, stock=10)
        lote = self._lote(p)
        venta_id = db.registrar_venta([self._item(p, lote, 4, 100.0)])
        db.eliminar_lote(lote)

        db.anular_venta(venta_id, "la tanda ya se había tirado")

        self.assertEqual(
            self._un_valor("SELECT anulada FROM ventas WHERE id=?", (venta_id,)), 1)
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM lotes"), 0)

    def test_deshacer_un_corte_no_choca_con_las_claves_foraneas(self):
        """Borra `cortes` teniendo `ventas.corte_id` y `corte_detalle`
        apuntándole: el orden en que lo hace importa ahora que las claves
        foráneas se revisan de verdad."""
        p = self._producto("Pan", 100.0, stock=20)
        db.registrar_venta([self._item(p, self._lote(p), 3, 100.0)])
        db.hacer_corte()
        db.deshacer_ultimo_corte()
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM cortes"), 0)

    def test_la_estructura_quedo_migrada(self):
        """Una base nueva tiene que nacer ya con el ON DELETE SET NULL, sin
        depender de que la migración corra sobre una base vieja."""
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            fk = next(f for f in c.execute("PRAGMA foreign_key_list(detalle_venta)")
                      if f[3] == "lote_id")
            self.assertEqual(fk[6], "SET NULL")
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_las_conexiones_de_la_app_traen_el_pragma_encendido(self):
        """El esquema puede estar perfecto y no servir de nada: en SQLite las
        claves foráneas se encienden POR CONEXIÓN y vienen apagadas de fábrica.
        Sin esta línea en `_conn()`, los REFERENCES no rigen en ningún lado."""
        with db._conn() as c:
            self.assertEqual(c.execute("PRAGMA foreign_keys").fetchone()[0], 1)


class MigracionDeClavesForaneas(_BaseDinero):
    """La migración que reconstruye `detalle_venta`. Corre una sola vez y
    sobre datos reales, así que se prueba con una base armada a la vieja."""

    # detalle_venta tal como era ANTES: la FK de lote_id sin ON DELETE.
    _VIEJA = """
        CREATE TABLE detalle_venta (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id        INTEGER NOT NULL REFERENCES ventas(id),
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            cantidad        INTEGER NOT NULL,
            precio_unitario REAL    NOT NULL,
            subtotal        REAL    NOT NULL,
            costo_unitario  REAL    NOT NULL DEFAULT 0,
            costo_subtotal  REAL    NOT NULL DEFAULT 0,
            lote_id         INTEGER REFERENCES lotes(id),
            precio_lista    REAL    NOT NULL DEFAULT 0,
            lista_subtotal  REAL    NOT NULL DEFAULT 0,
            dias_antiguedad INTEGER
        )
    """

    def _volver_al_esquema_viejo(self):
        """Deja la base como la de Alan antes de esta versión: un producto,
        una tanda viva, una venta con tres líneas -- una apuntando a la tanda
        viva, otra a una tanda ya borrada (huérfana) y otra en NULL (venta
        anterior al sistema de lotes).

        Los ids van salteados (4, 8, 15) y no 1, 2, 3 a propósito: una base
        de verdad tiene huecos, y con ids corridos desde 1 una migración que
        los renumerara daría por casualidad exactamente los mismos números y
        el error pasaría desapercibido.
        """
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            c.execute("PRAGMA foreign_keys = OFF")
            c.execute("DROP TABLE detalle_venta")
            c.execute(self._VIEJA)
            c.execute("INSERT INTO productos (id, nombre, precio, costo) VALUES (1, 'Pan', 10, 4)")
            c.execute("INSERT INTO lotes (id, producto_id, fecha_horneado, stock) "
                      "VALUES (7, 1, '2026-01-01', 50)")
            c.execute("INSERT INTO ventas (id, fecha, total) VALUES (1, '2026-01-01 08:00:00', 60)")
            for linea_id, lote_id in [(4, 7), (8, 999), (15, None)]:
                c.execute(
                    "INSERT INTO detalle_venta (id, venta_id, producto_id, lote_id, cantidad,"
                    " precio_unitario, subtotal, costo_unitario, costo_subtotal,"
                    " precio_lista, lista_subtotal, dias_antiguedad)"
                    " VALUES (?, 1, 1, ?, 2, 10, 20, 4, 8, 10, 20, 0)", (linea_id, lote_id))
            c.commit()

    def _filas(self):
        return self._consultar("SELECT * FROM detalle_venta ORDER BY id")

    def test_migrar_limpia_las_huerfanas_y_no_pierde_nada(self):
        self._volver_al_esquema_viejo()
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            fk = next(f for f in c.execute("PRAGMA foreign_key_list(detalle_venta)")
                      if f[3] == "lote_id")
            self.assertEqual(fk[6], "NO ACTION")  # confirma que arrancamos de lo viejo
            self.assertEqual(len(c.execute("PRAGMA foreign_key_check").fetchall()), 1)
        antes = self._filas()

        db.init_db()  # acá corre la migración

        # Fila por fila y columna por columna, no solo la suma de una: una
        # migración que se olvidara de copiar el costo, el precio de lista o
        # la antigüedad dejaría el total intacto y el resto en cero.
        despues = self._filas()
        self.assertEqual(len(despues), 3)
        for fila_antes, fila_despues in zip(antes, despues):
            esperada = list(fila_antes)
            if esperada[8] == 999:   # la única diferencia esperada: la huérfana
                esperada[8] = None
            self.assertEqual(list(fila_despues), esperada)

        # Y explícitamente, lo que la migración sí tiene que cambiar:
        self.assertEqual(self._un_valor("SELECT lote_id FROM detalle_venta WHERE id=4"), 7)
        self.assertIsNone(self._un_valor("SELECT lote_id FROM detalle_venta WHERE id=8"))
        self.assertIsNone(self._un_valor("SELECT lote_id FROM detalle_venta WHERE id=15"))
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            fk = next(f for f in c.execute("PRAGMA foreign_key_list(detalle_venta)")
                      if f[3] == "lote_id")
            self.assertEqual(fk[6], "SET NULL")
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_migrar_conserva_los_ids_y_el_contador(self):
        """Los ids no se pueden renumerar: la línea 8 tiene que seguir siendo
        la 8, y la próxima que se inserte la 16 -- no la 4."""
        self._volver_al_esquema_viejo()
        db.init_db()
        self.assertEqual(
            [r[0] for r in self._consultar("SELECT id FROM detalle_venta ORDER BY id")],
            [4, 8, 15])
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            c.execute("INSERT INTO detalle_venta (venta_id, producto_id, cantidad,"
                      " precio_unitario, subtotal) VALUES (1, 1, 1, 5, 5)")
            c.commit()
        self.assertEqual(self._un_valor("SELECT MAX(id) FROM detalle_venta"), 16)

    def test_migrar_dos_veces_no_rehace_la_tabla_la_segunda(self):
        """Se cuenta si la reconstrucción se llamó, en vez de comparar los
        datos: rehacer la tabla de más deja exactamente las mismas filas, así
        que mirando los datos no se distingue "no se hizo nada" de "se rehizo
        al pedo en cada arranque". (Tampoco sirve mirar en qué página del
        archivo vive la tabla: SQLite reutiliza la que acaba de liberar, y al
        reconstruir dos veces vuelve a caer en la misma.)
        """
        self._volver_al_esquema_viejo()
        db.init_db()
        antes = self._filas()

        reconstrucciones = []
        original = db._rehacer_detalle_venta

        def espia(c):
            reconstrucciones.append(1)
            return original(c)

        db._rehacer_detalle_venta = espia
        try:
            db.init_db()
            db.init_db()
        finally:
            db._rehacer_detalle_venta = original

        self.assertEqual(reconstrucciones, [])
        self.assertEqual(self._filas(), antes)

    def test_si_la_migracion_falla_la_app_sigue_funcionando_como_antes(self):
        """El caso que decide todo el diseño: encender las claves foráneas
        sobre el esquema viejo dejaría la app PEOR que sin la mejora (borrar
        una tanda con ventas pasaría a fallar). Así que si la migración no se
        puede aplicar, quedan apagadas y todo sigue como hoy.

        Se fuerza el fallo con una línea de venta que apunta a un producto que
        no existe: la migración no puede arreglar eso (solo limpia `lote_id`),
        así que verifica, deshace y se retira.
        """
        self._volver_al_esquema_viejo()
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            c.execute("PRAGMA foreign_keys = OFF")
            c.execute("INSERT INTO detalle_venta (id, venta_id, producto_id, lote_id,"
                      " cantidad, precio_unitario, subtotal) VALUES (9, 1, 99999, NULL, 1, 5, 5)")
            c.commit()
        antes = self._filas()

        db.init_db()  # no debe levantar excepción

        # La tabla quedó tal cual estaba, con su esquema viejo y sus datos.
        self.assertEqual(self._filas(), antes)
        with closing(sqlite3.connect(db.DB_PATH)) as c:
            fk = next(f for f in c.execute("PRAGMA foreign_key_list(detalle_venta)")
                      if f[3] == "lote_id")
            self.assertEqual(fk[6], "NO ACTION")
            self.assertIsNone(
                c.execute("SELECT 1 FROM sqlite_master WHERE name='detalle_venta_nueva'"
                          ).fetchone())
        # Y lo que importa de verdad: las claves foráneas NO se encendieron,
        # así que borrar una tanda con ventas encima sigue funcionando.
        self.assertFalse(db._FK_ACTIVAS)
        db.eliminar_lote(7)
        self.assertEqual(self._un_valor("SELECT COUNT(*) FROM lotes"), 0)


class DescuentoPorAntiguedad(unittest.TestCase):
    """`precio_vigente()` es matemática pura, no toca la base -- por eso esta
    clase no hereda de `_BaseDinero`."""

    def _tanda(self, precio, dias):
        return {"id": 1, "precio": precio,
                "fecha_horneado": (date.today() - timedelta(days=dias)).isoformat()}

    def test_usa_la_regla_mas_alta_que_aplique_no_la_exacta(self):
        """Son escalones, no rangos: pan de 5 días con reglas en el 1 y el 3
        usa la del 3. Si buscara coincidencia exacta no descontaría nada.

        Las reglas van ordenadas por día de menor a mayor -- así las devuelven
        `get_reglas_descuento()` y `get_reglas_de_producto()` (ORDER BY dias),
        y `precio_vigente()` cuenta con eso: se queda con la última que aplica.
        """
        reglas = [{"dias": 1, "porcentaje": 10}, {"dias": 3, "porcentaje": 30}]
        precio, dias, pct = db.precio_vigente(self._tanda(100.0, 5), reglas)
        self.assertAlmostEqual(precio, 70.0, places=2)
        self.assertEqual(dias, 5)
        self.assertEqual(pct, 30)

    def test_la_tanda_del_dia_no_se_descuenta(self):
        reglas = [{"dias": 1, "porcentaje": 10}, {"dias": 3, "porcentaje": 30}]
        precio, dias, pct = db.precio_vigente(self._tanda(100.0, 0), reglas)
        self.assertAlmostEqual(precio, 100.0, places=2)
        self.assertEqual(dias, 0)
        self.assertIsNone(pct)

    def test_sin_fecha_de_horneado_el_precio_no_cambia(self):
        """Antigüedad no trackeada = precio de lista, nunca un descuento
        inventado ni una antigüedad de cero."""
        reglas = [{"dias": 1, "porcentaje": 50}]
        precio, dias, pct = db.precio_vigente({"id": 1, "precio": 100.0,
                                               "fecha_horneado": None}, reglas)
        self.assertAlmostEqual(precio, 100.0, places=2)
        self.assertIsNone(dias)
        self.assertIsNone(pct)

    def test_la_regla_propia_del_producto_reemplaza_a_las_generales(self):
        """No se combinan ni se suman: si el producto tiene reglas propias,
        las generales no participan (aunque la general descontara más)."""
        generales = [{"dias": 1, "porcentaje": 10}, {"dias": 3, "porcentaje": 30}]
        propias = {1: [{"dias": 1, "porcentaje": 50}]}
        precio, _, pct = db.precio_vigente(self._tanda(100.0, 5), generales, propias)
        self.assertAlmostEqual(precio, 50.0, places=2)
        self.assertEqual(pct, 50)

    def test_la_regla_propia_que_todavia_no_aplica_no_deja_pasar_la_general(self):
        """El caso que distingue "reemplazan" de "se combinan": el producto
        tiene una regla propia recién a partir del día 7, así que a los 5 días
        NO se descuenta nada -- aunque la general sí descontaría un 30%. Si las
        listas se mezclaran, acá saldría pan rebajado sin que nadie lo pidió.
        """
        generales = [{"dias": 1, "porcentaje": 10}, {"dias": 3, "porcentaje": 30}]
        propias = {1: [{"dias": 7, "porcentaje": 50}]}
        precio, dias, pct = db.precio_vigente(self._tanda(100.0, 5), generales, propias)
        self.assertAlmostEqual(precio, 100.0, places=2)
        self.assertEqual(dias, 5)
        self.assertIsNone(pct)

    def test_un_producto_sin_reglas_propias_cae_a_las_generales(self):
        generales = [{"dias": 3, "porcentaje": 30}]
        propias = {99: [{"dias": 1, "porcentaje": 50}]}  # de otro producto
        precio, _, pct = db.precio_vigente(self._tanda(100.0, 5), generales, propias)
        self.assertAlmostEqual(precio, 70.0, places=2)
        self.assertEqual(pct, 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
