"""Dónde vive todo lo que la app escribe en disco.

Está en un módulo aparte, y no dentro de `database.py`, porque lo necesitan
tanto la base como el registro de errores (`registro.py`), y `database`
importa a `registro`: si `BASE_DIR` viviera en la base, sería un import
circular. Tenerlo una sola vez también evita lo que sería un bug silencioso
y molesto de encontrar: que el log termine en una carpeta distinta de la
base de datos.

**Los datos NO viven junto al ejecutable, sino en una carpeta hermana.**
Instalada, la app queda así (dentro de la carpeta personal del usuario, no
en `C:\\` ni en Documentos -- ver DOCUMENTACION.md para el porqué):

    %USERPROFILE%\\Fermento\\
    ├─ Datos\\        <- lo que escribe la app (esta carpeta, BASE_DIR)
    └─ Programa\\     <- el .exe y sus librerías (APP_DIR)

La razón es la actualización: para instalar una versión nueva se borra
`Programa\\` entera y se descomprime la nueva encima. Si la base viviera ahí
adentro, cada actualización se llevaría puesto el historial de ventas —
o dependería de que quien actualiza se acuerde de rescatarla primero, que
es exactamente la clase de cosa que sale mal una vez y no se puede deshacer.
Con las carpetas separadas, el paquete de actualización no contiene ningún
dato y no hay forma de pisar nada.

Congelada (`sys.frozen`) la app corre como .exe y `__file__` apunta adentro
del bundle temporal de PyInstaller, que Windows borra al cerrar: hay que
colgarse de `sys.executable`, no de `__file__`.

En desarrollo (sin congelar) `BASE_DIR` es la carpeta del proyecto, igual
que siempre: la base de pruebas queda al lado del código y no se mezcla con
la instalación real de la panadería.
"""

import os
import sys
from pathlib import Path

#: Carpeta del ejecutable. `None` en desarrollo (no hay .exe).
APP_DIR = None


def _usable(carpeta):
    """¿Se puede crear y escribir realmente en esta carpeta?

    No alcanza con `mkdir`: en `Program Files` la carpeta se crea pero
    escribir adentro falla, y el error aparecería recién al intentar guardar
    la primera venta. Se prueba con un archivo de verdad, que es la única
    respuesta confiable.
    """
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        prueba = carpeta / ".permiso"
        prueba.touch()
        prueba.unlink()
        return True
    except OSError:
        return False


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
    _hermana = APP_DIR.parent / "Datos"
    if _usable(_hermana):
        BASE_DIR = _hermana
    else:
        # Plan B para el caso "lo instalaron en Program Files" (o en
        # cualquier carpeta de solo lectura): los datos van al perfil del
        # usuario, que siempre es escribible. Es un fallback, no el lugar
        # preferido -- ahí son más difíciles de encontrar para copiarlos a
        # un USB, y por eso Ajustes muestra SIEMPRE la ruta real y tiene un
        # botón para abrirla. Sin eso, este plan B se vería desde el
        # mostrador como "se borraron todas las ventas".
        BASE_DIR = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "Fermento" / "Datos"
        _usable(BASE_DIR)
else:
    BASE_DIR = Path(__file__).parent
