import functools
import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime

import registro
from rutas import BASE_DIR

DB_PATH = BASE_DIR / "panaderia.db"
BACKUP_DIR = BASE_DIR / "backups"
MAX_BACKUPS = 30


class DBError(Exception):
    """Error de base de datos con un mensaje pensado para mostrarse al usuario."""


# Las claves foráneas se encienden recién cuando `init_db()` confirmó que la
# estructura las soporta. Encenderlas sobre el esquema viejo sería PEOR que
# dejarlas apagadas: `eliminar_lote()` pasaría a fallar en cualquier tanda que
# tenga una venta encima (ver _migrar_borrado_de_tandas()). Arranca apagado
# para que ese momento no exista, ni siquiera si la migración falla.
_FK_ACTIVAS = False


def _conn():
    # closing() garantiza que la conexión se cierre siempre al salir del
    # bloque "with", incluso si hay una excepción. sqlite3.Connection ya
    # commitea/rollbackea en su propio __exit__, pero nunca cierra el
    # archivo por sí sola.
    con = sqlite3.connect(DB_PATH)
    # SQLite trae las claves foráneas APAGADAS por defecto (compatibilidad
    # hacia atrás), y el ajuste es POR CONEXIÓN, no del archivo: si no se
    # enciende acá, las declaraciones "REFERENCES" de las tablas son
    # decorativas. Con esto encendido la base rechaza sola una línea de venta
    # que apunte a un producto inexistente, o un detalle colgado de un corte
    # ya borrado -- aunque el código que la genere tenga un bug.
    if _FK_ACTIVAS:
        con.execute("PRAGMA foreign_keys = ON")
    return closing(con)


