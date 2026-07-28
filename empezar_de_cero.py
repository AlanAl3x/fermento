"""Vacía la base de datos para arrancar con datos reales.

Para qué: `panaderia.db` tenía una demo de 30 días (ventas, cortes y tandas
inventadas, generadas para poder revisar la app con las pantallas llenas).
Antes de empezar a vender de verdad había que sacarla, o los reportes de la
primera semana real iban a venir mezclados con plata que nunca existió.

**Ya cumplió su función: se ejecutó el 2026-07-26 y la base arrancó de cero.**
El respaldo de la demo quedó en `backups/ANTES-DE-BORRAR_2026-07-26_*_demo.db`.
Queda acá por si alguna vez hay que volver a vaciar la base — y si se corre de
nuevo, ahora borraría datos REALES.

Se corre a mano, con la app cerrada:

    python empezar_de_cero.py

Qué hace, en orden:
  1. Muestra qué hay adentro, para que se vea qué se está por perder.
  2. Pide escribir BORRAR. No hay forma de saltear la confirmación a
     propósito: se usa una vez en la vida y el error no se puede deshacer.
  3. Deja un respaldo en `backups/`, con nombre `ANTES-DE-BORRAR_...`. Ese
     prefijo lo mantiene FUERA de la rotación automática de 30 copias (que
     solo borra las que se llaman `panaderia_*.db`), así que no se pierde
     con el tiempo como sí pasa con los backups de cada arranque.
  4. Borra todas las filas de todas las tablas y reinicia los contadores de
     id: la primera venta real es la #1, no la #302.
  5. Compacta el archivo y verifica que no haya quedado ni una fila.

**No borra el archivo ni toca la estructura de las tablas**, solo su
contenido. La app abre después de esto exactamente igual que siempre.

Cerrá la app antes de correrlo.
"""

import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import database as db

CONFIRMACION = "BORRAR"

# Las tablas NO van en una lista fija a propósito: se leen de la base misma.
# Si mañana se agrega una tabla (por ejemplo "recetas", que ya está en los
# pendientes), una lista escrita a mano la dejaría afuera en silencio y el
# arranque "de cero" quedaría con datos viejos adentro.
def _tablas(c):
    return [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _conteos(ruta):
    with closing(sqlite3.connect(ruta)) as c:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _tablas(c)}


def _respaldar(ruta, motivo="demo"):
    """Copia fuera de la rotación automática. Devuelve la ruta del respaldo."""
    import shutil
    destino_dir = ruta.parent / "backups"
    destino_dir.mkdir(exist_ok=True)
    destino = destino_dir / f"ANTES-DE-BORRAR_{datetime.now():%Y-%m-%d_%H-%M-%S}_{motivo}.db"
    shutil.copy2(ruta, destino)
    return destino


def _vaciar(ruta):
    with closing(sqlite3.connect(ruta)) as c:
        # Las tablas se vacían en orden alfabético, que NO respeta las
        # dependencias (se borran los cortes antes que las ventas que los
        # referencian). Acá eso da igual porque no queda nada apuntando a
        # nada, pero con las claves foráneas encendidas cada DELETE se
        # miraría de a uno y fallaría. Se apagan explícitamente en vez de
        # confiar en que vengan apagadas por defecto.
        c.execute("PRAGMA foreign_keys = OFF")
        try:
            for t in _tablas(c):
                c.execute(f"DELETE FROM {t}")
            # Reinicia los AUTOINCREMENT. Sin esto la primera venta real
            # seguiría numerada después de la última de la demo.
            if c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                         "AND name='sqlite_sequence'").fetchone():
                c.execute("DELETE FROM sqlite_sequence")
        except Exception:
            c.rollback()
            raise
        c.commit()
        # VACUUM tiene que ir fuera de la transacción; devuelve al disco el
        # espacio que ocupaba la demo.
        c.execute("VACUUM")


def main():
    # El argumento opcional existe para poder PROBAR el script sobre una
    # copia sin arriesgar la base real. Sin argumento apunta a la de verdad.
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else db.DB_PATH

    if not ruta.exists():
        print(f"No existe {ruta}. Nada que borrar: la app la crea sola al abrir.")
        return 0

    conteos = _conteos(ruta)
    if not any(conteos.values()):
        print(f"{ruta} ya está vacía. No hay nada que hacer.")
        return 0

    print(f"\nBase: {ruta}")
    print("\nEsto es lo que se va a borrar:\n")
    for tabla, n in conteos.items():
        print(f"   {tabla:<28} {n:>6}")

    with closing(sqlite3.connect(ruta)) as c:
        total = c.execute(
            "SELECT COALESCE(SUM(total), 0) FROM ventas WHERE anulada = 0").fetchone()[0]
        rango = c.execute("SELECT MIN(fecha), MAX(fecha) FROM ventas").fetchone()
    if rango[0]:
        print(f"\n   {rango[0][:10]} a {rango[1][:10]}, ${total:,.2f} facturados.")

    print("\nSe va a guardar un respaldo antes de borrar, pero la base va a")
    print("quedar vacía como el primer día. Esto no se puede deshacer desde la app.")
    try:
        respuesta = input(f"\nEscribí {CONFIRMACION} para continuar (cualquier otra cosa cancela): ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelado. No se tocó nada.")
        return 1
    if respuesta.strip() != CONFIRMACION:
        print("Cancelado. No se tocó nada.")
        return 1

    respaldo = _respaldar(ruta)
    print(f"\nRespaldo guardado en:\n   {respaldo}")

    _vaciar(ruta)

    # Verificar, no asumir: si algo quedó, es mejor enterarse ahora que
    # descubrirlo dentro de un mes con los reportes contaminados.
    quedaron = {t: n for t, n in _conteos(ruta).items() if n}
    if quedaron:
        print("\nATENCIÓN: quedaron filas sin borrar:", quedaron)
        print(f"La base NO quedó limpia. El respaldo está intacto en {respaldo}")
        return 1

    print("\nListo. La base quedó vacía y los contadores en cero:")
    print("la primera venta real va a ser la #1.")
    print("\nAl abrir la app hay que cargar los productos y los insumos reales")
    print("(Productos → + Agregar producto, e Inventario → + Agregar insumo),")
    print("y revisar las reglas de descuento por antigüedad en Ajustes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
