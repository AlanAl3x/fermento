# Genera el ticket de una venta como PDF con el tamaño exacto del rollo
# de la impresora (80mm de ancho, alto variable según lo que se vendió) y
# lo abre con el visor de PDF predeterminado de Windows, desde donde el
# usuario lo imprime (o solo lo mira, si el cliente no quería papel).
#
# Cada PDF queda guardado en tickets/ junto al .exe (misma lógica de
# rutas que panaderia.db y backups/), como respaldo digital del ticket.
# Solo se genera cuando el usuario lo pide -- no en cada venta.
#
# El logo JPEG (líneas doradas sobre fondo negro) no se puede estampar
# tal cual en una hoja blanca -- se imprimiría como un bloque sólido de
# tinta. _logo_emblema() lo reinterpreta para papel: el brillo de cada
# pixel (las líneas doradas) pasa a ser opacidad de tinta negra y el
# fondo queda transparente, así solo se imprimen las líneas del emblema.

import io
import os

from views import formato
import database as db

TICKETS_DIR = db.BASE_DIR / "tickets"

# ── Medidas del papel ────────────────────────────────────────────────────────
# El PDF se arma del ancho EXACTO del rollo, no en A4. Ese es todo el
# arreglo del ticket ilegible de agosto 2026: la versión anterior era una
# hoja A4 con una columna de 120mm centrada, y al mandarla al rollo el
# visor la achicaba entera para que entrara -- letra, márgenes y logo
# reducidos a menos de la mitad, en proporciones de hoja de oficina. Con
# la página del tamaño del papel no hay nada que escalar y los tamaños de
# fuente de acá abajo son los que salen impresos.
#
# **Para un rollo de otro ancho, cambiar SOLO este número**: todo el
# armado se calcula a partir de él (el resto son márgenes y altos de
# renglón). Con 58mm hay que revisar además los tamaños de fuente
# grandes, que fueron elegidos para 80mm.
ANCHO_ROLLO_MM = 80
_MARGEN_LAT_MM = 4    # zona no imprimible de las térmicas + aire visual
_MARGEN_SUP_MM = 5
# Cola al pie: las térmicas con cortador cortan unos milímetros más abajo
# de donde termina la página, y las que no lo tienen dejan el final del
# ticket adentro del mecanismo. Sin este margen, el "sin valor fiscal"
# queda partido por el corte o no llega a salir.
_MARGEN_INF_MM = 12

# Dirección del local, debajo del nombre. Vacío ("") = no se imprime la
# línea; el ticket sale igual, un renglón más corto.
DIRECCION = "Virreyes 10, Valle del Conde"

_NORMAL = "Helvetica"
_BOLD = "Helvetica-Bold"


class TicketError(Exception):
    """Error al generar/abrir un ticket, con mensaje pensado para el usuario."""


def generar_y_abrir(venta, detalle):
    """
    Genera el PDF del ticket de una venta y lo abre con el visor de PDF
    del sistema. Devuelve la ruta del archivo generado.

    venta: dict con las columnas de la tabla `ventas` (id, fecha, total,
    pago, anulada...). detalle: filas de get_detalle_venta() (nombre,
    cantidad, precio_unitario, subtotal).
    """
    # Import adentro de la función a propósito: si reportlab faltara
    # (entorno de desarrollo sin `pip install`), debe fallar solo la
    # generación del ticket con un mensaje claro, no el arranque de
    # toda la app por un import a nivel de módulo.
    try:
        from reportlab.pdfgen import canvas  # noqa: F401 (verifica la dependencia)
    except ImportError:
        raise TicketError(
            "Falta la librería 'reportlab' para generar tickets en PDF.\n"
            "Instalala con: pip install reportlab"
        )

    try:
        TICKETS_DIR.mkdir(exist_ok=True)
        ruta = TICKETS_DIR / _nombre_archivo(venta)
        _dibujar_pdf(ruta, venta, detalle)
    except OSError as e:
        raise TicketError(f"No se pudo generar el ticket.\nDetalle técnico: {e}")

    try:
        os.startfile(ruta)
    except OSError as e:
        raise TicketError(
            "El ticket se generó pero no se pudo abrir el visor de PDF.\n"
            f"Quedó guardado en:\n{ruta}\n"
            f"Detalle técnico: {e}"
        )
    return ruta