def _safe(fn):
    """Convierte cualquier error de SQLite en un DBError con mensaje amigable.

    Además lo deja anotado en el log: la pantalla le muestra al usuario un
    mensaje corto y entendible, pero ese mensaje pierde el traceback y el
    nombre de la operación que falló, que es justo lo único que sirve para
    diagnosticar después. Es el punto único por donde pasan TODOS los
    errores de base, así que alcanza con registrarlo acá."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.Error as e:
            registro.error(f"Error de SQLite en {fn.__name__}()")
            raise DBError(
                "No se pudo completar la operación en la base de datos.\n"
                f"Detalle técnico: {e}"
            ) from e
    return wrapper


def respaldar_db():
    """
    Copia panaderia.db a backups/ con timestamp en el nombre. Pensada para
    llamarse una vez al arrancar la app, ANTES de init_db() -- así queda
    respaldado el estado exacto con el que se cerró la sesión anterior,
    antes de que cualquier migración lo toque.

    No usa @_safe ni levanta DBError a propósito: un fallo al hacer backup
    (disco lleno, permisos) no debe impedir que la app arranque y la
    persona pueda seguir vendiendo. Se ignora en silencio.

    Mantiene como máximo MAX_BACKUPS copias (borra las más viejas) para no
    llenar el disco con el tiempo -- la app puede quedar abierta meses.
    """
    if not DB_PATH.exists():
        return  # primera vez que se usa la app, todavía no hay nada que respaldar
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        shutil.copy2(DB_PATH, BACKUP_DIR / f"panaderia_{timestamp}.db")

        backups = sorted(BACKUP_DIR.glob("panaderia_*.db"))
        for viejo in backups[:-MAX_BACKUPS]:
            viejo.unlink()
    except OSError:
        pass


@_safe
def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre  TEXT    NOT NULL,
                precio  REAL    NOT NULL,
                stock   INTEGER NOT NULL DEFAULT 0,
                activo  INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha  TEXT    NOT NULL,
                total  REAL    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS detalle_venta (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id        INTEGER NOT NULL REFERENCES ventas(id),
                producto_id     INTEGER NOT NULL REFERENCES productos(id),
                cantidad        INTEGER NOT NULL,
                precio_unitario REAL    NOT NULL,
                subtotal        REAL    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS cortes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha           TEXT    NOT NULL,
                total_ventas    REAL    NOT NULL,
                cantidad_ventas INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS corte_detalle (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                corte_id        INTEGER NOT NULL REFERENCES cortes(id),
                nombre_producto TEXT    NOT NULL,
                cantidad        INTEGER NOT NULL,
                total           REAL    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS insumos (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre  TEXT    NOT NULL,
                unidad  TEXT    NOT NULL,
                stock   REAL    NOT NULL DEFAULT 0,
                activo  INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Reglas de descuento por antigüedad del pan: a partir de qué día
        # (desde productos.fecha_horneado) se aplica qué % de descuento.
        # Son escalones, no rangos -- precio_vigente() usa la de mayor
        # "dias" que sea <= la antigüedad real.
        c.execute("""
            CREATE TABLE IF NOT EXISTS reglas_descuento (
                dias        INTEGER PRIMARY KEY,
                porcentaje  REAL    NOT NULL
            )
        """)
        # Reglas propias de UN producto puntual (ej. las facturas se echan
        # a perder más rápido que el pan lactal) -- si un producto tiene
        # filas acá, precio_vigente() las usa en vez de las generales de
        # reglas_descuento; si no tiene ninguna, cae a las generales. No
        # hace falta cargar reglas producto por producto, solo para las
        # excepciones.
        c.execute("""
            CREATE TABLE IF NOT EXISTS reglas_descuento_producto (
                producto_id INTEGER NOT NULL REFERENCES productos(id),
                dias        INTEGER NOT NULL,
                porcentaje  REAL    NOT NULL,
                PRIMARY KEY (producto_id, dias)
            )
        """)
        # Lotes: el stock de un producto puede convivir en distintas
        # hornadas a la vez (pan de hoy Y pan de hace 3 días sin vender
        # todavía) -- cada fila es UNA hornada con su propia fecha y
        # cantidad, en vez de un único "stock" y una única fecha por
        # producto. El stock total de un producto es la suma de sus lotes
        # con stock > 0 (ver get_productos()). Un lote en 0 no se borra
        # solo, queda inerte y filtrado por las consultas -- eliminar_lote()
        # es la baja explícita.
        c.execute("""
            CREATE TABLE IF NOT EXISTS lotes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id    INTEGER NOT NULL REFERENCES productos(id),
                fecha_horneado TEXT    NOT NULL,
                stock          INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migración: columna que marca qué venta ya quedó incluida en un
        # corte. NULL = todavía pendiente de cortar. Se agrega con chequeo
        # manual (en vez de "ADD COLUMN IF NOT EXISTS") para no depender de
        # una versión reciente de SQLite.
        columnas = [r[1] for r in c.execute("PRAGMA table_info(ventas)").fetchall()]
        if "corte_id" not in columnas:
            c.execute("ALTER TABLE ventas ADD COLUMN corte_id INTEGER REFERENCES cortes(id)")
        if "anulada" not in columnas:
            c.execute("ALTER TABLE ventas ADD COLUMN anulada INTEGER NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE ventas ADD COLUMN motivo_anulacion TEXT")
            c.execute("ALTER TABLE ventas ADD COLUMN fecha_anulacion TEXT")
        if "pago" not in columnas:
            # Con cuánto pagó el cliente, para imprimir "PAGO CON" y "SU
            # CAMBIO" en el ticket. Es OPCIONAL y por eso admite NULL, sin
            # DEFAULT 0: NULL = no se registró (el vendedor dejó el campo
            # vacío, o es una venta anterior a esta columna) y el ticket
            # omite las dos líneas, mientras que un 0 se imprimiría como
            # "SU CAMBIO: $0.00", o sea "pagó justo" -- que es un hecho
            # distinto. Mismo criterio que el costo y el precio de lista:
            # dato faltante no es cero. No entra en ninguna cuenta de caja
            # (el corte suma `total`, nunca `pago`): es un dato del papel.
            c.execute("ALTER TABLE ventas ADD COLUMN pago REAL")
        columnas_insumos = [r[1] for r in c.execute("PRAGMA table_info(insumos)").fetchall()]
        if "stock_minimo" not in columnas_insumos:
            # 0 = sin umbral configurado (no dispara alerta de stock bajo).
            c.execute("ALTER TABLE insumos ADD COLUMN stock_minimo REAL NOT NULL DEFAULT 0")
        if "fecha_inicial" not in columnas_insumos:
            # Con cuánto arrancó el día este insumo, y de qué día es esa
            # marca. De acá sale la "sombra" del Inventario (lo que había
            # antes de ponerse a hornear). `fecha_inicial` NULL = nunca se
            # ajustó: no hay nada que rastrear y no se dibuja sombra.
            # Ver ajustar_stock_insumo() para cuándo se renueva la marca.
            c.execute("ALTER TABLE insumos ADD COLUMN stock_inicial_dia REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE insumos ADD COLUMN fecha_inicial TEXT")
        columnas_productos = [r[1] for r in c.execute("PRAGMA table_info(productos)").fetchall()]
        if "costo" not in columnas_productos:
            # Costo interno, distinto del precio de venta -- para calcular
            # margen (precio - costo). 0 = todavía no cargado (no implica
            # margen 100%, la UI lo muestra como "sin datos").
            c.execute("ALTER TABLE productos ADD COLUMN costo REAL NOT NULL DEFAULT 0")
        # El costo se CONGELA en detalle_venta al momento de la venta, igual
        # criterio que precio_unitario/subtotal: si el costo del producto
        # cambia después, el margen de ventas ya hechas no se altera. 0 =
        # no había costo cargado en ese momento (margen de esa línea
        # queda como "sin datos", no como "100% de margen").
        columnas_detalle = [r[1] for r in c.execute("PRAGMA table_info(detalle_venta)").fetchall()]
        if "costo_unitario" not in columnas_detalle:
            c.execute("ALTER TABLE detalle_venta ADD COLUMN costo_unitario REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE detalle_venta ADD COLUMN costo_subtotal REAL NOT NULL DEFAULT 0")
        if "lote_id" not in columnas_detalle:
            # De qué lote salió esta línea -- para poder devolverle el
            # stock al lote correcto si la venta se anula (ver
            # anular_venta()). NULL en ventas de antes de que existieran
            # los lotes: anularlas no puede devolver el stock a ningún
            # lado en particular, se omite en vez de inventar uno.
            c.execute("ALTER TABLE detalle_venta ADD COLUMN lote_id INTEGER REFERENCES lotes(id)")
        # Precio de LISTA (sin descuento por antigüedad) y antigüedad de la
        # tanda, congelados igual que el costo. Sin esto no hay forma de
        # saber después cuánto se dejó de cobrar por rematar pan viejo:
        # `productos.precio` cambia con el tiempo y eliminar_lote() borra la
        # fila físicamente, así que la antigüedad de una venta pasada no se
        # puede reconstruir. 0 / NULL = venta anterior a esta columna, la UI
        # lo muestra como "sin datos" (nunca como "descuento cero").
        if "precio_lista" not in columnas_detalle:
            c.execute("ALTER TABLE detalle_venta ADD COLUMN precio_lista REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE detalle_venta ADD COLUMN lista_subtotal REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE detalle_venta ADD COLUMN dias_antiguedad INTEGER")
        # corte_detalle/cortes: mismo costo ya congelado en detalle_venta,
        # sumado -- hacer_corte() no vuelve a consultar productos.costo.
        columnas_corte_detalle = [r[1] for r in c.execute("PRAGMA table_info(corte_detalle)").fetchall()]
        if "costo_total" not in columnas_corte_detalle:
            c.execute("ALTER TABLE corte_detalle ADD COLUMN costo_total REAL NOT NULL DEFAULT 0")
        # `lista_total` y `lista_cobrado` van SIEMPRE de a pares y suman solo
        # las líneas que tienen precio de lista guardado: lo rematado es la
        # resta entre ambos. Guardar únicamente `lista_total` y restarle el
        # total del corte daría un número sin sentido en cualquier corte que
        # mezcle ventas con y sin el dato (pasa sí o sí en el corte de la
        # transición, y en cualquier venta sin lote asociado).
        if "lista_total" not in columnas_corte_detalle:
            c.execute("ALTER TABLE corte_detalle ADD COLUMN lista_total REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE corte_detalle ADD COLUMN lista_cobrado REAL NOT NULL DEFAULT 0")
        columnas_cortes = [r[1] for r in c.execute("PRAGMA table_info(cortes)").fetchall()]
        if "costo_total" not in columnas_cortes:
            c.execute("ALTER TABLE cortes ADD COLUMN costo_total REAL NOT NULL DEFAULT 0")
        if "lista_total" not in columnas_cortes:
            c.execute("ALTER TABLE cortes ADD COLUMN lista_total REAL NOT NULL DEFAULT 0")
            c.execute("ALTER TABLE cortes ADD COLUMN lista_cobrado REAL NOT NULL DEFAULT 0")
        c.commit()
    # Va al final y con conexión propia: reconstruye una tabla entera y necesita
    # las claves foráneas APAGADAS, al revés que todo el resto de la app.
    _migrar_borrado_de_tandas()


