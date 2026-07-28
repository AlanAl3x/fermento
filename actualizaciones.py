"""Aviso de versión nueva, consultando las Releases de GitHub.

Existe porque la app corre en la panadería y quien la mantiene no está ahí:
sin esto, la única forma de enterarse de que hay una versión nueva es que
alguien avise por teléfono, y un .exe viejo funciona igual de bien que uno
nuevo, así que nada delata que falta actualizar.

**Es el único lugar de la app que toca internet**, y está escrito con esa
premisa. Tres reglas que no se pueden relajar:

1. **Nunca bloquea.** La consulta va en un hilo aparte con timeout corto. La
   ventana termina de armarse y se puede vender aunque la red esté caída,
   lentísima o detrás de un proxy que no contesta. El hilo es `daemon`, así
   que tampoco impide cerrar la app si quedó colgado esperando.
2. **Nunca molesta.** Si falla cualquier cosa -- sin internet, GitHub caído,
   respuesta rara, límite de peticiones -- no se muestra nada. "No pude
   verificar actualizaciones" es ruido inútil en un mostrador con gente
   esperando; el único caso que merece pantalla es que SÍ haya una versión
   nueva. Tampoco se registra en el log: quedarse sin internet no es un
   error de la app, y llenar el log de eso taparía lo que sí importa.
3. **Ante la duda, callar.** Si el número de versión que devuelve GitHub no
   se puede interpretar, se asume que no hay nada nuevo. Avisar de más es
   peor que no avisar: manda a alguien a reinstalar sin motivo.

Sin dependencias nuevas: `urllib` viene con Python. Mismo criterio que
descartó `tkcalendar` y `pytest`.
"""

import json
import re
import threading
import urllib.error
import urllib.request

from version import VERSION

USUARIO = "AlanAl3x"
REPO = "fermento"

URL_API = f"https://api.github.com/repos/{USUARIO}/{REPO}/releases/latest"
#: La que se le abre al usuario. Siempre apunta a la más reciente.
URL_DESCARGA = f"https://github.com/{USUARIO}/{REPO}/releases/latest"

#: Corto a propósito: si en 6 segundos GitHub no contestó, no vale la pena
#: seguir esperando por algo que es opcional.
TIMEOUT = 6

_RE_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def numeros(etiqueta):
    """"v1.2.3" -> (1, 2, 3). Devuelve None si no se puede interpretar.

    Acepta el prefijo "v" (que es como se nombran los tags) y versiones
    incompletas ("1.2" -> (1, 2, 0)). Ignora lo que venga después del
    tercer número, para que un "v1.2.3-beta" no se caiga.
    """
    if not etiqueta:
        return None
    m = _RE_VERSION.match(etiqueta.strip())
    if not m:
        return None
    return tuple(int(x) if x else 0 for x in m.groups())


def es_mas_nueva(remota, actual=VERSION):
    """¿`remota` es posterior a `actual`?

    Compara como tuplas de enteros y NO como texto: "1.10.0" es posterior a
    "1.9.0", pero alfabéticamente sería al revés. Es el error clásico de
    comparar versiones, y acá se manifestaría recién en la décima versión.
    """
    r, a = numeros(remota), numeros(actual)
    if r is None or a is None:
        return False
    return r > a


#: Estados posibles de una búsqueda manual.
NUEVA = "nueva"
AL_DIA = "al_dia"
SIN_CONEXION = "sin_conexion"


def _consultar():
    """-> (etiqueta, hubo_error). Distingue "no hay novedad" de "no pude preguntar".

    La diferencia importa solo para la búsqueda manual: al arrancar, los dos
    casos se tratan igual (no mostrar nada), pero si el usuario apretó un
    botón hay que poder contestarle "estás al día" o "no hay internet", que
    no son lo mismo.
    """
    pedido = urllib.request.Request(
        URL_API,
        headers={
            # GitHub rechaza las peticiones sin User-Agent.
            "User-Agent": f"Fermento/{VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            datos = json.loads(r.read().decode("utf-8"))
        etiqueta = datos.get("tag_name")
        return (etiqueta, False) if etiqueta else (None, True)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        # Sin internet, DNS caído, proxy, JSON inesperado, límite de
        # peticiones... para la app es todo el mismo caso.
        return None, True


def _en_hilo(tarea):
    """Corre `tarea()` fuera del hilo de Tk. Daemon: no impide cerrar la app."""
    threading.Thread(target=tarea, daemon=True).start()


def _volver_al_hilo_de_tk(ventana, fn, *args):
    """Encola `fn(*args)` en el bucle de eventos.

    **Ningún widget se puede tocar desde el hilo de la consulta**; este es el
    único puente permitido. Se traga cualquier error a propósito: si la
    ventana se destruyó mientras la petición estaba en vuelo, Tk levanta
    (`TclError`, `RuntimeError` según el momento) y no hay nada que hacer
    ni a quién avisarle -- la app ya se está cerrando.
    """
    try:
        ventana.after(0, fn, *args)
    except Exception:
        pass


def buscar_en_segundo_plano(ventana, al_encontrar):
    """Chequeo del arranque: **avisa solo si hay una versión nueva**.

    Sin conexión o sin novedades no pasa absolutamente nada. Nadie pidió
    esta consulta, así que su único resultado visible legítimo es la buena
    noticia; cualquier otra cosa sería ruido a la hora de vender.
    """
    def trabajo():
        etiqueta, error = _consultar()
        if error or not etiqueta or not es_mas_nueva(etiqueta):
            return
        _volver_al_hilo_de_tk(ventana, al_encontrar, etiqueta)

    _en_hilo(trabajo)


def buscar_ahora(ventana, al_terminar):
    """Búsqueda manual: **contesta siempre**, con uno de los tres estados.

    Acá el silencio sería un error: el usuario apretó un botón y espera una
    respuesta. `al_terminar(estado, etiqueta)` corre en el hilo de Tk.
    """
    def trabajo():
        etiqueta, error = _consultar()
        if error:
            estado = SIN_CONEXION
        elif es_mas_nueva(etiqueta):
            estado = NUEVA
        else:
            estado = AL_DIA
        _volver_al_hilo_de_tk(ventana, al_terminar, estado, etiqueta)

    _en_hilo(trabajo)


def abrir_pagina():
    """Abre la página de descargas en el navegador. Nunca levanta."""
    import webbrowser
    try:
        webbrowser.open(URL_DESCARGA)
        return True
    except Exception:
        return False
