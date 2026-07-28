"""Widgets compartidos entre pantallas.

Distinto de `views/dialogos.py`, que son helpers de las ventanas
`CTkToplevel`: acá viven controles que se packean DENTRO de una pantalla.

Hoy solo `FiltroFechas`, que estaba duplicado casi palabra por palabra entre
Análisis (`graficos.py`) e Historial → Ventas (`historial.py`) -- los cuatro
widgets, la validación y los dos mensajes de error, ~50 líneas en cada uno.
"""

import calendar
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox

from views import formato, theme

# Nombres en castellano fijos, sin depender del locale del sistema: la app se
# distribuye como .exe y el locale de una PC cualquiera puede estar en inglés.
_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
# La semana arranca el lunes (firstweekday=0), como se lee un calendario acá.
_DIAS_SEMANA = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]


class FiltroFechas(ctk.CTkFrame):
    """Barra "Desde: [ ] Hasta: [ ] (Filtrar) (Limpiar)" con validación.

    Habla en ISO hacia afuera y en DD-MM-AAAA en pantalla: el llamador solo
    recibe fechas ya validadas y convertidas, listas para comparar contra
    `ventas.fecha` / `cortes.fecha` (ver `formato.a_iso()`).

    - `on_cambio(desde_iso, hasta_iso)`: el rango cambió, hay que refrescar.
      Cualquiera de los dos puede ser None (= sin filtro en ese extremo).
    - `on_manual()`: opcional, y solo cuando el cambio lo hizo el usuario
      tocando "Filtrar"/"Limpiar" -- no cuando el rango se aplicó por código
      con `set_rango()`. Existe para el caso de Análisis, donde filtrar a
      mano tiene que apagar el preset resaltado en dorado; si `set_rango()`
      lo disparara también, un preset se apagaría a sí mismo al aplicarse.
      Se llama ANTES de `on_cambio`, para que la pantalla ya esté consistente
      cuando se redibuje.

    El widget NO guarda el rango aplicado: esa es la verdad de la pantalla
    (`self._desde`/`self._hasta`), que lo usa para filtrar sus propios datos.
    Acá solo vive lo que hay tecleado en los campos.
    """

    def __init__(self, parent, on_cambio, on_manual=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self._on_cambio = on_cambio
        self._on_manual = on_manual

        ctk.CTkLabel(self, text="Desde:", text_color=theme.TEXT_PRIMARY).pack(
            side="left", padx=(0, 6))
        self._e_desde = self._entry()
        ctk.CTkLabel(self, text="Hasta:", text_color=theme.TEXT_PRIMARY).pack(
            side="left", padx=(0, 6))
        self._e_hasta = self._entry()

        ctk.CTkButton(self, text="Filtrar", width=90,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ACCENT_TEXT,
                      command=self._aplicar).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self, text="Limpiar", width=90,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self._limpiar).pack(side="left")

    def _entry(self):
        """Un campo DD-MM-AAAA con su botón "▾" al lado, que abre el
        calendario. Se puede tipear o elegir con el mouse, indistinto."""
        e = ctk.CTkEntry(self, placeholder_text="DD-MM-AAAA", width=110,
                         fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                         border_color=theme.BORDER)
        e.pack(side="left", padx=(0, 2))
        e.bind("<Return>", lambda ev: self._aplicar())

        # "▾" y no un ícono de calendario: los emoji tipo 📅 están fuera del
        # plano básico de Unicode y Tk en Windows los dibuja como un cuadro.
        b = ctk.CTkButton(self, text="▾", width=30,
                          fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)
        b.configure(command=lambda: self._abrir_calendario(e, b))
        b.pack(side="left", padx=(0, 10))
        return e

    def _abrir_calendario(self, entry, boton):
        """Abre el calendario sobre ese campo, arrancando en el mes de la
        fecha que ya tenga cargada (o el actual si está vacío o es basura)."""
        texto = entry.get().strip()
        actual = formato.a_iso(texto) if texto else None

        def elegida(iso):
            entry.delete(0, "end")
            entry.insert(0, formato.fecha(iso))

        _CalendarioPopup(self, boton, actual, elegida)

    # ── API para la pantalla ──────────────────────────────────────────────

    def set_rango(self, desde_iso, hasta_iso):
        """Aplica un rango por código (los presets de Análisis) y lo refleja
        en los campos en DD-MM-AAAA, para que el usuario vea qué quedó
        aplicado y pueda seguir ajustándolo a mano desde ahí. No dispara
        `on_manual` -- no lo escribió el usuario."""
        self._e_desde.delete(0, "end")
        self._e_hasta.delete(0, "end")
        if desde_iso:
            self._e_desde.insert(0, formato.fecha(desde_iso))
        if hasta_iso:
            self._e_hasta.insert(0, formato.fecha(hasta_iso))
        self._on_cambio(desde_iso, hasta_iso)

    # ── Acciones del usuario ──────────────────────────────────────────────

    def _aplicar(self):
        desde_txt = self._e_desde.get().strip()
        hasta_txt = self._e_hasta.get().strip()

        for txt in (desde_txt, hasta_txt):
            if txt and formato.a_iso(txt) is None:
                messagebox.showerror(
                    "Fecha inválida",
                    f"'{txt}' no es una fecha válida. Usá el formato DD-MM-AAAA (ej. 10-07-2026).",
                    parent=self)
                return

        desde_iso = formato.a_iso(desde_txt) if desde_txt else None
        hasta_iso = formato.a_iso(hasta_txt) if hasta_txt else None
        if desde_iso and hasta_iso and desde_iso > hasta_iso:
            messagebox.showerror("Error", "La fecha 'Desde' no puede ser posterior a 'Hasta'.",
                                 parent=self)
            return

        # Un campo vacío no es un error: filtrar solo con "Desde" (o solo con
        # "Hasta") es un uso normal -- "todo lo que va de este mes".
        if self._on_manual:
            self._on_manual()
        self._on_cambio(desde_iso, hasta_iso)

    def _limpiar(self):
        self._e_desde.delete(0, "end")
        self._e_hasta.delete(0, "end")
        if self._on_manual:
            self._on_manual()
        self._on_cambio(None, None)


