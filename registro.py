"""Registro de errores a archivo.

Sin esto un error que se escape de un `try` queda **invisible**: la app se
distribuye como .exe sin consola, así que el traceback que Python o Tkinter
imprimen en stderr no lo ve nadie. Desde el mostrador el síntoma es "apreté
el botón y no hizo nada" o "se cerró sola", y no queda con qué diagnosticar.

Escribe en `panaderia_error.log`, al lado de la base de datos. Rota al llegar
a 1 MB y conserva 3 archivos viejos: en años de uso el log no puede crecer
sin techo, pero tampoco sirve uno que se borre entero justo cuando hacía
falta lo de ayer.

Criterio general: **no poder registrar nunca puede romper la app**. Todas las
fallas de este módulo (carpeta de solo lectura, disco lleno, permisos) se
tragan en silencio -- es preferible una app que anda sin log que una que no
arranca por culpa del log.
"""

import logging
import logging.handlers
import sys
import threading
import traceback

from rutas import BASE_DIR

LOG_PATH = BASE_DIR / "panaderia_error.log"

_log = logging.getLogger("fermento")
_iniciado = False


def iniciar():
    """Deja el archivo de log listo y engancha los errores que no pasan por
    Tkinter (hilo principal y otros hilos). Idempotente: se puede llamar
    varias veces sin duplicar handlers ni líneas repetidas en el archivo."""
    global _iniciado
    if _iniciado:
        return
    _iniciado = True

    _log.setLevel(logging.INFO)
    _log.propagate = False  # que no salga además por stderr
    try:
        handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return  # sin log, pero la app arranca igual
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s"))
    _log.addHandler(handler)
    _log.info("=== Fermento iniciado ===")

    def _no_atendido(tipo, valor, tb):
        _log.error("Error no atendido:\n%s", _formatear(tipo, valor, tb))

    sys.excepthook = _no_atendido

    def _no_atendido_en_hilo(args):
        _log.error("Error no atendido en un hilo:\n%s",
                   _formatear(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = _no_atendido_en_hilo


def enganchar_tk(ventana):
    """Engancha los errores de los callbacks de Tkinter, que es por donde se
    escapa casi todo en una app de ventanas: lo que revienta adentro de un
    botón, un `bind` o un `after` lo atrapa Tk, que por defecto lo imprime en
    stderr y sigue como si nada. Además de anotarlo, se le avisa al usuario:
    si no, el click simplemente no hace nada y parece que la app se colgó."""
    iniciar()

    def _en_callback(tipo, valor, tb):
        _log.error("Error no atendido en la interfaz:\n%s", _formatear(tipo, valor, tb))
        _avisar(valor)

    ventana.report_callback_exception = _en_callback


def error(mensaje):
    """Anota un error ya atendido (los `DBError` que la pantalla muestra en un
    messagebox). Se registra igual porque el mensaje amigable que ve el
    usuario pierde el traceback, que es justamente lo que sirve después."""
    iniciar()
    _log.error(mensaje, exc_info=True)


def _formatear(tipo, valor, tb):
    return "".join(traceback.format_exception(tipo, valor, tb))


def _avisar(exc):
    # `messagebox` se importa acá adentro y no arriba: este módulo lo usa
    # también `database.py`, que no tiene por qué arrastrar Tkinter.
    try:
        from tkinter import messagebox
        messagebox.showerror(
            "Error inesperado",
            "Ocurrió un error inesperado y la acción no se completó.\n\n"
            f"Quedó registrado en:\n{LOG_PATH}\n\n"
            f"Detalle técnico: {type(exc).__name__}: {exc}")
    except Exception:
        pass  # si ni el aviso se puede mostrar, al menos ya quedó anotado