def _nombre_archivo(venta):
    # Fecha en ISO (no DD-MM-AAAA) para que los archivos ordenen
    # cronológicamente por nombre en el explorador -- misma excepción a
    # propósito que el CSV de cortes (ver views/cortes.py). Reimprimir
    # la misma venta sobreescribe el mismo archivo: el contenido es
    # idéntico, no tiene sentido acumular copias.
    fecha = str(venta["fecha"]).replace(":", "-").replace(" ", "_")
    return f"ticket_{venta['id']}_{fecha}.pdf"


def _logo_emblema():
    """
    Emblema del logo Fermento como imagen RGBA: líneas NEGRAS sobre
    fondo TRANSPARENTE, listo para estampar en la hoja blanca del
    ticket. None si FermentoLogo.jpeg no está junto al .exe (el ticket
    sale igual, solo sin emblema -- mismo criterio que branding.py).

    El JPEG original es líneas doradas sobre fondo negro: acá el brillo
    de cada pixel se convierte en opacidad de tinta negra (línea
    brillante = trazo opaco, fondo oscuro = transparente), con una curva
    que aplasta el ruido de compresión JPEG del fondo para que no quede
    un velo gris alrededor del emblema.
    """
    from PIL import Image
    from views import branding

    if not branding.LOGO_PATH.exists():
        return None
    emblema = branding._recortar(Image.open(branding.LOGO_PATH), branding._CAJA_EMBLEMA)
    brillo = emblema.convert("L")
    # < 40: ruido JPEG del fondo negro -> transparente total.
    # 40..180: rampa de opacidad (bordes suaves de las líneas).
    # > 180: trazo pleno -> opaco total.
    alfa = brillo.point(lambda v: 0 if v < 40 else min(255, round((v - 40) * 255 / 140)))
    negro = Image.new("L", brillo.size, 0)
    rgba = Image.merge("RGBA", (negro, negro, negro, alfa))
    # Recortar al dibujo mismo: `_CAJA_EMBLEMA` está expresada en fracciones
    # del JPEG y deja un margen transparente alrededor. Acá el emblema se
    # centra y se escala por su ALTO, así que ese margen se traduce en un
    # logo más chico de lo pedido y descentrado si sobra más de un lado que
    # del otro. La caja del alfa da el borde exacto de la tinta, sin
    # depender de que las fracciones estén afinadas al pixel.
    return rgba.crop(rgba.getbbox() or (0, 0, rgba.width, rgba.height))


def _plata(valor):
    """$1,234.50 -- con separador de miles, que en el rollo se lee de un
    vistazo y es lo que hace cualquier ticket de punto de venta."""
    return f"${valor:,.2f}"


def _dibujar_pdf(ruta, venta, detalle):
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas

    # El logo se prepara UNA vez y se le pasa a las dos pasadas: además
    # de ahorrarse el trabajo de Pillow dos veces, garantiza que la que
    # mide y la que dibuja usen exactamente las mismas proporciones.
    logo = _logo_emblema()

    # Dos pasadas con la MISMA función de armado. El alto de la página
    # depende del contenido (cuántos productos, y cuántos renglones ocupa
    # cada nombre al partirse), y reportlab necesita el alto antes de
    # dibujar el primer trazo. La alternativa -- una fórmula aparte del
    # tipo "50mm + 9mm por producto" -- se desincroniza en silencio en
    # cuanto alguien agrega un renglón al pie; acá no puede pasar, porque
    # la medición es literalmente el mismo código sin dibujar.
    medidor = pdf_canvas.Canvas(io.BytesIO(), pagesize=(ANCHO_ROLLO_MM * mm, 1))
    alto = _armar(medidor, venta, detalle, logo, 0, dibujar=False)

    c = pdf_canvas.Canvas(str(ruta), pagesize=(ANCHO_ROLLO_MM * mm, alto))
    _armar(c, venta, detalle, logo, alto, dibujar=True)
    c.save()