# Estructura final de detalle_venta. Se escribe entera acá (y no como otro
# ALTER TABLE) porque SQLite no sabe modificar una clave foránea ya creada:
# la única vía es rehacer la tabla y copiar las filas.
_DETALLE_VENTA_NUEVA = """
    CREATE TABLE detalle_venta_nueva (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id        INTEGER NOT NULL REFERENCES ventas(id),
        producto_id     INTEGER NOT NULL REFERENCES productos(id),
        cantidad        INTEGER NOT NULL,
        precio_unitario REAL    NOT NULL,
        subtotal        REAL    NOT NULL,
        costo_unitario  REAL    NOT NULL DEFAULT 0,
        costo_subtotal  REAL    NOT NULL DEFAULT 0,
        lote_id         INTEGER REFERENCES lotes(id) ON DELETE SET NULL,
        precio_lista    REAL    NOT NULL DEFAULT 0,
        lista_subtotal  REAL    NOT NULL DEFAULT 0,
        dias_antiguedad INTEGER
    )
"""

# El orden de las columnas es el mismo que venían teniendo (el que dejaron los
# ALTER TABLE de arriba, uno atrás del otro), así que ningún SELECT * cambia
# de forma. La línea del CASE es la que limpia: un lote_id que apunta a una
# tanda ya borrada pasa a NULL, que es exactamente lo que significa.
_COPIAR_DETALLE_VENTA = """
    INSERT INTO detalle_venta_nueva
        (id, venta_id, producto_id, cantidad, precio_unitario, subtotal,
         costo_unitario, costo_subtotal, lote_id, precio_lista, lista_subtotal,
         dias_antiguedad)
    SELECT id, venta_id, producto_id, cantidad, precio_unitario, subtotal,
           costo_unitario, costo_subtotal,
           CASE WHEN lote_id IN (SELECT id FROM lotes) THEN lote_id END,
           precio_lista, lista_subtotal, dias_antiguedad
    FROM detalle_venta
"""


def _borrado_de_tandas_ya_migrado(c):
    """¿La FK de lote_id ya tiene el ON DELETE SET NULL?

    Se pregunta por la estructura y no por un número de versión guardado
    aparte: es la misma condición que la migración deja verdadera, así que no
    puede desincronizarse ni quedar marcada como hecha sin haberse hecho.
    """
    for fk in c.execute("PRAGMA foreign_key_list(detalle_venta)").fetchall():
        if fk[3] == "lote_id":          # fk[3] = columna, fk[6] = ON DELETE
            return fk[6] == "SET NULL"
    return False


def _rehacer_detalle_venta(c):
    """La reconstrucción propiamente dicha. `c` viene en autocommit y con las
    claves foráneas apagadas. Si algo sale mal deshace TODO: es preferible
    quedarse con la tabla vieja que con una a medio rehacer."""
    c.execute("BEGIN")
    try:
        c.execute(_DETALLE_VENTA_NUEVA)
        c.execute(_COPIAR_DETALLE_VENTA)
        c.execute("DROP TABLE detalle_venta")
        c.execute("ALTER TABLE detalle_venta_nueva RENAME TO detalle_venta")
        # Verificar ANTES de confirmar. Se mira SOLO la tabla reconstruida y
        # no la base entera a propósito: una referencia colgada en otra tabla
        # no la causó esta migración y no es motivo para renunciar a ella.
        problemas = c.execute("PRAGMA foreign_key_check(detalle_venta)").fetchall()
        if problemas:
            raise sqlite3.IntegrityError(
                f"quedaron {len(problemas)} referencias sin resolver")
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def _migrar_borrado_de_tandas():
    """Le pone ON DELETE SET NULL a `detalle_venta.lote_id` y, si sale bien,
    habilita las claves foráneas para toda la app.

    Por qué hace falta: `eliminar_lote()` borra la tanda FÍSICAMENTE (es la
    baja explícita de una hornada que se tiró). Con las claves foráneas
    encendidas y la FK como estaba, ese borrado pasaría a fallar en cuanto la
    tanda tuviera una sola venta -- o sea, casi siempre. SET NULL deja
    borrarla y le pone NULL a sus líneas de venta, que es justo lo que
    `anular_venta()` ya sabe interpretar: "no hay tanda a la que devolverle
    el stock", el mismo caso que las ventas anteriores al sistema de lotes.

    De paso limpia las huérfanas que dejó el modelo viejo (612 en la base de
    la demo): apuntaban a tandas borradas hace rato, así que ya no
    significaban nada distinto de NULL.

    **Si la migración falla, las claves foráneas quedan apagadas y la app
    sigue funcionando exactamente como antes.** Es deliberado y es el punto
    más importante de esta función: encenderlas sobre el esquema viejo
    rompería el borrado de tandas, o sea que un fallo acá dejaría la app
    PEOR que sin la mejora. Mismo criterio que `respaldar_db()` y que
    `registro.py`: una mejora que no se pudo aplicar no puede impedir vender.
    El error queda anotado en el log.

    Corre una sola vez; si la tabla ya está migrada no toca nada. Ojo con el
    respaldo: `respaldar_db()` se llama en `main.py` ANTES de `init_db()`,
    así que queda una copia del archivo tal como estaba justo antes de esto.
    """
    global _FK_ACTIVAS
    # isolation_level=None (autocommit) para manejar BEGIN/COMMIT a mano:
    # `PRAGMA foreign_keys` es una instrucción vacía adentro de una
    # transacción, y acá hay que poder apagarlas antes de abrirla.
    with closing(sqlite3.connect(DB_PATH, isolation_level=None)) as c:
        if not _borrado_de_tandas_ya_migrado(c):
            c.execute("PRAGMA foreign_keys = OFF")
            try:
                _rehacer_detalle_venta(c)
            except Exception:
                registro.error("No se pudo migrar detalle_venta: las claves "
                               "foráneas quedan apagadas y la app sigue igual "
                               "que antes")
                # Se apaga explícitamente en vez de confiar en que ya estaba
                # apagada: es un interruptor de seguridad, tiene que quedar en
                # una posición conocida sin importar cómo se llegó hasta acá.
                _FK_ACTIVAS = False
                return
        _FK_ACTIVAS = True


# ── Productos ────────────────────────────────────────────────────────────────

