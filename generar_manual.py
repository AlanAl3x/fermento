"""Genera el manual de instalación y uso de Fermento (Word).

    pip install python-docx      # una sola vez
    python generar_manual.py

Reescribe `Fermento - Manual de instalacion y uso.docx`, que es el documento
que lee la panadería y que `empaquetar.py` mete adentro del ZIP.

**El .docx se genera, no se edita a mano.** Si se corrige el Word directo, el
cambio se pierde la próxima vez que alguien corra este script -- y no hay
forma de darse cuenta salvo comparando los dos archivos. Al cambiar algo que
se vea en pantalla de la app, tocar acá y volver a correrlo.

La versión sale de `version.py`, así que no hay que actualizarla en dos
lugares.

Nota sobre el formato: los recuadros de aviso son tablas de 1x1 con relleno y
barra lateral (Word no tiene "cajas"), y llevan `cantSplit` para que no se
corten a la mitad entre dos páginas.
"""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

PROYECTO = Path(r"C:\Users\alana\Documents\Proyectos\Panaderia")
SALIDA = PROYECTO / "Fermento - Manual de instalacion y uso.docx"

DORADO = RGBColor(0xB8, 0x8A, 0x1A)      # el dorado de la marca, algo mas oscuro
NEGRO = RGBColor(0x1A, 0x1A, 0x1A)       # para impresion en papel blanco
GRIS = RGBColor(0x55, 0x55, 0x55)
FILL_AVISO = "FDF6E3"                    # crema, para las cajas de "importante"
FILL_NOTA = "F2F2F2"

doc = Document()

# ── Pagina carta y margenes comodos ──────────────────────────────────────────
s = doc.sections[0]
s.page_width, s.page_height = Inches(8.5), Inches(11)
s.left_margin = s.right_margin = Inches(1.0)
s.top_margin = Inches(0.9)
s.bottom_margin = Inches(0.9)

# ── Estilos base ─────────────────────────────────────────────────────────────
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11.5)
normal.paragraph_format.space_after = Pt(8)
normal.paragraph_format.line_spacing = 1.15

for nombre, tam, color, antes in (
    ("Heading 1", 20, DORADO, 22),
    ("Heading 2", 15, NEGRO, 16),
    ("Heading 3", 12.5, NEGRO, 12),
):
    st = doc.styles[nombre]
    st.font.name = "Calibri"
    st.font.size = Pt(tam)
    st.font.bold = True
    st.font.color.rgb = color
    st.paragraph_format.space_before = Pt(antes)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.keep_with_next = True


def p(texto="", negrita=False, size=None, color=None, align=None, espacio=None,
      cursiva=False):
    par = doc.add_paragraph()
    run = par.add_run(texto)
    run.bold = negrita
    run.italic = cursiva
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    if align is not None:
        par.alignment = align
    if espacio is not None:
        par.paragraph_format.space_after = Pt(espacio)
    return par


def rico(partes, align=None, espacio=None):
    """Parrafo con tramos en negrita: [(texto, bold), ...]."""
    par = doc.add_paragraph()
    for texto, bold in partes:
        run = par.add_run(texto)
        run.bold = bold
    if align is not None:
        par.alignment = align
    if espacio is not None:
        par.paragraph_format.space_after = Pt(espacio)
    return par


def vineta(texto, negrita_hasta=None):
    par = doc.add_paragraph(style="List Bullet")
    if negrita_hasta:
        par.add_run(negrita_hasta).bold = True
        par.add_run(texto)
    else:
        par.add_run(texto)
    par.paragraph_format.space_after = Pt(4)
    return par


def _sombrear(celda, fill):
    tcPr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _no_partir(fila):
    """Evita que una fila se corte a la mitad entre dos paginas."""
    trPr = fila._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def _borde_izquierdo(celda, color):
    tcPr = celda._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for lado, ancho, col in (("left", 24, color), ("top", 4, "FFFFFF"),
                             ("bottom", 4, "FFFFFF"), ("right", 4, "FFFFFF")):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(ancho))
        el.set(qn("w:color"), col)
        borders.append(el)
    tcPr.append(borders)