class BotonesPreset(ctk.CTkFrame):
    """Fila de atajos de rango: "Ver: [Hoy] [Esta semana] [Este mes]".

    Cada preset es una tupla `(key, texto, ancho, calcular)`, donde
    `calcular()` devuelve `(desde_iso, hasta_iso)` -- o None para no aplicar
    nada (p. ej. si necesita consultar la BD y falla, o no hay datos: ahí el
    propio `calcular` avisa y el preset no queda seleccionado).

    Al tocar uno aplica el rango con `filtro.set_rango()`, que **no** dispara
    el `on_manual` del filtro -- si lo disparara, el preset se apagaría a sí
    mismo al aplicarse. El seleccionado queda en dorado, mismo criterio que
    las pestañas activas del resto de la app.

    La pantalla tiene que enganchar `olvidar()` al `on_manual` del filtro: si
    el usuario filtra o limpia a mano, ningún preset representa ya lo que se
    está viendo.
    """

    def __init__(self, parent, filtro, presets, etiqueta="Ver:", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self._filtro = filtro
        self._activo = None
        self._botones = {}

        ctk.CTkLabel(self, text=etiqueta, text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(0, 8))
        for key, texto, ancho, calcular in presets:
            b = ctk.CTkButton(self, text=texto, width=ancho,
                              command=lambda k=key, f=calcular: self._aplicar(k, f))
            b.pack(side="left", padx=(0, 6))
            self._botones[key] = b
        self._pintar()

    def olvidar(self):
        """El rango dejó de venir de un preset: ninguno queda resaltado."""
        self._activo = None
        self._pintar()

    def _aplicar(self, key, calcular):
        rango = calcular()
        if rango is None:
            return
        self._activo = key
        self._pintar()
        self._filtro.set_rango(*rango)

    def _pintar(self):
        activo = {"fg_color": theme.ACCENT, "hover_color": theme.ACCENT_HOVER,
                  "text_color": theme.ACCENT_TEXT}
        inactivo = {"fg_color": theme.NEUTRAL, "hover_color": theme.NEUTRAL_HOVER,
                    "text_color": theme.TEXT_PRIMARY}
        for key, btn in self._botones.items():
            btn.configure(**(activo if key == self._activo else inactivo))


class Paginador(ctk.CTkFrame):
    """Barra "‹ Anterior · Página X de Y · Siguiente ›" para listas largas.

    El motivo es de rendimiento: cada fila de una lista son varios widgets de
    customtkinter y CTk es lento creándolos, así que dibujar cientos de golpe
    se siente lento. Paginar acota cuántas filas se pintan por vez.

    La pantalla la packea (normalmente al fondo) y, en su `refresh()`, le pasa
    la lista COMPLETA a `pagina_de(items)`: el paginador reencaja la página al
    rango válido (por si la lista se achicó), redibuja sus propios botones y
    devuelve solo el tramo que toca dibujar. Con una sola página no muestra
    controles -- no hay adónde navegar.

    `on_cambio()` se llama cuando el usuario toca una flecha; la pantalla
    responde volviendo a hacer `refresh()`, de donde sale el nuevo tramo. El
    paginador NO guarda los datos, solo el número de página -- misma división
    que `FiltroFechas`, donde el estado real vive en la pantalla.
    """

    def __init__(self, parent, on_cambio, por_pagina, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self._on_cambio = on_cambio
        self._por_pagina = por_pagina
        self._pagina = 0

    def pagina_de(self, items):
        """Reencaja la página, redibuja la barra y devuelve el sub-tramo de
        `items` correspondiente a la página actual."""
        total_paginas = max(1, (len(items) + self._por_pagina - 1) // self._por_pagina)
        self._pagina = max(0, min(self._pagina, total_paginas - 1))
        self._redibujar(total_paginas)
        inicio = self._pagina * self._por_pagina
        return items[inicio:inicio + self._por_pagina]

    def reset(self):
        """Volver a la primera página. La pantalla la llama cuando cambia lo
        que se lista (p. ej. un filtro nuevo): la página en la que estabas no
        tiene por qué existir en el nuevo resultado."""
        self._pagina = 0

    def _redibujar(self, total_paginas):
        for w in self.winfo_children():
            w.destroy()
        if total_paginas <= 1:
            return
        ctk.CTkButton(self, text="‹ Anterior", width=110,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      state="normal" if self._pagina > 0 else "disabled",
                      command=lambda: self._ir(self._pagina - 1)).pack(side="left")
        ctk.CTkLabel(self, text=f"Página {self._pagina + 1} de {total_paginas}",
                     text_color=theme.TEXT_SECONDARY).pack(side="left", expand=True)
        ctk.CTkButton(self, text="Siguiente ›", width=110,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      state="normal" if self._pagina < total_paginas - 1 else "disabled",
                      command=lambda: self._ir(self._pagina + 1)).pack(side="right")

    def _ir(self, n):
        self._pagina = n
        self._on_cambio()


class _CalendarioPopup(ctk.CTkToplevel):
    """Calendario de un mes para elegir una fecha con el mouse.

    Lo abre el botón "▾" de `FiltroFechas` y **solo escribe la fecha en el
    campo: no aplica el filtro**. Es a propósito y es el mismo criterio que
    tipear a mano -- el rango se aplica con "Filtrar", así se pueden elegir
    los dos extremos antes de que la lista se mueva. Si al elegir "Desde" ya
    filtrara, el "Hasta" se cargaría sobre una lista a medio filtrar.

    Se posiciona debajo del botón que lo abrió (no centrado como el resto de
    los diálogos): está atado a ese campo, no a la pantalla.
    """

    def __init__(self, parent, boton, fecha_iso, on_elegir):
        super().__init__(parent)
        self.title("Elegir fecha")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

        self._on_elegir = on_elegir
        self._elegido = fecha_iso  # el ya cargado en el campo, para resaltarlo
        base = datetime.now()
        if fecha_iso:
            try:
                base = datetime.strptime(fecha_iso, "%Y-%m-%d")
            except ValueError:
                pass
        self._anio, self._mes = base.year, base.month

        self._build_ui()
        self._dibujar_mes()
        self.update_idletasks()
        self.geometry(f"+{boton.winfo_rootx()}+{boton.winfo_rooty() + boton.winfo_height() + 4}")

    def _build_ui(self):
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkButton(cab, text="‹", width=30,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=lambda: self._mover_mes(-1)).pack(side="left")
        self._lbl_mes = ctk.CTkLabel(cab, text="", text_color=theme.TEXT_PRIMARY,
                                     font=ctk.CTkFont(size=13, weight="bold"))
        self._lbl_mes.pack(side="left", expand=True)
        ctk.CTkButton(cab, text="›", width=30,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=lambda: self._mover_mes(1)).pack(side="right")

        self._grilla = ctk.CTkFrame(self, fg_color="transparent")
        self._grilla.pack(padx=10, pady=(0, 6))

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(pie, text="Hoy", width=70,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=lambda: self._elegir(datetime.now().strftime("%Y-%m-%d"))).pack(side="left")
        ctk.CTkButton(pie, text="Cancelar", width=90,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self.destroy).pack(side="right")

    def _dibujar_mes(self):
        self._lbl_mes.configure(text=f"{_MESES[self._mes - 1]} {self._anio}")
        for w in self._grilla.winfo_children():
            w.destroy()

        for col, dia in enumerate(_DIAS_SEMANA):
            ctk.CTkLabel(self._grilla, text=dia, width=34, text_color=theme.TEXT_DISABLED,
                         font=ctk.CTkFont(size=11)).grid(row=0, column=col, padx=1, pady=(0, 2))

        hoy_iso = datetime.now().strftime("%Y-%m-%d")
        semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(self._anio, self._mes)
        for fila, semana in enumerate(semanas, start=1):
            for col, dia in enumerate(semana):
                if dia == 0:  # relleno del mes anterior/siguiente
                    continue
                iso = f"{self._anio:04d}-{self._mes:02d}-{dia:02d}"
                if iso == self._elegido:
                    # El día ya cargado en el campo: dorado lleno, mismo
                    # criterio que las pestañas activas del resto de la app.
                    colores = {"fg_color": theme.ACCENT, "hover_color": theme.ACCENT_HOVER,
                               "text_color": theme.ACCENT_TEXT}
                elif iso == hoy_iso:
                    # Hoy: solo el número en dorado, para ubicarse sin
                    # competir con el día efectivamente elegido.
                    colores = {"fg_color": "transparent", "hover_color": theme.NEUTRAL_HOVER,
                               "text_color": theme.ACCENT}
                else:
                    colores = {"fg_color": "transparent", "hover_color": theme.NEUTRAL_HOVER,
                               "text_color": theme.TEXT_PRIMARY}
                ctk.CTkButton(self._grilla, text=str(dia), width=34, height=28,
                              command=lambda i=iso: self._elegir(i), **colores).grid(
                    row=fila, column=col, padx=1, pady=1)

    def _mover_mes(self, delta):
        mes = self._mes + delta
        # Aritmética 0-based para que diciembre→enero cambie de año solo.
        self._anio += (mes - 1) // 12
        self._mes = (mes - 1) % 12 + 1
        self._dibujar_mes()

    def _elegir(self, iso):
        self._on_elegir(iso)
        self.destroy()