@_safe
def get_productos(solo_activos=True):
    """
    `stock` acá es el TOTAL sumado de todos los lotes activos del
    producto (ver tabla `lotes`) -- las columnas `productos.stock` y
    `productos.fecha_horneado` de versiones anteriores quedaron sin uso,
    superadas por `lotes`; esta consulta ni las toca. Para el desglose
    por hornada (necesario para el descuento por antigüedad y para los
    botones "+ Agregar" de cada lote en Nueva Venta) hace falta además
    get_lotes_todos() o get_lotes(producto_id).
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        filtro = "WHERE p.activo=1" if solo_activos else ""
        sql = f"""
            SELECT p.id, p.nombre, p.precio, p.costo, p.activo,
                   COALESCE(SUM(l.stock), 0) AS stock
            FROM productos p
            LEFT JOIN lotes l ON l.producto_id = p.id AND l.stock > 0
            {filtro}
            GROUP BY p.id
            ORDER BY p.nombre
        """
        return [dict(r) for r in c.execute(sql).fetchall()]


@_safe
def add_producto(nombre, precio, stock, costo=0):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO productos (nombre, precio, costo) VALUES (?, ?, ?)",
            (nombre, precio, costo),
        )
        # El stock inicial es la primera hornada del producto -- se asume
        # recién horneada, mismo criterio que agregar_lote() para cualquier
        # hornada nueva.
        if stock > 0:
            c.execute(
                "INSERT INTO lotes (producto_id, fecha_horneado, stock) VALUES (?, ?, ?)",
                (cur.lastrowid, date.today().isoformat(), stock),
            )
        c.commit()


@_safe
def update_producto(id, nombre, precio, costo):
    with _conn() as c:
        c.execute("UPDATE productos SET nombre=?, precio=?, costo=? WHERE id=?",
                  (nombre, precio, costo, id))
        c.commit()


@_safe
def desactivar_producto(id):
    with _conn() as c:
        c.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))
        c.commit()


@_safe
def reactivar_producto(id):
    with _conn() as c:
        c.execute("UPDATE productos SET activo=1 WHERE id=?", (id,))
        c.commit()


# ── Lotes ────────────────────────────────────────────────────────────────────
# El stock de un producto puede convivir en más de una hornada a la vez
# (pan de hoy Y pan de hace 3 días sin vender todavía) -- cada lote es una
# hornada con su propia fecha y cantidad. Nueva Venta muestra un botón
# "+ Agregar" por cada lote activo de un producto, con su propio precio
# según la antigüedad de ESE lote puntual (ver precio_vigente()).

@_safe
def get_lotes(producto_id):
    """Lotes activos (stock > 0) de UN producto, del más viejo al más nuevo."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(
            "SELECT * FROM lotes WHERE producto_id=? AND stock > 0 ORDER BY fecha_horneado",
            (producto_id,)).fetchall()]


@_safe
def get_lote(lote_id):
    """Un lote puntual -- para revalidar su stock antes de subir la
    cantidad de una línea ya agregada al carrito en Nueva Venta."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM lotes WHERE id=?", (lote_id,)).fetchone()
        return dict(row) if row else None


@_safe
def get_lotes_todos():
    """Todos los lotes activos, agrupados por producto_id -- para resolver
    una lista completa de productos (Productos, Nueva Venta) sin una
    consulta por fila."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        filas = c.execute(
            "SELECT * FROM lotes WHERE stock > 0 ORDER BY producto_id, fecha_horneado"
        ).fetchall()
    por_producto = {}
    for r in filas:
        por_producto.setdefault(r["producto_id"], []).append(dict(r))
    return por_producto


@_safe
def agregar_lote(producto_id, cantidad, fecha_horneado=None):
    """
    Registra una hornada nueva. Si ya existe un lote de este producto con
    la MISMA fecha_horneado (ej. hornearon dos veces el mismo día), se
    suma a ese lote en vez de crear uno duplicado -- misma antigüedad,
    no tiene sentido distinguirlos. `fecha_horneado` en None = hoy.
    """
    fecha = fecha_horneado or date.today().isoformat()
    with _conn() as c:
        existente = c.execute(
            "SELECT id FROM lotes WHERE producto_id=? AND fecha_horneado=?",
            (producto_id, fecha)).fetchone()
        if existente:
            c.execute("UPDATE lotes SET stock = stock + ? WHERE id=?",
                      (cantidad, existente[0]))
        else:
            c.execute(
                "INSERT INTO lotes (producto_id, fecha_horneado, stock) VALUES (?, ?, ?)",
                (producto_id, fecha, cantidad))
        c.commit()


@_safe
def corregir_stock_lote(lote_id, nuevo_stock):
    """Corrige el conteo de UN lote puntual (ej. se rompieron unidades) --
    no crea ni fusiona lotes, ni toca su fecha, solo ajusta la cantidad."""
    with _conn() as c:
        c.execute("UPDATE lotes SET stock=? WHERE id=?", (nuevo_stock, lote_id))
        c.commit()


@_safe
def eliminar_lote(lote_id):
    """Da de baja un lote entero (ej. se tiró todo lo que quedaba de esa
    hornada). A diferencia de productos/insumos no hay "reactivar": un
    lote descartado no vuelve a aparecer."""
    with _conn() as c:
        c.execute("DELETE FROM lotes WHERE id=?", (lote_id,))
        c.commit()


# ── Descuento por antigüedad ────────────────────────────────────────────────
# El pan pierde frescura a los pocos días de horneado. En vez de que el
# usuario tenga que bajar el precio a mano (o crear un producto "de ayer")
# cada 2-3 días, se define una tabla chica de reglas (día -> % de
# descuento) y precio_vigente() la aplica sola, en el momento de vender.

@_safe
def get_reglas_descuento():
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in
                c.execute("SELECT * FROM reglas_descuento ORDER BY dias").fetchall()]


@_safe
def set_regla_descuento(dias, porcentaje):
    with _conn() as c:
        c.execute(
            "INSERT INTO reglas_descuento (dias, porcentaje) VALUES (?, ?) "
            "ON CONFLICT(dias) DO UPDATE SET porcentaje=excluded.porcentaje",
            (dias, porcentaje),
        )
        c.commit()


@_safe
def eliminar_regla_descuento(dias):
    with _conn() as c:
        c.execute("DELETE FROM reglas_descuento WHERE dias=?", (dias,))
        c.commit()


@_safe
def get_reglas_de_producto(producto_id):
    """Reglas propias de UN producto (para editarlas en el diálogo).
    No incluye el fallback a las generales -- eso lo resuelve precio_vigente()."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(
            "SELECT * FROM reglas_descuento_producto WHERE producto_id=? ORDER BY dias",
            (producto_id,)).fetchall()]


@_safe
def get_reglas_descuento_producto():
    """Todas las reglas por producto, agrupadas por producto_id -- para
    resolver el fallback de una lista completa de productos sin hacer una
    consulta por fila (ver precio_vigente())."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        filas = c.execute(
            "SELECT * FROM reglas_descuento_producto ORDER BY producto_id, dias"
        ).fetchall()
    por_producto = {}
    for r in filas:
        por_producto.setdefault(r["producto_id"], []).append(dict(r))
    return por_producto