def caja(titulo, lineas, fill=FILL_AVISO, barra="C9A227"):
    """Recuadro destacado: una tabla de 1x1 con relleno y barra lateral."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.columns[0].width = Inches(6.5)
    _no_partir(t.rows[0])
    celda = t.cell(0, 0)
    celda.width = Inches(6.5)
    _sombrear(celda, fill)
    _borde_izquierdo(celda, barra)

    primero = celda.paragraphs[0]
    run = primero.add_run(titulo)
    run.bold = True
    run.font.size = Pt(11.5)
    primero.paragraph_format.space_after = Pt(4)
    for linea in lineas:
        par = celda.add_paragraph()
        par.add_run(linea).font.size = Pt(11)
        par.paragraph_format.space_after = Pt(3)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def tabla(encabezados, filas, anchos):
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (h, w) in enumerate(zip(encabezados, anchos)):
        t.columns[i].width = Inches(w)
        celda = t.cell(0, i)
        celda.width = Inches(w)
        _sombrear(celda, "2B2B2B")
        par = celda.paragraphs[0]
        run = par.add_run(h)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.size = Pt(10.5)
        par.paragraph_format.space_after = Pt(2)
    _no_partir(t.rows[0])
    for fila in filas:
        renglon = t.add_row()
        _no_partir(renglon)
        celdas = renglon.cells
        for i, (valor, w) in enumerate(zip(fila, anchos)):
            celdas[i].width = Inches(w)
            par = celdas[i].paragraphs[0]
            run = par.add_run(valor)
            run.font.size = Pt(10.5)
            if i == 0:
                run.bold = True
            par.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def salto():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ═══════════════════════════════════════════════════════════════════════════
# PORTADA
# ═══════════════════════════════════════════════════════════════════════════
doc.add_paragraph().paragraph_format.space_after = Pt(60)

logo = PROYECTO / "FermentoLogo.jpeg"
if logo.exists():
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(logo), width=Inches(3.1))
    par.paragraph_format.space_after = Pt(30)

p("Manual de instalación y uso", negrita=True, size=30, color=NEGRO,
  align=WD_ALIGN_PARAGRAPH.CENTER, espacio=6)
p("Sistema de ventas para la panadería", size=15, color=GRIS,
  align=WD_ALIGN_PARAGRAPH.CENTER, espacio=40)
p("Versión 1.0.0", negrita=True, size=12, color=DORADO,
  align=WD_ALIGN_PARAGRAPH.CENTER, espacio=2)
p("Julio de 2026", size=11, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, espacio=60)

p("Este manual está escrito para usarse sin saber nada de computación. "
  "Si sigues los pasos en orden, no te puedes equivocar.",
  size=11.5, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, cursiva=True)

salto()

# ═══════════════════════════════════════════════════════════════════════════
# CONTENIDO
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Lo que vas a encontrar aquí", level=1)
p("Este manual tiene cinco partes. Si apenas vas a instalar el programa, "
  "empieza por la primera. Si ya lo tienes funcionando y solo quieres saber "
  "qué hace cada botón, ve directo a la parte 4.", espacio=12)

tabla(
    ["Parte", "De qué se trata", "Cuándo la vas a necesitar"],
    [
        ["1", "Cómo instalar el programa", "Una sola vez, al principio"],
        ["2", "Cómo actualizarlo", "Cada vez que te manden una versión nueva"],
        ["3", "Dónde se guardan tus ventas", "Para sacar copias de seguridad"],
        ["4", "Para qué sirve cada parte", "Cuando quieras aprender a usarlo"],
        ["5", "Si algo sale mal", "Ojalá nunca"],
    ],
    [0.6, 2.6, 3.3],
)

salto()

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 1 — INSTALACION
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Parte 1. Cómo instalar el programa", level=1)

p("Instalar Fermento es copiar una carpeta a la computadora. No hay que "
  "instalar nada más, ni programas extra, ni internet.", espacio=10)

doc.add_heading("Lo que necesitas antes de empezar", level=2)
vineta("La computadora de la panadería, con Windows.")
vineta("El archivo Fermento-v1.0.0.zip (te lo pasan en una memoria USB o por correo).",
       negrita_hasta="")
p("", espacio=2)

doc.add_heading("Paso 1. Abre tu carpeta personal", level=2)
p("Abre el Explorador de archivos (el ícono de la carpetita amarilla, en la barra "
  "de abajo de la pantalla).")
rico([("Arriba hay una barra larga donde dice la ubicación. Haz clic ahí, borra lo "
       "que diga, escribe esto tal cual y presiona Enter:", False)])
rico([("%USERPROFILE%", True)], align=WD_ALIGN_PARAGRAPH.CENTER)
p("Vas a llegar a tu carpeta personal: es la que tiene adentro Descargas, "
  "Documentos, Imágenes y Escritorio.", espacio=8)

caja("Por qué aquí y no en Documentos ni en el Escritorio",
     ["Si la computadora usa OneDrive, las carpetas Documentos y Escritorio se copian "
      "solas a internet todo el tiempo. Eso puede dañar el archivo donde se guardan "
      "las ventas.",
      "Tu carpeta personal no se copia a ningún lado, y tampoco te pide permisos de "
      "administrador. Es el lugar más seguro para dejarlo."])

doc.add_heading("Paso 2. Crea ahí una carpeta llamada Fermento", level=2)
p("Haz clic derecho en un espacio vacío, elige Nuevo y luego Carpeta.")
rico([("Escribe el nombre ", False), ("Fermento", True), (" y presiona Enter.", False)])
p("Déjala abierta: la vas a necesitar en el paso que sigue.", espacio=12)

doc.add_heading("Paso 3. Copia el programa adentro", level=2)
rico([("Haz clic derecho sobre el archivo ", False), ("Fermento-v1.0.0.zip", True),
      (" y elige ", False), ("Extraer todo…", True)])
p("Se abre una ventana que te pregunta dónde ponerlo. Ahí tienes que señalar la "
  "carpeta Fermento que acabas de crear:")
vineta("Haz clic en el botón Examinar…")
vineta("Busca y selecciona tu carpeta Fermento (está en tu carpeta personal, la del "
       "paso 1).")
rico([("Por último haz clic en ", False), ("Extraer", True), (".", False)])
rico([("Cuando termine, dentro de tu carpeta Fermento debe haber una carpeta llamada ",
       False), ("Programa", True), (".", False)], espacio=12)

doc.add_heading("Paso 4. Ábrelo por primera vez", level=2)
rico([("Entra a ", False), ("Fermento", True), (" y luego a ", False), ("Programa", True),
      (", y haz doble clic en ", False), ("Fermento.exe", True),
      (" (el del ícono de la espiga dorada).", False)])

caja("La primera vez Windows te va a asustar. Es normal.",
     ["Va a salir una pantalla azul que dice “Windows protegió tu PC”. Eso le pasa "
      "a cualquier programa que no venga de una tienda; no significa que haya un virus.",
      "Haz clic en “Más información” y luego en el botón “Ejecutar de todas formas”.",
      "Solo pasa la primera vez."])

p("La aplicación abre en unos segundos. Al abrirse, ella sola crea una carpeta "
  "llamada Datos, que es donde va a guardar todas tus ventas.", espacio=12)

doc.add_heading("Paso 5. Ponlo en el escritorio para no buscarlo cada vez", level=2)
rico([("Haz clic derecho sobre ", False), ("Fermento.exe", True), (".", False)])
rico([("Elige ", False), ("Mostrar más opciones", True), (", después ", False),
      ("Enviar a", True), (" y por último ", False),
      ("Escritorio (crear acceso directo)", True), (".", False)])
p("Listo: ya puedes abrir la aplicación desde el escritorio con doble clic. "
  "De aquí en adelante ya no tienes que buscar la carpeta.", espacio=12)

salto()

doc.add_heading("Paso 6. Carga tu información", level=2)
p("La primera vez el programa abre completamente vacío, como una libreta nueva. "
  "Hay que cargarle tres cosas. Esto se hace una sola vez:", espacio=6)

tabla(
    ["Qué", "Dónde", "¿Es obligatorio?"],
    [
        ["Tus productos y sus precios", "Productos → + Agregar producto", "Sí"],
        ["Tus insumos (harina, azúcar…)", "Inventario → + Agregar insumo", "No, pero ayuda"],
        ["Los descuentos del pan del día anterior", "Ajustes → Configurar reglas",
         "No, pero se recomienda"],
    ],
    [2.5, 2.7, 1.3],
)

caja("Después del paso 6 ya puedes vender.",
     ["Todo lo demás (el historial, los cortes de caja, las gráficas) se va llenando "
      "solo conforme vayas usando la aplicación."],
     fill="EAF3EA", barra="4C8C4A")

salto()

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 2 — ACTUALIZAR
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Parte 2. Cómo actualizar a una versión nueva", level=1)

p("Cuando se le hagan mejoras al programa va a salir una versión nueva. "
  "Actualizar son tres pasos:", espacio=10)

caja("La aplicación te avisa sola",
     ["Cuando hay una versión nueva, abajo a la izquierda (arriba del botón de "
      "Ajustes) aparece un letrero dorado que dice “↑ Versión … lista”.",
      "Haz clic ahí y te ofrece abrir la página de descarga. Bajas el ZIP nuevo "
      "y sigues los tres pasos de abajo.",
      "Si no aparece nada, es que ya tienes la última. También puedes revisarlo "
      "cuando quieras en Ajustes → Buscar actualizaciones.",
      "Para esto la computadora necesita internet. Si no tiene, la aplicación "
      "funciona igual, nada más que no avisa."],
     fill="EAF3EA", barra="4C8C4A")

doc.add_heading("Paso 1. Cierra la aplicación", level=3)
p("Si está abierta, ciérrala con la X. Asegúrate de que no quede abierta en la "
  "barra de tareas.", espacio=8)

doc.add_heading("Paso 2. Borra la carpeta Programa", level=3)
rico([("Entra a tu carpeta ", False), ("Fermento", True),
      (", haz clic derecho sobre la carpeta ", False), ("Programa", True),
      (" y bórrala completa.", False)])
rico([("Sí, completa. ", True),
      ("Más abajo te explicamos por qué esto no borra ninguna venta.", False)], espacio=8)

doc.add_heading("Paso 3. Extrae el ZIP nuevo", level=3)
rico([("Igual que la primera vez: clic derecho en el ZIP nuevo → ", False),
      ("Extraer todo…", True), (" → ", False), ("Examinar…", True),
      (" → selecciona tu carpeta ", False), ("Fermento", True), (" → ", False),
      ("Extraer", True), (".", False)])
p("Abre la aplicación normalmente (desde el acceso directo del escritorio). "
  "Todo va a estar donde lo dejaste.", espacio=12)

caja("El acceso directo del escritorio sigue funcionando",
     ["Aunque borraste y volviste a poner la carpeta Programa, el acceso directo "
      "apunta al mismo lugar, así que no hay que volver a crearlo."],
     fill=FILL_NOTA, barra="888888")

caja("Tus ventas NO se borran al actualizar. Nunca.",
     ["Las ventas, los productos, los cortes y todo el historial NO viven en la "
      "carpeta Programa. Viven en la carpeta Datos, que está aparte y que la "
      "actualización no toca.",
      "Además, el archivo ZIP que recibes no trae ninguna base de datos adentro. "
      "Aunque quisieras, no hay forma de que borre tu información.",
      "La única regla importante: nunca borres ni muevas la carpeta Datos."])

doc.add_heading("Cómo saber si la actualización sí quedó", level=2)
rico([("Abre la aplicación y entra a ", False), ("Ajustes", True),
      (". Abajo dice “Fermento — versión…”. Si el número cambió, quedó instalada.",
       False)], espacio=8)

salto()

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 3 — LOS DATOS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Parte 3. Dónde se guardan tus ventas", level=1)

p("Después de instalar, dentro de tu carpeta Fermento vas a tener dos carpetas. "
  "Vale la pena entender la diferencia, porque es lo que hace que actualizar "
  "sea seguro:", espacio=10)

tabla(
    ["Carpeta", "Qué tiene adentro", "¿Se puede borrar?"],
    [
        ["Programa", "La aplicación en sí (el ícono, los archivos que la hacen funcionar)",
         "Sí, cuando actualizas"],
        ["Datos", "Todas tus ventas, productos, cortes, tickets y respaldos",
         "NUNCA"],
    ],
    [1.3, 3.9, 1.3],
)

doc.add_heading("Qué hay dentro de la carpeta Datos", level=2)
vineta("aquí está TODO tu historial. Es el archivo más importante de los dos equipos.",
       negrita_hasta="panaderia.db — ")
vineta("copias de seguridad automáticas. El programa hace una cada vez que lo abres "
       "y guarda las últimas 30.", negrita_hasta="backups — ")
vineta("los tickets que vas generando, en PDF.", negrita_hasta="tickets — ")
vineta("si algo falla, este es el archivo que hay que mandar para revisar qué pasó.",
       negrita_hasta="panaderia_error.log — ")

doc.add_heading("Cómo llegar rápido a esa carpeta", level=2)
rico([("Dentro de la aplicación: ", False), ("Ajustes", True),
      (" → botón ", False), ("Abrir carpeta de datos", True),
      (". Ahí mismo te muestra la ruta exacta, por si alguna vez no está donde "
       "esperabas.", False)], espacio=10)

caja("Saca una copia de vez en cuando (esto sí es importante)",
     ["Una vez por semana, copia la carpeta Datos completa a una memoria USB o "
      "a la nube (Google Drive, OneDrive, lo que uses).",
      "Las copias automáticas te protegen si el archivo se daña o si alguien lo "
      "borra sin querer. No te protegen si se descompone la computadora, se la "
      "roban o se quema. Para eso necesitas una copia fuera de esa máquina."])

salto()

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 4 — LA APLICACION
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Parte 4. Para qué sirve cada parte de la aplicación", level=1)

doc.add_heading("Cómo está organizada la pantalla", level=2)
p("Del lado izquierdo hay una barra con todas las secciones, agrupadas según "
  "cuándo las usas:", espacio=8)

tabla(
    ["Grupo", "Secciones", "Cuándo se usan"],
    [
        ["DÍA A DÍA", "Nueva venta · Productos · Inventario",
         "Con la panadería abierta"],
        ["REVISAR", "Historial · Análisis",
         "Al cerrar el día o para ver cómo va el mes"],
        ["⚙ Ajustes", "(hasta abajo)", "Se configura una vez y casi no se toca"],
    ],
    [1.3, 3.0, 2.2],
)

doc.add_heading("Tres palabras que conviene entender primero", level=2)
p("Aparecen por toda la aplicación y son la clave para entenderla:", espacio=6)

tabla(
    ["Palabra", "Qué significa"],
    [
        ["Tanda",
         "Cada hornada de un producto, con la fecha en que se horneó. El pan de hoy y "
         "el de ayer son dos tandas distintas del mismo producto, cada una con su "
         "cantidad y su precio."],
        ["Corte de caja",
         "El cierre. Junta todas las ventas que todavía no habías cerrado, saca el "
         "total y lo guarda como un hecho. Puedes hacer varios al día (por turnos)."],
        ["Margen",
         "Lo que te queda de ganancia: el precio de venta menos lo que te costó "
         "hacerlo. Solo aparece si cargaste el costo del producto."],
    ],
    [1.3, 5.2],
)

# ── Nueva venta ──────────────────────────────────────────────────────────────
doc.add_heading("Nueva venta", level=2)
p("Es la pantalla donde vendes, y con la que vas a pasar el 90 % del día. "
  "La aplicación abre directamente aquí.", espacio=6)
vineta("Del lado izquierdo están todos tus productos. Arriba hay un buscador para "
       "encontrarlos rápido si tienes muchos: escribe parte del nombre, o el N° de "
       "item si te lo sabes de memoria. El número de cada producto aparece chiquito "
       "delante de su nombre, para que confirmes de un vistazo que buscaste el que "
       "querías antes de agregarlo.")
vineta("Cada producto tiene un botón “+ Agregar” por cada tanda disponible. Si tienes "
       "pan de hoy y pan de ayer, verás dos botones, cada uno con su precio y su "
       "antigüedad: así vendes del que corresponda sin equivocarte de precio.")
vineta("Lo que se terminó aparece agrupado hasta abajo, bajo el letrero AGOTADOS. "
       "No desaparece, para que puedas avisarle al cliente que ya no hay.")
vineta("Del lado derecho se va armando el ticket con el total. Cuando terminas, "
       "presionas el botón de registrar la venta.")
vineta("Al lado del total hay un campo “Paga con”. Escribe ahí con cuánto te paga el "
       "cliente y al costado te va calculando el cambio mientras escribes. Es "
       "opcional: si lo dejas vacío, la venta se registra igual y el ticket sale sin "
       "esa parte. Si el monto no alcanza para el total, te avisa y no deja registrar.")
vineta("Después de vender aparece un aviso verde con un botón “Ticket”, por si el "
       "cliente lo quiere. Se genera en PDF y se abre solo para imprimirlo. "
       "Si no lo pide, ignóralo y el aviso se va solo. Si anotaste el pago, el aviso "
       "también te repite el cambio, para que lo tengas a la vista al contarlo.")
vineta("El ticket sale del ancho del rollo de la impresora (8 cm), con el total, el "
       "pago y el cambio en letra grande. Al imprimirlo desde el visor de PDF, "
       "asegúrate de que la escala esté en “Tamaño real” o al 100 %: si le pones "
       "“Ajustar a la página”, algunas impresoras lo achican y queda chiquito.")

# ── Productos ────────────────────────────────────────────────────────────────
doc.add_heading("Productos", level=2)
p("Tu catálogo: qué vendes, a qué precio y cuánto tienes. Se toca poco, "
  "normalmente al empezar la semana o cuando sacas algo del horno.", espacio=6)
vineta("El botón “+ Agregar producto” da de alta algo nuevo (nombre y precio; "
       "el costo es opcional).")
vineta("Cada producto tiene su “N° de item”, el número de la primera columna. Te sirve "
       "para buscarlo escribiendo el número en vez del nombre, y para ordenar la lista por "
       "él. Cuando das de alta un producto ya viene puesto el siguiente que está libre: si "
       "no te importa el número, déjalo como viene. Si prefieres tu propia numeración, "
       "cámbialo — lo único que no te deja es ponerle a dos productos el mismo número, y si "
       "pasa te dice cuál lo está usando (aunque sea uno que diste de baja).")
vineta("Cada renglón tiene un botón “+ Tanda”: es el que usas cuando sacas pan del "
       "horno. Le pones cuántas piezas y de qué día son.")
vineta("El botón “⋯” de cada renglón abre las opciones de editar o eliminar. "
       "Están escondidas ahí a propósito, porque se usan mucho menos que “+ Tanda”.")
vineta("Si le cargas el costo a un producto, aparece la columna Margen: cuánto ganas "
       "por pieza, en pesos y en porcentaje. Si no lo cargas, muestra un guion — "
       "prefiere no decir nada antes que darte un número inventado.")
vineta("Los productos no se borran de verdad: se ocultan. Así el historial de ventas "
       "viejas nunca se rompe.")

# ── Inventario ───────────────────────────────────────────────────────────────
doc.add_heading("Inventario", level=2)
p("El control de tus materias primas: harina, azúcar, levadura, huevo, lo que uses. "
  "Es una lista aparte de los productos que vendes.", espacio=6)
vineta("Cada insumo tiene su cantidad actual y su unidad (kilos, litros).")
vineta("Le puedes poner un mínimo. Cuando la existencia baja de ahí, el número se "
       "pinta de naranja y aparece un aviso al pie de la pantalla. Si no le pones "
       "mínimo, nunca te avisa nada.")
vineta("Cada renglón tiene una barra que muestra de un vistazo cuánto te queda, "
       "con cuánto empezaste el día y dónde está el mínimo.")

caja("Ojo con el inventario: hoy es manual",
     ["Cuando vendes un pan, la aplicación NO descuenta sola la harina que llevaba. "
      "Para que lo hiciera habría que cargarle la receta de cada producto, y eso "
      "todavía no está hecho.",
      "Por ahora el inventario se ajusta a mano: cuando compras harina la sumas, "
      "y cuando amasas la restas."],
     fill=FILL_NOTA, barra="888888")

# ── Historial ────────────────────────────────────────────────────────────────
doc.add_heading("Historial", level=2)
p("Todo lo que ya pasó. Tiene dos pestañas.", espacio=6)

doc.add_heading("Pestaña Ventas", level=3)
vineta("La lista de todas las ventas, de la más reciente para atrás.")
vineta("Puedes filtrar por fechas escribiéndolas o eligiéndolas en un calendario "
       "(el botón “▾”), y hay atajos de Hoy, Esta semana y Este mes.")
vineta("Al abrir una venta ves qué se llevó el cliente, pieza por pieza, y puedes "
       "volver a imprimir su ticket.")
vineta("Si te equivocaste, puedes anular una venta: te pide el motivo, la marca como "
       "anulada y le regresa las piezas a la tanda de donde salieron. No se borra, "
       "queda el registro de que existió y se canceló. Solo se pueden anular ventas "
       "que todavía no entraron a un corte de caja.")

doc.add_heading("Pestaña Cortes", level=3)
vineta("Aquí haces el corte de caja. Antes de confirmarlo te muestra el desglose para "
       "que lo revises.")
vineta("Abajo está la lista de todos los cortes anteriores, con su total. Puedes abrir "
       "cualquiera para ver cuánto se vendió de cada producto.")
vineta("Cada corte se puede exportar a Excel (archivo CSV), y también hay un botón "
       "para exportar todas las ventas con fecha y hora exactas.")
vineta("Si cerraste el corte por error, se puede deshacer, pero únicamente el último. "
       "Las ventas vuelven a quedar pendientes, como si no hubieras cerrado.")

# ── Analisis ─────────────────────────────────────────────────────────────────
doc.add_heading("Análisis", level=2)
p("Las gráficas: sirven para decidir qué conviene hornear más y qué menos. "
  "Todo se puede filtrar por fechas.", espacio=6)
vineta("Arriba, tres números grandes del período: cuánto vendiste, cuánto resignaste "
       "rematando pan del día anterior, y cuánto te quedó de ganancia.")
vineta("Una gráfica de línea con el total de cada corte, para ver si vas subiendo o "
       "bajando con el tiempo.")
vineta("Un ranking de productos, con barras de colores. Puedes cambiar qué mide: "
       "cuánto dinero dejó cada uno, cuánta ganancia, o qué tanto se remata.")
vineta("Si algún producto no tiene costo cargado, te lo avisa al pie en vez de "
       "enseñarte una ganancia más alta de la real.")

# ── Ajustes ──────────────────────────────────────────────────────────────────
doc.add_heading("Ajustes", level=2)
p("Está hasta abajo de la barra, separado de lo demás, porque se configura una vez "
  "y casi no se vuelve a tocar.", espacio=6)
vineta("Las reglas de descuento por antigüedad: a partir de cuántos días el pan baja "
       "de precio y cuánto baja. Por ejemplo: “a los 2 días, 25 % menos”.")
vineta("Puedes ponerle reglas distintas a un producto en particular, si se echa a "
       "perder más rápido que los demás.")
vineta("El descuento se aplica solo, al momento de vender, según la fecha de la tanda. "
       "No tienes que cambiarle el precio a nada a mano.")
vineta("Abajo se muestra la versión instalada y la carpeta donde están tus ventas, "
       "con un botón para abrirla.")
vineta("El botón “Buscar actualizaciones” revisa si salió una versión nueva y te "
       "dice en qué estás: al día, hay una nueva, o no hay internet en este momento.")

caja("Cómo funciona el descuento en la práctica",
     ["Una concha cuesta $16. Si tienes la regla “a los 2 días, 25 % menos”, la concha "
      "de una tanda de hace dos días se vende sola en $12, sin que nadie toque nada.",
      "El precio de lista de la concha sigue siendo $16: la de hoy se sigue vendiendo "
      "a precio normal. Lo que cambia es el precio de esa tanda, por vieja."])

salto()

# ═══════════════════════════════════════════════════════════════════════════
# PARTE 5 — PROBLEMAS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Parte 5. Si algo sale mal", level=1)

tabla(
    ["Qué pasa", "Qué hacer"],
    [
        ["Sale una pantalla azul que dice que Windows protegió tu PC",
         "Es normal la primera vez. “Más información” → “Ejecutar de todas formas”."],
        ["La aplicación no abre",
         "Revisa que estés abriendo Fermento.exe, dentro de la carpeta Programa. "
         "Si aun así no abre, manda el archivo panaderia_error.log."],
        ["Aparece un mensaje de error dentro de la aplicación",
         "Anota qué estabas haciendo y manda el archivo panaderia_error.log de la "
         "carpeta Datos."],
        ["Abrí la aplicación y está vacía, sin mis productos",
         "No borres nada ni la vuelvas a instalar. Entra a Ajustes y fíjate qué "
         "carpeta dice. Avisa antes de hacer cualquier otra cosa."],
        ["Se descompuso la computadora",
         "Con la copia de la carpeta Datos que sacaste al USB, se instala en otra "
         "máquina y todo vuelve como estaba."],
    ],
    [2.2, 4.3],
)

caja("La regla de oro",
     ["Si algo se ve raro, NO reinstales y NO borres carpetas para “empezar de nuevo”. "
      "Casi todo tiene arreglo mientras la carpeta Datos siga completa.",
      "Manda el archivo panaderia_error.log y espera respuesta."])

doc.save(SALIDA)
print(f"Guardado: {SALIDA}")
print(f"Tamaño: {SALIDA.stat().st_size / 1024:.0f} KB")
