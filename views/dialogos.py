# Helpers compartidos por las ventanas de diálogo (CTkToplevel) de la app.
#
# `centrar_sobre` vivía duplicada en views/productos.py y views/inventario.py;
# al aparecer una tercera pantalla con diálogos (Ajustes) se movió acá en vez
# de hacer una copia más.


def centrar_sobre(ventana, parent, ancho, alto):
    """Centra `ventana` (ya con su tamaño final) sobre la ventana principal."""
    root = parent.winfo_toplevel()
    x = root.winfo_rootx() + (root.winfo_width() - ancho) // 2
    y = root.winfo_rooty() + (root.winfo_height() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")