@_safe
def set_regla_descuento_producto(producto_id, dias, porcentaje):
    with _conn() as c:
        c.execute(
            "INSERT INTO reglas_descuento_producto (producto_id, dias, porcentaje) "
            "VALUES (?, ?, ?) ON CONFLICT(producto_id, dias) "
            "DO UPDATE SET porcentaje=excluded.porcentaje",
            (producto_id, dias, porcentaje),
        )
        c.commit()


@_safe
def eliminar_regla_descuento_producto(producto_id, dias):
    with _conn() as c:
        c.execute("DELETE FROM reglas_descuento_producto WHERE producto_id=? AND dias=?",
                  (producto_id, dias))
        c.commit()


def precio_vigente(producto, reglas_generales, reglas_por_producto=None):
    """
    Precio efectivo hoy para `producto`. Si el producto tiene reglas
    propias en `reglas_por_producto` (dict producto_id -> lista, ver
    get_reglas_descuento_producto()), esas reemplazan por completo a las
    generales para ese producto; si no tiene ninguna, usa `reglas_generales`.
    En ambos casos se aplica la regla con mayor "dias" que sea <= la
    antigüedad real -- son escalones, no rangos: un producto de 5 días usa
    la regla más alta definida (ej. "día 3") en vez de no descontarse por
    no haber una regla exacta para "día 5". `producto["fecha_horneado"]`
    en None/vacío = antigüedad no trackeada, precio sin cambios.

    Devuelve (precio_con_descuento, dias_antiguedad, porcentaje_aplicado).
    Los dos últimos son None cuando no aplica ninguna regla.
    """
    if not producto.get("fecha_horneado"):
        return producto["precio"], None, None
    dias = (date.today() - date.fromisoformat(producto["fecha_horneado"])).days
    reglas = (reglas_por_producto or {}).get(producto["id"]) or reglas_generales
    aplicable = None
    for r in reglas:
        if r["dias"] <= dias:
            aplicable = r
    if aplicable is None:
        return producto["precio"], dias, None
    precio = round(producto["precio"] * (1 - aplicable["porcentaje"] / 100), 2)
    return precio, dias, aplicable["porcentaje"]


# ── Inventario (insumos) ──────────────────────────────────────────────────────
# Insumos = materias primas (harina, levadura, etc.), distinto de productos
# (los panes que se venden). Control manual de stock, sin vínculo con las
# ventas todavía -- ver "Pendiente" en CLAUDE.md/DOCUMENTACION.md para el
# descuento automático por receta al vender (a futuro, no implementado).
# stock es REAL (no INTEGER como productos): las cantidades de insumos se
# miden en kilos/litros, no en unidades enteras.

@_safe
def get_insumos(solo_activos=True):
    with _conn() as c:
        c.row_factory = sqlite3.Row
        sql = "SELECT * FROM insumos WHERE activo=1 ORDER BY nombre" if solo_activos \
              else "SELECT * FROM insumos ORDER BY nombre"
        return [dict(r) for r in c.execute(sql).fetchall()]


@_safe
def add_insumo(nombre, unidad, stock, stock_minimo=0):
    with _conn() as c:
        c.execute("INSERT INTO insumos (nombre, unidad, stock, stock_minimo) VALUES (?, ?, ?, ?)",
                  (nombre, unidad, stock, stock_minimo))
        c.commit()


@_safe
def update_insumo(id, nombre, unidad, stock_minimo):
    with _conn() as c:
        c.execute("UPDATE insumos SET nombre=?, unidad=?, stock_minimo=? WHERE id=?",
                  (nombre, unidad, stock_minimo, id))
        c.commit()


