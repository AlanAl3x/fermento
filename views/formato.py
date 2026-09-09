from datetime import datetime


def fecha(iso):
    """
    Convierte una fecha/hora ISO -- como se guarda en la BD, "AAAA-MM-DD"
    o "AAAA-MM-DD HH:MM:SS" (ver database.py, así ordena bien como texto)
    -- al formato que ve el usuario en toda la app: "DD-MM-AAAA" o
    "DD-MM-AAAA HH:MM:SS". Es solo para mostrar; no cambia cómo se guarda.

    Si `iso` no tiene el formato esperado (o es None/vacío), se devuelve
    tal cual en vez de romper -- mostrar una fecha rara es mejor que
    crashear la pantalla.
    """
    if not iso:
        return iso
    try:
        if len(iso) > 10:
            dt = datetime.strptime(iso, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d-%m-%Y %H:%M:%S")
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return iso


def a_iso(txt):
    """Convierte "DD-MM-AAAA" (lo que escribe el usuario en los filtros de
    fecha) a "AAAA-MM-DD" (lo que se compara contra `ventas.fecha` /
    `cortes.fecha` en la BD). Es la conversión inversa de `fecha()`, y por
    eso vive acá al lado -- estuvo duplicada en `graficos.py` e
    `historial.py` hasta el 2026-07-21.

    Devuelve None si el texto no es una fecha válida: el llamador decide qué
    hacer con eso (hoy, los dos filtros muestran el mismo messagebox).
    """
    try:
        return datetime.strptime(txt, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def edad_tanda(dias):
    """Antigüedad de una tanda, con las palabras que se usan en el mostrador.

    "hace 0 día(s)" era técnicamente cierto y se leía mal justo en el caso
    más frecuente (el pan del día). Los dos primeros escalones tienen
    nombre propio -- "de hoy" y "anterior" -- porque son los que se
    distinguen de un vistazo al vender; del día 2 en adelante lo que
    importa es el número, no la etiqueta.

    `dias` en None (tanda sin fecha de horneado) devuelve None: el llamador
    decide qué mostrar, no se inventa una antigüedad.
    """
    if dias is None:
        return None
    if dias <= 0:
        return "Tanda de hoy"
    if dias == 1:
        return "Tanda anterior"
    return f"hace {dias} días"

def coincide_busqueda(producto, filtro):
    """¿Este producto entra en lo que se escribió en el buscador?

    Criterio Único de las dos pantallas que listan productos -- Productos y
    Nueva Venta. Vivió escrito dos veces por un rato y alcanza con que se
    toque una para que buscar lo mismo dé distinto según dónde se esté
    parado, que es el peor resultado posible para alguien atendiendo.

    El nombre se busca por CONTENIDO y el N° de item por PRINCIPIO, que es
    como se usa cada uno: en el nombre lo natural es encontrar “choco”
    dentro de “Concha de chocolate”, mientras que los números se leen de
    izquierda a derecha -- tipear “10” trae el 10, el 101 y el 102, pero
    no el 210, que no espera nadie parado en el mostrador.

    `filtro` llega en minúsculas y sin espacios en los bordes (lo hace el
    llamador, que ya tenía que normalizarlo para su propio `if`).
    """
    return (filtro in producto["nombre"].lower()
            or str(producto["codigo"] or "").startswith(filtro))