def _armar(c, venta, detalle, logo, alto_pag, dibujar):
    """
    Dibuja el ticket entero de arriba hacia abajo y devuelve el alto que
    ocupó. Con `dibujar=False` hace exactamente las mismas cuentas (y el
    mismo partido de nombres largos, que necesita medir texto) pero no
    estampa nada: así se averigua el alto de la página antes de crearla.

    `alto_pag` es el alto de la página que se está dibujando; en la
    pasada de medición va 0 y el cursor `y` simplemente arranca en
    negativo -- todo el armado es en desplazamientos relativos, así que
    el alto resultante es el mismo.

    **No hay salto de página**: en un rollo el ticket es una tira
    continua, así que la página crece hacia abajo tanto como haga falta.
    Por eso desapareció el manejo de `showPage()` que tenía la versión
    en A4.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader

    ancho_pag = ANCHO_ROLLO_MM * mm
    x0 = _MARGEN_LAT_MM * mm
    x1 = ancho_pag - _MARGEN_LAT_MM * mm
    cx = ancho_pag / 2
    ancho_util = x1 - x0

    y = alto_pag - _MARGEN_SUP_MM * mm

    # Los tres helpers bajan el cursor PRIMERO y dibujan después, así que
    # `alto` es el alto del renglón completo y no hay que llevar aparte
    # la cuenta del interlineado.
    def centrado(txt, tam, alto, negrita=False):
        nonlocal y
        y -= alto
        if dibujar:
            c.setFont(_BOLD if negrita else _NORMAL, tam)
            c.drawCentredString(cx, y, txt)

    def izq_der(izq, der, tam, alto, negrita=False, sangria=0):
        nonlocal y
        y -= alto
        if dibujar:
            c.setFont(_BOLD if negrita else _NORMAL, tam)
            c.drawString(x0 + sangria, y, izq)
            c.drawRightString(x1, y, der)

    def separador(alto, punteado=True):
        nonlocal y
        y -= alto
        if dibujar:
            c.setLineWidth(0.8)
            if punteado:
                c.setDash(1.6, 1.6)
            c.line(x0, y, x1, y)
            c.setDash()

    # ── Encabezado ───────────────────────────────────────────────────────
    # El emblema va CENTRADO y grande, no arriba a la izquierda como en la
    # versión A4: en 72mm útiles no hay lugar para poner algo al lado, y
    # centrado es además lo que se espera de un ticket de mostrador.
    if logo:
        alto_logo = 17 * mm
        ancho_logo = alto_logo * logo.width / logo.height
        y -= alto_logo
        if dibujar:
            c.drawImage(ImageReader(logo), cx - ancho_logo / 2, y,
                        ancho_logo, alto_logo, mask="auto")

    centrado("FERMENTO", 19, 8.5 * mm, negrita=True)
    centrado("Panadería", 9, 4.5 * mm)
    if DIRECCION:
        centrado(DIRECCION, 8.5, 4.4 * mm)

    separador(3 * mm, punteado=False)

    izq_der(f"Ticket N° {venta['id']}", formato.fecha(venta["fecha"]), 8.5, 5.5 * mm)

    # Reimpresión defensiva de una venta anulada (la UI normalmente no
    # ofrece ticket para anuladas, pero si llega una acá, que el papel
    # no parezca una venta vigente).
    if venta.get("anulada"):
        centrado("*** VENTA ANULADA ***", 12, 7 * mm, negrita=True)
        anulacion = formato.fecha(venta.get("fecha_anulacion"))
        if anulacion:
            centrado(anulacion, 8.5, 4.2 * mm)

    # ── Líneas de la venta ───────────────────────────────────────────────
    # Dos renglones por producto en vez de las cuatro columnas del A4:
    # con 72mm útiles, "Producto / Cant. / P. unit. / Subtotal" solo entra
    # achicando la letra hasta donde no se lee, que es el problema que
    # este rediseño viene a arreglar. Arriba el nombre a todo el ancho
    # (partido en dos renglones si es largo, en vez de recortado con "…")
    # y abajo la cuenta: "2 x $35.00" a la izquierda, el importe a la
    # derecha.
    separador(3.5 * mm)
    izq_der("CANT. / DESCRIPCIÓN", "IMPORTE", 7.5, 4.5 * mm, negrita=True)
    separador(1.8 * mm)
    y -= 1.5 * mm

    articulos = 0
    for item in detalle:
        articulos += item["cantidad"]
        for linea in _envolver(c, item["nombre"], _BOLD, 10.5, ancho_util):
            y -= 5.2 * mm
            if dibujar:
                c.setFont(_BOLD, 10.5)
                c.drawString(x0, y, linea)
        izq_der(f"{item['cantidad']} x {_plata(item['precio_unitario'])}",
                _plata(item["subtotal"]), 9.5, 5 * mm, sangria=3 * mm)
        y -= 1.8 * mm   # aire entre productos, para que no se lean como uno

    # ── Total y pago ─────────────────────────────────────────────────────
    separador(2 * mm)
    izq_der("ARTÍCULOS", str(articulos), 9.5, 5.5 * mm)
    izq_der("TOTAL", _plata(venta["total"]), 17, 9.5 * mm, negrita=True)

    # Pago y cambio solo si se registraron: `pago` en NULL significa que
    # el vendedor no cargó con cuánto pagó el cliente (o que la venta es
    # anterior a esa columna), y un "SU CAMBIO: $0.00" inventado se
    # leería como "pagó justo", que es otra cosa.
    pago = venta.get("pago")
    if pago is not None:
        izq_der("PAGO CON", _plata(pago), 12, 7 * mm)
        # max(0.0, ...) por el cero negativo: pagando justo, la resta de dos
        # float da -0.0 y se imprimiría "SU CAMBIO: $-0.00". La pantalla de
        # venta ya no deja registrar un pago menor al total, así que acá
        # cualquier valor no positivo es cambio cero.
        izq_der("SU CAMBIO", _plata(max(0.0, pago - venta["total"])), 14, 8 * mm,
                negrita=True)

    # ── Pie ──────────────────────────────────────────────────────────────
    # Una sola línea de cierre. La aclaración "Comprobante sin valor
    # fiscal" que traía la versión A4 se sacó a pedido de Alan el
    # 2026-08-31: en el mostrador nadie confunde este papel con una
    # factura, y en un rollo angosto cada renglón del pie es papel que se
    # gasta en cada venta.
    #
    # Sin gris en el pie: la térmica no imprime medios tonos, los simula
    # con puntos salteados y en letra chica eso sale como una mancha.
    separador(4 * mm, punteado=False)
    centrado("¡Gracias por su compra!", 10, 7 * mm)

    y -= _MARGEN_INF_MM * mm
    return alto_pag - y


def _envolver(c, texto, fuente, tam, ancho_max):
    """
    Parte `texto` en los renglones que entren en `ancho_max`, cortando
    entre palabras. En el rollo un nombre largo es lo normal ("Concha de
    chocolate grande"), así que se parte en vez de recortarse con "…"
    como hacía la versión A4 -- ahí sobraba ancho y acá no, y el nombre
    del producto es justo lo que el cliente revisa.
    """
    palabras = texto.split()
    if not palabras:
        return [texto]
    lineas, actual = [], palabras[0]
    for palabra in palabras[1:]:
        if c.stringWidth(f"{actual} {palabra}", fuente, tam) <= ancho_max:
            actual = f"{actual} {palabra}"
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    # Una sola palabra más larga que el renglón no tiene por dónde
    # partirse: esa sí se recorta, o se saldría del papel.
    return [ln if c.stringWidth(ln, fuente, tam) <= ancho_max
            else _truncar(c, ln, fuente, tam, ancho_max) for ln in lineas]


def _truncar(c, texto, fuente, tam, ancho_max):
    """Recorta `texto` con '…' para que entre en `ancho_max` puntos."""
    if c.stringWidth(texto, fuente, tam) <= ancho_max:
        return texto
    while texto and c.stringWidth(texto + "…", fuente, tam) > ancho_max:
        texto = texto[:-1]
    return texto + "…"