@_safe
def ajustar_stock_insumo(id, nuevo_stock):
    """
    Ajusta el stock y, ANTES de pisarlo, deja marcado con cuánto arrancó el
    día ese insumo -- de ahí sale la "sombra" del Inventario.

    La marca se renueva en el PRIMER ajuste de cada día: si ya es de hoy se
    respeta, así varios ajustes en la misma jornada siguen comparando contra
    el mismo punto de partida y no contra el ajuste anterior. Ejemplo: si a
    las 6 se baja de 20 a 15 y a las 9 de 15 a 12, la sombra dice 20 las dos
    veces, no 15.

    No se renueva por reloj a medianoche sino recién al tocar el insumo: un
    insumo que no se movió hoy queda con la marca del último día en que sí,
    y la pantalla no le dibuja sombra (no tendría nada que rastrear de hoy).
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    with _conn() as c:
        fila = c.execute("SELECT stock, fecha_inicial FROM insumos WHERE id=?", (id,)).fetchone()
        if fila is None:
            return
        stock_previo, fecha_inicial = fila
        if fecha_inicial != hoy:
            c.execute("UPDATE insumos SET stock_inicial_dia=?, fecha_inicial=? WHERE id=?",
                      (stock_previo, hoy, id))
        c.execute("UPDATE insumos SET stock=? WHERE id=?", (nuevo_stock, id))
        c.commit()


@_safe
def desactivar_insumo(id):
    with _conn() as c:
        c.execute("UPDATE insumos SET activo=0 WHERE id=?", (id,))
        c.commit()


@_safe
def reactivar_insumo(id):
    with _conn() as c:
        c.execute("UPDATE insumos SET activo=1 WHERE id=?", (id,))
        c.commit()


# ── Ventas ───────────────────────────────────────────────────────────────────

@_safe
def verificar_stock(items):
    """Devuelve lista de mensajes de error si algún item supera el stock
    disponible EN SU LOTE puntual (items trae "lote_id", no solo
    producto_id -- cada lote es una hornada distinta con su propio stock)."""
    errores = []
    with _conn() as c:
        c.row_factory = sqlite3.Row
        for item in items:
            row = c.execute(
                "SELECT p.nombre, l.stock FROM lotes l "
                "JOIN productos p ON p.id = l.producto_id WHERE l.id=?",
                (item["lote_id"],)).fetchone()
            if row and item["cantidad"] > row["stock"]:
                errores.append(f"'{row['nombre']}': solicitado {item['cantidad']}, disponible {row['stock']}")
    return errores


@_safe
def registrar_venta(items, pago=None):
    """
    items: lista de dicts con claves producto_id, lote_id, cantidad,
    precio_unitario, subtotal (y opcionalmente "nombre", solo para
    mensajes de error más claros). Descuenta el stock del LOTE
    correspondiente automáticamente y devuelve el id de la venta.

    `pago` es con cuánto pagó el cliente, y es opcional: None significa
    "no se registró" y el ticket omite las líneas de pago y cambio. No
    se valida contra el total acá -- eso lo hace la pantalla de venta,
    que es la que puede avisarle al vendedor a tiempo.

    El descuento de stock exige "stock >= cantidad" en el propio UPDATE:
    si dos ventas del mismo lote se disparan casi al mismo tiempo (por
    ejemplo, la app abierta dos veces sin querer), esto evita que el
    stock quede negativo. verificar_stock() ya hace una verificación
    previa para dar feedback rápido en la UI; esta es la garantía real
    a nivel de base de datos.
    """
    total = sum(i["subtotal"] for i in items)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        try:
            cur = c.execute("INSERT INTO ventas (fecha, total, pago) VALUES (?, ?, ?)",
                            (fecha, total, pago))
            venta_id = cur.lastrowid
            for i in items:
                # Costo interno del producto AL MOMENTO de la venta, congelado
                # acá mismo -- igual criterio que precio_unitario: si el costo
                # cambia después, esta línea no se altera. 0 = no había costo
                # cargado en ese momento (no "costo cero real"). El costo no
                # depende del lote (no se trackea costo por hornada), solo la
                # antigüedad/precio sí.
                fila_prod = c.execute(
                    "SELECT costo, precio FROM productos WHERE id=?", (i["producto_id"],)
                ).fetchone()
                costo_unitario = fila_prod[0] if fila_prod else 0
                costo_subtotal = costo_unitario * i["cantidad"]
                # Precio de lista y antigüedad de la tanda, también congelados:
                # `precio_unitario` ya viene con el descuento por antigüedad
                # aplicado (lo calcula precio_vigente() en la pantalla de
                # venta), así que sin guardar el de lista al lado se pierde
                # para siempre cuánto se resignó por rematar. La antigüedad se
                # lee del lote acá y no se deduce después: eliminar_lote() lo
                # borra físicamente. Ambos quedan en 0/NULL si falta el dato,
                # no se inventa un precio ni una edad.
                precio_lista = fila_prod[1] if fila_prod else 0
                lista_subtotal = precio_lista * i["cantidad"]
                fila_lote = c.execute(
                    "SELECT fecha_horneado FROM lotes WHERE id=?", (i["lote_id"],)
                ).fetchone()
                dias_antiguedad = None
                if fila_lote and fila_lote[0]:
                    dias_antiguedad = (date.today() - date.fromisoformat(fila_lote[0])).days
                c.execute(
                    "INSERT INTO detalle_venta (venta_id, producto_id, lote_id, cantidad,"
                    " precio_unitario, subtotal, costo_unitario, costo_subtotal,"
                    " precio_lista, lista_subtotal, dias_antiguedad)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (venta_id, i["producto_id"], i["lote_id"], i["cantidad"], i["precio_unitario"],
                     i["subtotal"], costo_unitario, costo_subtotal,
                     precio_lista, lista_subtotal, dias_antiguedad),
                )
                cur_stock = c.execute(
                    "UPDATE lotes SET stock = stock - ? WHERE id=? AND stock >= ?",
                    (i["cantidad"], i["lote_id"], i["cantidad"]),
                )
                if cur_stock.rowcount == 0:
                    nombre = i.get("nombre", f"id {i['producto_id']}")
                    raise DBError(
                        f"No hay suficiente stock de '{nombre}' para completar la venta "
                        "(puede haber cambiado desde que abriste el carrito). "
                        "Revisá el stock actual e intentá de nuevo."
                    )
        except Exception:
            c.rollback()
            raise
        c.commit()
    return venta_id


@_safe
def get_ventas():
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in
                c.execute("SELECT * FROM ventas ORDER BY fecha DESC").fetchall()]


@_safe
def get_venta(venta_id):
    """Una venta puntual por id (None si no existe). Usada para armar el
    ticket recién registrada la venta, sin recargar el listado completo."""
    with _conn() as c:
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM ventas WHERE id=?", (venta_id,)).fetchone()
        return dict(r) if r else None


@_safe
def anular_venta(venta_id, motivo):
    """
    Anula una venta y devuelve el stock vendido, sin borrar el registro
    (se conserva para el historial, marcada con motivo y fecha de anulación).

    Solo se puede anular mientras la venta sigue pendiente de corte
    (corte_id IS NULL): si ya fue incluida en un corte cerrado, anularla
    dejaría el total de ese corte sin ventas reales que lo sostengan, y un
    corte es un hecho contable que no debe moverse (ver hacer_corte()).
    """
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        c.row_factory = sqlite3.Row
        try:
            venta = c.execute("SELECT * FROM ventas WHERE id=?", (venta_id,)).fetchone()
            if venta is None:
                raise DBError("La venta no existe.")
            if venta["anulada"]:
                raise DBError("Esta venta ya está anulada.")
            if venta["corte_id"] is not None:
                raise DBError(
                    "Esta venta ya fue incluida en un corte de caja cerrado y no se puede anular."
                )
            detalle = c.execute(
                "SELECT producto_id, lote_id, cantidad FROM detalle_venta WHERE venta_id=?",
                (venta_id,)
            ).fetchall()
            for d in detalle:
                if d["lote_id"] is None:
                    # Venta de antes de que existiera el sistema de lotes --
                    # no hay forma de saber a qué hornada devolverle el
                    # stock, así que se omite en vez de inventar un lote.
                    continue
                c.execute("UPDATE lotes SET stock = stock + ? WHERE id=?",
                          (d["cantidad"], d["lote_id"]))
            c.execute(
                "UPDATE ventas SET anulada=1, motivo_anulacion=?, fecha_anulacion=? WHERE id=?",
                (motivo, fecha, venta_id)
            )
        except Exception:
            c.rollback()
            raise
        c.commit()


@_safe
def get_ventas_detalle_export():
    """
    Una fila por línea de venta (producto vendido dentro de una venta),
    con la fecha/hora EXACTA de esa venta (v.fecha) -- a diferencia del
    export de Cortes, que agrupa cantidades por producto dentro de cada
    corte y usa la fecha del corte, no la de cada venta individual.
    Pensado para analizar qué se vende más y a qué hora del día, no para
    cuadrar caja (para eso ya está el export de Cortes).

    Incluye ventas ya cortadas y pendientes por igual (no importa el
    estado del corte para este análisis); excluye ventas anuladas, porque
    esa mercadería no se vendió realmente.
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("""
            SELECT v.id AS venta_id, v.fecha, p.nombre AS producto,
                   dv.cantidad, dv.precio_unitario, dv.subtotal,
                   dv.costo_unitario, dv.costo_subtotal
            FROM   detalle_venta dv
            JOIN   ventas v ON v.id = dv.venta_id
            JOIN   productos p ON p.id = dv.producto_id
            WHERE  v.anulada = 0
            ORDER BY v.fecha
        """).fetchall()]


