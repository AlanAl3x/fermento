# Genera los assets de marca (logo Fermento) usados en la app: el
# recorte nítido para el encabezado de la barra lateral, el ícono de
# ventana/barra de tareas (.ico), y la marca de agua de fondo (emblema
# a baja opacidad, sangrando por el borde inferior de la barra lateral).
#
# Todo se deriva de FermentoLogo.jpeg en la raíz del proyecto. Si el
# archivo no está presente, las funciones devuelven None y quien las
# llama debe mostrar el texto de respaldo en su lugar (ver main.py).

from pathlib import Path

from PIL import Image, ImageEnhance
import customtkinter as ctk

import rutas
from views import theme

# El logo y el ícono son parte del PROGRAMA, no de los datos: se reemplazan
# junto con el .exe en cada actualización, así que van en la carpeta del
# ejecutable (`rutas.APP_DIR`) y no en la de datos (`rutas.BASE_DIR`, que es
# donde viven la base, los backups y los tickets). Antes esta lógica estaba
# duplicada acá con su propio `BASE_DIR`; ahora vive una sola vez en
# `rutas.py`, donde también se decide dónde van los datos -- la distinción
# entre "lo que se actualiza" y "lo que no se toca nunca" se lee de un lugar.
_APP_DIR = rutas.APP_DIR or Path(__file__).resolve().parent.parent

LOGO_PATH = _APP_DIR / "FermentoLogo.jpeg"
ICON_PATH = _APP_DIR / "assets" / "fermento.ico"

# Cajas de recorte como fracción (izq, arriba, der, abajo) del logo original.
_CAJA_WORDMARK = (0.0, 0.0, 1.0, 0.87)    # emblema + "FERMENTO", sin subtítulo
_CAJA_EMBLEMA = (0.26, 0.0, 0.74, 0.64)   # solo el emblema de trigo


def _recortar(im, caja):
    w, h = im.size
    l, t, r, b = caja
    return im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))


def logo_sidebar(ancho=128):
    """CTkImage del emblema + "FERMENTO" para el encabezado de la barra lateral."""
    if not LOGO_PATH.exists():
        return None
    im = _recortar(Image.open(LOGO_PATH), _CAJA_WORDMARK)
    alto = round(ancho * im.height / im.width)
    return ctk.CTkImage(light_image=im, dark_image=im, size=(ancho, alto))


# Los tamaños que Windows saca de un .ico según dónde lo dibuje: 16 en la
# barra de título, 32 en la barra de tareas, 48 en el explorador, 256 en el
# escritorio con "iconos grandes" y en Alt+Tab. **Si un tamaño no está en el
# archivo, Windows estira el más grande que encuentre**, y ahí es donde un
# ícono se ve borroso.
_ICO_TAMANOS = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _emblema_cuadrado(lado=256):
    """El emblema centrado en un lienzo cuadrado, listo para ser ícono.

    Dos cosas que hay que hacer a mano y explican por qué esto no es un
    `save()` directo:

    1. **El recorte del emblema NO es cuadrado** (`_CAJA_EMBLEMA` es más ancha
       que alta), y Pillow respeta la relación de aspecto al guardar un .ico:
       pedirle (16,16) devolvía (16,15), (48,48) devolvía (48,44). Windows
       los deforma para encajarlos en su casillero cuadrado.
    2. **Pillow no agranda**: los tamaños más grandes que la imagen fuente
       los descarta en silencio. Por eso el 256 pedido no estaba en el
       archivo aunque figurara en la lista. Hay que escalar ANTES.

    El fondo se toma del pixel de la esquina del propio recorte (el negro del
    logo) en vez de escribir un color a mano: así el emblema se funde con el
    lienzo sin dejar un borde visible, aunque el JPEG tenga algo de ruido y
    su negro no sea exactamente #000000.
    """
    emblema = _recortar(Image.open(LOGO_PATH), _CAJA_EMBLEMA).convert("RGB")
    fondo = emblema.getpixel((0, 0))

    # 84% del lienzo: el ícono necesita aire alrededor o a 16px queda pegado
    # a los bordes y se lee como una mancha.
    util = int(lado * 0.84)
    escala = min(util / emblema.width, util / emblema.height)
    escalado = emblema.resize(
        (max(1, round(emblema.width * escala)), max(1, round(emblema.height * escala))),
        Image.LANCZOS)

    lienzo = Image.new("RGB", (lado, lado), fondo)
    lienzo.paste(escalado, ((lado - escalado.width) // 2, (lado - escalado.height) // 2))
    return lienzo


def icono_ventana(regenerar=False):
    """Genera (si hace falta) el .ico de la ventana y devuelve su ruta.

    Nunca levanta: instalada, la app puede quedar en una carpeta donde el
    usuario no tiene permiso de escritura, y quedarse sin ícono no es motivo
    para no abrir. `main.py` llama a esta función antes de que exista
    cualquier widget que pueda mostrar un error, así que un fallo acá sería
    una app que directamente no arranca y no dice por qué.
    """
    if not LOGO_PATH.exists():
        return None
    try:
        if regenerar or not ICON_PATH.exists():
            ICON_PATH.parent.mkdir(exist_ok=True)
            _emblema_cuadrado().save(ICON_PATH, sizes=_ICO_TAMANOS)
    except OSError:
        return ICON_PATH if ICON_PATH.exists() else None
    return ICON_PATH


def marca_agua_sidebar(ancho=170, alto=720):
    """
    Emblema a baja opacidad y sin difuminar, sangrando por el borde
    inferior de la barra lateral. Se genera sobre un lienzo del color de
    la barra lateral para que el borde se funda con el fondo sin dejar
    un halo visible.

    Nítido en vez de difuminado a propósito: el emblema es un dibujo de
    líneas finas, y un blur notorio lo vuelve una mancha irreconocible
    en vez de una textura de marca (se probaron ambas variantes).
    """
    if not LOGO_PATH.exists():
        return None
    emblema = _recortar(Image.open(LOGO_PATH), _CAJA_EMBLEMA).convert("RGB")
    escala = round(ancho * 2.6)
    emblema = emblema.resize((escala, round(escala * emblema.height / emblema.width)))

    lienzo = Image.new("RGB", (ancho, alto), theme.rgb(theme.BG_SIDEBAR))
    x = (ancho - emblema.width) // 2
    y = alto - round(emblema.height * 0.72)
    lienzo.paste(emblema, (x, y))

    # Reducir el brillo sobre un lienzo casi negro equivale a bajar la
    # opacidad del emblema: sin esto se ve como un logo "gigante", no
    # como una textura de fondo sutil.
    tenue = ImageEnhance.Brightness(lienzo).enhance(0.16)
    return ctk.CTkImage(light_image=tenue, dark_image=tenue, size=(ancho, alto))
