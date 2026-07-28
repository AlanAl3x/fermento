# Paleta de colores del modo oscuro de la aplicación.
# Tomada del logo de la marca (FermentoLogo.jpeg): fondo negro, emblema
# dorado, texto blanco cálido. La app corre siempre en modo oscuro (ver
# main.py), así que los colores acá son valores fijos en vez de tuplas
# (claro, oscuro) de CustomTkinter.

# Fondos, de más oscuro a más claro ("elevación") — negro neutro, como
# el fondo del logo.
BG_SIDEBAR = "#0d0d0d"
BG_APP = "#121212"
BG_CARD = "#1c1c1c"
BG_CARD_HEADER = "#242424"
BG_INPUT = "#1f1f1f"

# Texto
TEXT_PRIMARY = "#f0ede4"      # blanco cálido, como "FERMENTO" en el logo
TEXT_SECONDARY = "#b8ab84"    # dorado apagado, como el subtítulo del logo
TEXT_DISABLED = "#6b6355"

# Acento — acciones primarias (Editar, Agregar, Ver detalle, Guardar...).
# Dorado del emblema; el texto sobre estos botones va oscuro (ACCENT_TEXT)
# porque el dorado es demasiado claro para texto blanco encima.
ACCENT = "#c9a227"
ACCENT_HOVER = "#a3830f"
ACCENT_TEXT = "#1a1508"

# Éxito — Confirmar venta, ajustar Stock
SUCCESS = "#2e7d32"
SUCCESS_HOVER = "#1b5e20"

# Peligro — Eliminar, quitar del carrito
DANGER = "#c62828"
DANGER_HOVER = "#a11d1d"

# Advertencia — Reactivar
WARNING = "#e65100"
WARNING_HOVER = "#bf360c"

# Neutro — Limpiar, Cerrar, controles +/- del carrito
NEUTRAL = "#4a453a"
NEUTRAL_HOVER = "#38342c"

# Barra lateral: botón de sección inactiva
NAV_INACTIVE = "#1c1c1c"
NAV_INACTIVE_HOVER = "#262626"

# Borde sutil para campos de entrada
BORDER = "#3a3327"


def rgb(hex_color):
    """Convierte "#rrggbb" a la tupla (r, g, b) que espera Pillow."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