@_safe
def get_detalle_venta(venta_id):
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("""
            SELECT dv.cantidad, dv.precio_unitario, dv.subtotal,
                   dv.costo_unitario, dv.costo_subtotal, p.nombre
            FROM   detalle_venta dv
            JOIN   productos p ON p.id = dv.producto_id
            WHERE  dv.venta_id = ?
        """, (venta_id,)).fetchall()]


# ── Cortes ───────────────────────────────────────────────────────────────────
# Un corte es un cierre de caja: congela el total y el desglose por producto
# de todas las ventas que todavía no habían sido cortadas. Se pueden hacer
# varios cortes por día (ej. turno mañana / turno tarde).

def _resumen_pendiente(c):
    """Total, cantidad y desglose por producto de las ventas con corte_id NULL.
    El costo ya viene congelado por línea desde registrar_venta(); acá solo
    se suma, nunca se vuelve a consultar productos.costo (evita que un
    cambio de costo posterior mueva el desglose de un corte)."""
    c.row_factory = sqlite3.Row
    resumen = c.execute(
        "SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total "
        "FROM ventas WHERE corte_id IS NULL AND anulada = 0"
    ).fetchone()
    costo_row = c.execute("""
        SELECT COALESCE(SUM(dv.costo_subtotal), 0) AS costo_total,
               COALESCE(SUM(CASE WHEN dv.precio_lista > 0 THEN dv.lista_subtotal END), 0) AS lista_total,
               COALESCE(SUM(CASE WHEN dv.precio_lista > 0 THEN dv.subtotal END), 0) AS lista_cobrado
        FROM   detalle_venta dv
        JOIN   ventas v ON v.id = dv.venta_id
        WHERE  v.corte_id IS NULL AND v.anulada = 0
    """).fetchone()
    desglose = c.execute("""
        SELECT p.nombre AS nombre, SUM(dv.cantidad) AS cantidad, SUM(dv.subtotal) AS total,
               SUM(dv.costo_subtotal) AS costo_total,
               COALESCE(SUM(CASE WHEN dv.precio_lista > 0 THEN dv.lista_subtotal END), 0) AS lista_total,
               COALESCE(SUM(CASE WHEN dv.precio_lista > 0 THEN dv.subtotal END), 0) AS lista_cobrado
        FROM   detalle_venta dv
        JOIN   ventas v ON v.id = dv.venta_id
        JOIN   productos p ON p.id = dv.producto_id
        WHERE  v.corte_id IS NULL AND v.anulada = 0
        GROUP BY p.nombre
        ORDER BY total DESC
    """).fetchall()
    return {
        "cantidad_ventas": resumen["cantidad"],
        "total_ventas": resumen["total"],
        "costo_total": costo_row["costo_total"],
        "lista_total": costo_row["lista_total"],
        "lista_cobrado": costo_row["lista_cobrado"],
        "desglose": [dict(r) for r in desglose],
    }


@_safe
def preview_corte():
    """Vista previa (sin guardar nada) de lo que incluiría el próximo corte."""
    with _conn() as c:
        return _resumen_pendiente(c)


@_safe
def hacer_corte():
    """
    Cierra todas las ventas pendientes (corte_id IS NULL) en un corte nuevo:
    guarda total, cantidad y desglose por producto, y marca esas ventas
    como incluidas. Devuelve el id del corte creado, o None si no había
    ventas pendientes (no se crean cortes vacíos).
    """
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        try:
            resumen = _resumen_pendiente(c)
            if resumen["cantidad_ventas"] == 0:
                return None

            cur = c.execute(
                "INSERT INTO cortes (fecha, total_ventas, cantidad_ventas, costo_total,"
                " lista_total, lista_cobrado) VALUES (?, ?, ?, ?, ?, ?)",
                (fecha, resumen["total_ventas"], resumen["cantidad_ventas"],
                 resumen["costo_total"], resumen["lista_total"], resumen["lista_cobrado"]),
            )
            corte_id = cur.lastrowid
            for item in resumen["desglose"]:
                c.execute(
                    "INSERT INTO corte_detalle (corte_id, nombre_producto, cantidad, total,"
                    " costo_total, lista_total, lista_cobrado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (corte_id, item["nombre"], item["cantidad"], item["total"],
                     item["costo_total"], item["lista_total"], item["lista_cobrado"]),
                )
            c.execute(
                "UPDATE ventas SET corte_id = ? WHERE corte_id IS NULL AND anulada = 0",
                (corte_id,)
            )
        except Exception:
            c.rollback()
            raise
        c.commit()
    return corte_id


@_safe
def get_cortes():
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in
                c.execute("SELECT * FROM cortes ORDER BY fecha DESC").fetchall()]


