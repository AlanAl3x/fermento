# Genera el ticket de una venta como PDF (hoja A4, blanco y negro,
# pensado para una impresora convencional de hoja completa, no térmica)
# y lo abre con el visor de PDF predeterminado de Windows, desde donde
# el usuario lo imprime (o solo lo mira, si el cliente no quería papel).
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

import os

from views import formato
import database as db

TICKETS_DIR = db.BASE_DIR / "tickets"

# Ancho de la columna de contenido, centrada en la hoja A4. Un ticket
# a lo ancho de toda la hoja se lee mal -- esto imita la proporción de
# un recibo sin llegar al extremo de una cinta térmica de 80mm.
_ANCHO_COL_MM = 120


class TicketError(Exception):
    """Error al generar/abrir un ticket, con mensaje pensado para el usuario."""


def generar_y_abrir(venta, detalle):
    """
    Genera el PDF del ticket de una venta y lo abre con el visor de PDF
    del sistema. Devuelve la ruta del archivo generado.

    venta: dict con las columnas de la tabla `ventas` (id, fecha, total,
    anulada...). detalle: filas de get_detalle_venta() (nombre, cantidad,
    precio_unitario, subtotal).
    """
    # Import adentro de la función a propósito: si reportlab faltara
    # (entorno de desarrollo sin `pip install`), debe fallar solo la
    # generación del ticket con un mensaje claro, no el arranque de
    # toda la app por un import a nivel de módulo.
    try:
        from reportlab.lib.pagesizes import A4  # noqa: F401 (verifica la dependencia)
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
    return Image.merge("RGBA", (negro, negro, negro, alfa))


def _dibujar_pdf(ruta, venta, detalle):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    c = pdf_canvas.Canvas(str(ruta), pagesize=A4)
    ancho_pag, alto_pag = A4
    ancho_col = _ANCHO_COL_MM * mm
    x0 = (ancho_pag - ancho_col) / 2   # borde izquierdo de la columna
    x1 = x0 + ancho_col                # borde derecho

    # Posiciones (alineadas a la derecha) de las columnas numéricas; el
    # nombre del producto usa lo que sobra a la izquierda.
    x_subtotal = x1
    x_punit = x1 - 27 * mm
    x_cant = x1 - 52 * mm
    ancho_nombre = (x_cant - 14 * mm) - x0

    y_min = 30 * mm  # margen inferior: debajo de esto, salto de página

    def encabezado_tabla(y):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x0, y, "Producto")
        c.drawRightString(x_cant, y, "Cant.")
        c.drawRightString(x_punit, y, "P. unit.")
        c.drawRightString(x_subtotal, y, "Subtotal")
        c.setLineWidth(0.6)
        c.line(x0, y - 2 * mm, x1, y - 2 * mm)
        return y - 7 * mm

    # ── Encabezado del ticket ────────────────────────────────────────────
    # Emblema arriba a la izquierda (líneas negras, fondo transparente);
    # el texto FERMENTO/Panadería sigue centrado en la columna. Si el
    # JPEG no está, el ticket sale igual sin emblema.
    logo = _logo_emblema()
    if logo:
        # 18mm de alto con el borde inferior 4mm por encima de la línea
        # divisoria (que está en alto_pag - 41mm): con 22mm y menos
        # margen, la espiga quedaba tocando la línea y parecía recortada.
        alto_logo = 18 * mm
        ancho_logo = alto_logo * logo.width / logo.height
        c.drawImage(ImageReader(logo), x0, alto_pag - 37 * mm,
                    ancho_logo, alto_logo, mask="auto")

    y = alto_pag - 30 * mm
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(ancho_pag / 2, y, "FERMENTO")
    y -= 6 * mm
    c.setFont("Helvetica", 11)
    c.drawCentredString(ancho_pag / 2, y, "Panadería")
    y -= 5 * mm
    c.setLineWidth(1)
    c.line(x0, y, x1, y)
    y -= 9 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y, f"Ticket de venta N° {venta['id']}")
    c.setFont("Helvetica", 10)
    c.drawRightString(x1, y, formato.fecha(venta["fecha"]))
    y -= 6 * mm

    # Reimpresión defensiva de una venta anulada (la UI normalmente no
    # ofrece ticket para anuladas, pero si llega una acá, que el papel
    # no parezca una venta vigente).
    if venta.get("anulada"):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x0, y, f"VENTA ANULADA el {formato.fecha(venta.get('fecha_anulacion'))}")
        y -= 6 * mm

    y -= 3 * mm
    y = encabezado_tabla(y)

    # ── Líneas de la venta ───────────────────────────────────────────────
    c.setFont("Helvetica", 10)
    for item in detalle:
        if y < y_min:
            c.showPage()
            y = alto_pag - 25 * mm
            y = encabezado_tabla(y)
            c.setFont("Helvetica", 10)
        c.drawString(x0, y, _truncar(c, item["nombre"], "Helvetica", 10, ancho_nombre))
        c.drawRightString(x_cant, y, str(item["cantidad"]))
        c.drawRightString(x_punit, y, f"${item['precio_unitario']:.2f}")
        c.drawRightString(x_subtotal, y, f"${item['subtotal']:.2f}")
        y -= 5.5 * mm

    # ── Total y pie ──────────────────────────────────────────────────────
    if y < y_min:
        c.showPage()
        y = alto_pag - 25 * mm
    y -= 2 * mm
    c.setLineWidth(0.6)
    c.line(x0, y, x1, y)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(x1, y, f"TOTAL: ${venta['total']:.2f}")

    y -= 14 * mm
    c.setFont("Helvetica", 11)
    c.drawCentredString(ancho_pag / 2, y, "¡Gracias por su compra!")
    y -= 6 * mm
    c.setFont("Helvetica", 8)
    c.setFillGray(0.45)
    c.drawCentredString(ancho_pag / 2, y, "Comprobante sin valor fiscal")

    c.save()


def _truncar(c, texto, fuente, tam, ancho_max):
    """Recorta `texto` con '…' para que entre en `ancho_max` puntos."""
    if c.stringWidth(texto, fuente, tam) <= ancho_max:
        return texto
    while texto and c.stringWidth(texto + "…", fuente, tam) > ancho_max:
        texto = texto[:-1]
    return texto + "…"