@_safe
def get_resumen_analisis(desde=None, hasta=None):
    """
    Los tres números de cabecera de Análisis, sobre los cortes del rango
    (mismo criterio de fecha que get_ranking_productos): cuánto entró,
    cuánto se resignó rematando pan viejo, y qué margen quedó.

    El "rematado" sale de restar `lista_total - lista_cobrado`, dos sumas
    que hacer_corte() calcula sobre EXACTAMENTE las mismas líneas (las que
    tienen precio de lista guardado). No se puede usar `total_ventas` como
    término de la resta: incluye también las líneas sin el dato, y en
    cualquier corte mezclado el resultado sería negativo y sin sentido.

    Las ventas anteriores a la columna `precio_lista` no lo guardaron y no
    hay forma de reconstruirlo, así que se devuelven aparte
    `cortes_totales` y `cortes_con_lista`: si no coinciden, la pantalla
    avisa sobre cuántos cortes está hablando en vez de presentar un
    remate subestimado como si fuera el total. Mismo criterio que el
    costo: dato faltante = "sin datos", nunca "cero".

    El margen se devuelve en pesos Y en porcentaje sobre lo vendido
    (`margen_pct`): dos productos con el mismo margen en $ pueden ser
    negocios muy distintos si uno factura el triple que el otro, y la
    pregunta "¿cómo va el negocio?" se contesta mejor con las dos.
    Ambos se calculan sobre TODO lo vendido, incluyendo las líneas sin
    costo cargado -- eso los deja optimistas, así que se devuelve además
    `sin_costo_total` / `sin_costo_nombres` (cuánto y de qué productos)
    para que la pantalla pueda avisarlo. Se prefirió eso a calcular el
    porcentaje solo sobre la porción con costo: el $ y el % quedarían
    medidos sobre bases distintas y no se podrían leer juntos.
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        # Se arma dos veces porque la segunda consulta hace JOIN y necesita
        # la fecha calificada con el alias del corte (`co.fecha`); los
        # parámetros son los mismos para las dos.
        def _cond(col):
            cond = "1=1"
            if desde:
                cond += f" AND {col} >= ?"
            if hasta:
                cond += f" AND {col} <= ?"
            return cond

        params = []
        if desde:
            params.append(desde)
        if hasta:
            params.append(hasta + " 23:59:59")
        cond = _cond("fecha")
        fila = c.execute(f"""
            SELECT COUNT(*) AS cortes_totales,
                   COALESCE(SUM(total_ventas), 0) AS total,
                   COALESCE(SUM(costo_total), 0) AS costo_total,
                   COALESCE(SUM(lista_total), 0) AS lista_total,
                   COALESCE(SUM(lista_cobrado), 0) AS lista_cobrado,
                   COALESCE(SUM(CASE WHEN lista_total > 0 THEN 1 ELSE 0 END), 0) AS cortes_con_lista
            FROM   cortes WHERE {cond}
        """, params).fetchone()
        d = dict(fila)
        d["margen"] = d["total"] - d["costo_total"]
        d["margen_pct"] = (d["margen"] / d["total"] * 100) if d["total"] else 0
        d["rematado"] = d["lista_total"] - d["lista_cobrado"]
        d["rematado_pct"] = (d["rematado"] / d["lista_total"] * 100) if d["lista_total"] else 0

        # Qué parte de lo vendido en el rango no tiene costo cargado. Se
        # mide en plata (no en cantidad de productos): lo que ensucia el
        # margen es cuánto facturaron esas líneas, no cuántas son.
        hueco = c.execute(f"""
            SELECT COALESCE(SUM(cd.total), 0) AS sin_costo_total,
                   GROUP_CONCAT(DISTINCT cd.nombre_producto) AS nombres
            FROM   corte_detalle cd
            JOIN   cortes co ON co.id = cd.corte_id
            WHERE  cd.costo_total <= 0 AND {_cond("co.fecha")}
        """, params).fetchone()
        d["sin_costo_total"] = hueco["sin_costo_total"]
        d["sin_costo_nombres"] = sorted(
            (hueco["nombres"] or "").split(",")) if hueco["nombres"] else []
        return d


@_safe
def get_ranking_productos(desde=None, hasta=None):
    """
    Cantidad y total vendido por producto, sumado a través de todos los
    cortes cuya fecha (de CORTE, no de cada venta) cae en [desde, hasta]
    -- ambos en ISO "AAAA-MM-DD", ambos extremos inclusive, None = sin
    límite en ese extremo. Ordenado de mayor a menor cantidad vendida.

    Pensado para el gráfico "producto más vendido" en views/graficos.py.
    Solo cuenta ventas ya incluidas en algún corte (corte_detalle no
    existe para ventas todavía pendientes de cortar).

    Cada fila incluye "margen" = total - costo_total, calculado acá (no
    guardado). costo_total == 0 significa que ninguna venta de ese
    producto en el rango tenía costo cargado -- el llamador (el toggle
    "Margen ($)" del ranking) lo trata como "sin datos", no como margen
    100%.

    También "pleno_pct" = qué porcentaje del valor de lista se terminó
    cobrando (100 = nunca se remató; 60 = de cada $100 de precio de lista
    entraron $60). Se mide en plata y no en unidades a propósito: rematar
    dos facturas caras pesa más que rematar dos bolillos, y lo que se
    quiere ver es cuánto cuesta el sobrante, no cuántas piezas fueron.
    None cuando el producto no tiene ninguna venta con precio de lista
    guardado -- mismo criterio de "sin datos" que el costo.
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        sql = """
            SELECT cd.nombre_producto AS nombre,
                   SUM(cd.cantidad) AS cantidad,
                   SUM(cd.total) AS total,
                   SUM(cd.costo_total) AS costo_total,
                   SUM(cd.lista_total) AS lista_total,
                   SUM(cd.lista_cobrado) AS lista_cobrado
            FROM   corte_detalle cd
            JOIN   cortes co ON co.id = cd.corte_id
            WHERE  1=1
        """
        params = []
        if desde:
            sql += " AND co.fecha >= ?"
            params.append(desde)
        if hasta:
            sql += " AND co.fecha <= ?"
            params.append(hasta + " 23:59:59")
        sql += " GROUP BY cd.nombre_producto ORDER BY cantidad DESC"
        filas = [dict(r) for r in c.execute(sql, params).fetchall()]
        for f in filas:
            f["margen"] = f["total"] - f["costo_total"]
            # El margen en % (sobre lo que facturó ESE producto) contesta
            # una pregunta distinta al margen en $: un producto puede dejar
            # poca plata en total y ser el más eficiente de la lista, o al
            # revés. Se devuelve como dato de la fila en vez de una quinta
            # métrica del toggle -- el ranking ya está al límite de ancho
            # (ver CLAUDE.md), así que se muestra junto al $ en la etiqueta
            # de cada barra. None con costo sin cargar, igual que el resto.
            f["margen_pct"] = (f["margen"] / f["total"] * 100
                               if f["costo_total"] > 0 and f["total"] else None)
            f["pleno_pct"] = (f["lista_cobrado"] / f["lista_total"] * 100
                              if f["lista_total"] else None)
        return filas


@_safe
def get_corte_detalle(corte_id):
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(
            "SELECT nombre_producto, cantidad, total, costo_total FROM corte_detalle "
            "WHERE corte_id = ? ORDER BY total DESC",
            (corte_id,),
        ).fetchall()]


@_safe
def deshacer_ultimo_corte():
    """
    Deshace el corte más reciente (mayor id): reabre sus ventas
    (corte_id vuelve a NULL, quedan pendientes de cortar de nuevo) y borra
    el corte junto con su detalle. Solo se permite para el corte más
    reciente -- deshacer uno intermedio dejaría un hueco en la cronología
    de cortes (uno "salteado" entre dos que sí quedaron).
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        try:
            ultimo = c.execute("SELECT * FROM cortes ORDER BY id DESC LIMIT 1").fetchone()
            if ultimo is None:
                raise DBError("No hay ningún corte para deshacer.")
            corte_id = ultimo["id"]
            c.execute("UPDATE ventas SET corte_id = NULL WHERE corte_id = ?", (corte_id,))
            c.execute("DELETE FROM corte_detalle WHERE corte_id = ?", (corte_id,))
            c.execute("DELETE FROM cortes WHERE id = ?", (corte_id,))
        except Exception:
            c.rollback()
            raise
        c.commit()
    return corte_id


