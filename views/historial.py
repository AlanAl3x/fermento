from datetime import datetime, timedelta

import customtkinter as ctk
from tkinter import messagebox
import database as db
from views import dialogos, formato, theme, ticket, widgets
from views.cortes import CortesFrame


class HistorialFrame(ctk.CTkFrame):
    """Contenedor con dos sub-pestañas: Ventas (listado crudo de tickets)
    y Cortes (cierres de caja con desglose por producto y export a CSV)."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._sub_actual = "ventas"
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Historial", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")

        sub_nav = ctk.CTkFrame(header, fg_color="transparent")
        sub_nav.pack(side="right")
        self._btn_ventas = ctk.CTkButton(sub_nav, text="Ventas", width=90,
                                         command=lambda: self._mostrar_sub("ventas"))
        self._btn_ventas.pack(side="left", padx=(0, 6))
        self._btn_cortes = ctk.CTkButton(sub_nav, text="Cortes", width=90,
                                         command=lambda: self._mostrar_sub("cortes"))
        self._btn_cortes.pack(side="left")

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True)

        self._sub_frames = {
            "ventas": _VentasPanel(contenedor),
            "cortes": CortesFrame(contenedor),
        }
        self._sub_buttons = {"ventas": self._btn_ventas, "cortes": self._btn_cortes}

        self._mostrar_sub("ventas")

    def _mostrar_sub(self, nombre):
        for frame in self._sub_frames.values():
            frame.pack_forget()
        frame = self._sub_frames[nombre]
        frame.pack(fill="both", expand=True)
        frame.refresh()
        self._sub_actual = nombre

        for key, btn in self._sub_buttons.items():
            if key == nombre:
                btn.configure(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                              text_color=theme.ACCENT_TEXT)
            else:
                btn.configure(fg_color=theme.NAV_INACTIVE, hover_color=theme.NAV_INACTIVE_HOVER,
                              text_color=theme.TEXT_PRIMARY)

    def refresh(self):
        """Llamado por main.py al navegar a la sección Historial."""
        self._sub_frames[self._sub_actual].refresh()


# ── Sub-pestaña Ventas ────────────────────────────────────────────────────────

# La lista se pagina de a 50 filas (ver `widgets.Paginador` para el porqué).
# Con y sin filtro de fechas por igual. Las páginas van de la más reciente a
# la más antigua (las ventas ya vienen ORDER BY fecha DESC).
_POR_PAGINA = 50


class _VentasPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        # Rango de fechas aplicado, en formato ISO internamente (comparable
        # como texto contra ventas.fecha; ver database.py) aunque el
        # usuario escribe y ve DD-MM-AAAA. None = sin filtro en ese
        # extremo. Se guarda separado de lo que hay tecleado en los Entry
        # para que escribir una fecha a medias no filtre la lista hasta
        # apretar "Filtrar" -- si filtrara en vivo, cada letra tipeada de
        # un año incompleto (ej. "202") rompería la comparación de fechas.
        self._desde = None
        self._hasta = None
        self._build_ui()

    def _build_ui(self):
        # `on_manual` apaga el atajo resaltado cuando el usuario filtra o
        # limpia a mano; los atajos aplican con `set_rango()`, que no lo
        # dispara (si lo hiciera, se apagarían solos al aplicarse).
        self._filtro = widgets.FiltroFechas(self, on_cambio=self._set_rango,
                                            on_manual=self._olvidar_preset)
        self._filtro.pack(fill="x", padx=20, pady=(0, 4))

        # Atajos de rango: las tres preguntas que se hacen de verdad al abrir
        # el historial ("¿cuánto vendí hoy?", "¿y en la semana?"), sin tener
        # que elegir fechas. "Hasta" queda abierto en semana/mes: el rango es
        # "desde tal día hasta ahora".
        self._presets = widgets.BotonesPreset(self, self._filtro, [
            ("hoy", "Hoy", 80, self._rango_hoy),
            ("semana", "Esta semana", 120, self._rango_semana),
            ("mes", "Este mes", 100, self._rango_mes),
        ])
        self._presets.pack(fill="x", padx=20, pady=(0, 10))

        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=6)
        enc.pack(fill="x", padx=20, pady=(0, 2))
        ctk.CTkLabel(enc, text="Fecha", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY,
                     anchor="w").pack(side="left", expand=True, fill="x", padx=10, pady=6)
        ctk.CTkLabel(enc, text="Total", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY,
                     width=110, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(enc, text="", width=196).pack(side="left", padx=6)

        # Barra de paginación anclada al fondo (side="bottom" antes de la
        # lista, para que la lista ocupe lo de arriba y no haya que scrollear
        # hasta el final para cambiar de página).
        self._pag = widgets.Paginador(self, on_cambio=self._al_paginar, por_pagina=_POR_PAGINA)
        self._pag.pack(side="bottom", fill="x", padx=20, pady=(0, 12))

        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.lista.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        self.refresh()

    def refresh(self):
        for w in self.lista.winfo_children():
            w.destroy()

        try:
            ventas = db.get_ventas()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        hay_filtro = self._desde is not None or self._hasta is not None
        if self._desde:
            ventas = [v for v in ventas if v["fecha"][:10] >= self._desde]
        if self._hasta:
            ventas = [v for v in ventas if v["fecha"][:10] <= self._hasta]

        # El paginador reencaja la página y devuelve solo el tramo a dibujar
        # (lista vacía -> tramo vacío, y la barra se oculta sola).
        pagina = self._pag.pagina_de(ventas)
        if not pagina:
            texto = ("No hay ventas en el rango de fechas seleccionado." if hay_filtro
                     else "No hay ventas registradas.")
            ctk.CTkLabel(self.lista, text=texto, text_color=theme.TEXT_DISABLED).pack(pady=20)
            return

        for v in pagina:
            fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
            fila.pack(fill="x", pady=2)

            if v.get("anulada"):
                fecha_txt = formato.fecha(v["fecha"]) + "  ·  ANULADA"
                color_fecha = theme.DANGER
            elif v.get("corte_id") is None:
                fecha_txt = formato.fecha(v["fecha"]) + "  ·  sin cortar"
                color_fecha = theme.WARNING
            else:
                fecha_txt = formato.fecha(v["fecha"])
                color_fecha = theme.TEXT_PRIMARY
            ctk.CTkLabel(fila, text=fecha_txt, anchor="w", text_color=color_fecha).pack(
                side="left", expand=True, fill="x", padx=10, pady=8)
            ctk.CTkLabel(fila, text=f"${v['total']:.2f}", text_color=theme.TEXT_PRIMARY,
                         width=110, anchor="center").pack(side="left", padx=6)
            ctk.CTkButton(fila, text="Detalle", width=90,
                          fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                          text_color=theme.ACCENT_TEXT,
                          command=lambda v=v: self._ver_detalle(v)).pack(
                side="left", padx=4, pady=6)
            if not v.get("anulada") and v.get("corte_id") is None:
                ctk.CTkButton(fila, text="Anular", width=90,
                              fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                              command=lambda v=v: self._anular(v)).pack(
                    side="left", padx=4, pady=6)

    def _al_paginar(self):
        """El paginador cambió de página: redibujar y volver arriba del
        scroll (si no, la página nueva quedaría a la altura de la anterior)."""
        self.refresh()
        try:
            self.lista._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def _set_rango(self, desde_iso, hasta_iso):
        """Callback de `widgets.FiltroFechas`: llega ya validado y en ISO,
        venga de los campos o de un atajo. Un rango nuevo arranca en la
        primera página -- la página en la que estabas no tiene por qué
        existir en el resultado filtrado."""
        self._desde = desde_iso
        self._hasta = hasta_iso
        self._pag.reset()
        self.refresh()

    def _olvidar_preset(self):
        """El usuario filtró/limpió a mano: ningún atajo queda resaltado."""
        self._presets.olvidar()

    @staticmethod
    def _rango_hoy():
        hoy = datetime.now().strftime("%Y-%m-%d")
        return hoy, hoy

    @staticmethod
    def _rango_semana():
        """Semana corriente arrancando el lunes (weekday(): 0 = lunes)."""
        hoy = datetime.now()
        return (hoy - timedelta(days=hoy.weekday())).strftime("%Y-%m-%d"), None

    @staticmethod
    def _rango_mes():
        hoy = datetime.now()
        return f"{hoy.year:04d}-{hoy.month:02d}-01", None

    def _ver_detalle(self, v):
        d = _DetalleDialog(self, v)
        self.wait_window(d)

    def _anular(self, v):
        d = _AnularDialog(self, v)
        self.wait_window(d)
        self.refresh()


class _DetalleDialog(ctk.CTkToplevel):
    def __init__(self, parent, venta):
        super().__init__(parent)
        self.title(f"Detalle — {formato.fecha(venta['fecha'])}")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self._build_ui(venta)
        # Alto dinámico: la sección "ANULADA" agrega una línea extra que un
        # alto fijo dejaría cortada (mismo problema que _DialogoProducto).
        self.update_idletasks()
        dialogos.centrar_sobre(self, parent, 500, self.winfo_reqheight())

    def _build_ui(self, v):
        ctk.CTkLabel(self, text=f"Fecha: {formato.fecha(v['fecha'])}", anchor="w",
                     text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=20, pady=(16, 6))

        if v.get("anulada"):
            ctk.CTkLabel(
                self,
                text=f"ANULADA el {formato.fecha(v['fecha_anulacion'])}\nMotivo: {v['motivo_anulacion']}",
                anchor="w", justify="left", text_color=theme.DANGER,
                wraplength=390,
            ).pack(anchor="w", padx=20, pady=(0, 6))

        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=4)
        enc.pack(fill="x", padx=20, pady=(0, 2))
        for txt in ["Producto", "Cant.", "P. Unit.", "Subtotal", "Margen"]:
            ctk.CTkLabel(enc, text=txt, text_color=theme.TEXT_SECONDARY,
                         font=ctk.CTkFont(weight="bold")).pack(
                side="left", expand=True, fill="x", padx=6, pady=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=170)
        scroll.pack(fill="x", padx=20)

        try:
            detalle = db.get_detalle_venta(v["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            detalle = []

        # Margen por línea: "—" si esa línea no tenía costo cargado al
        # momento de la venta (costo_unitario congelado en 0) -- no se
        # calcula como si el costo fuera 0 real, sería un margen falso.
        margen_total = 0.0
        hay_algun_costo = False
        hay_todos_costos = True
        for item in detalle:
            fila = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=4)
            fila.pack(fill="x", pady=1)
            for txt in [item["nombre"], str(item["cantidad"]),
                        f"${item['precio_unitario']:.2f}", f"${item['subtotal']:.2f}"]:
                ctk.CTkLabel(fila, text=txt, text_color=theme.TEXT_PRIMARY).pack(
                    side="left", expand=True, fill="x", padx=6, pady=5)

            if item["costo_unitario"] > 0:
                margen_linea = item["subtotal"] - item["costo_subtotal"]
                margen_total += margen_linea
                hay_algun_costo = True
                texto_margen = f"${margen_linea:.2f}"
                color_margen = theme.SUCCESS if margen_linea >= 0 else theme.DANGER
            else:
                hay_todos_costos = False
                texto_margen = "—"
                color_margen = theme.TEXT_DISABLED
            ctk.CTkLabel(fila, text=texto_margen, text_color=color_margen).pack(
                side="left", expand=True, fill="x", padx=6, pady=5)

        ctk.CTkLabel(self, text=f"Total: ${v['total']:.2f}", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="e").pack(anchor="e", padx=28, pady=(10, 2))

        if hay_algun_costo:
            texto_margen_total = f"Margen: ${margen_total:.2f}"
            if not hay_todos_costos:
                texto_margen_total += "  (algunos productos sin costo cargado)"
            color_margen_total = theme.SUCCESS if margen_total >= 0 else theme.DANGER
        else:
            texto_margen_total = "Margen: — (sin costos cargados)"
            color_margen_total = theme.TEXT_DISABLED
        ctk.CTkLabel(self, text=texto_margen_total, text_color=color_margen_total,
                     font=ctk.CTkFont(size=12), anchor="e").pack(anchor="e", padx=28, pady=(0, 10))
        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=(0, 16))
        # Reimprimir el ticket de una venta pasada (cliente que lo pide
        # después, papel que se rompió). No se ofrece para anuladas: un
        # ticket de una venta anulada solo confundiría.
        if not v.get("anulada"):
            ctk.CTkButton(botones, text="Ticket", width=100,
                          fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                          text_color=theme.ACCENT_TEXT,
                          command=lambda: self._generar_ticket(v)).pack(side="left", padx=6)
        ctk.CTkButton(botones, text="Cerrar", width=100,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self.destroy).pack(side="left", padx=6)

    def _generar_ticket(self, v):
        try:
            detalle = db.get_detalle_venta(v["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        try:
            ticket.generar_y_abrir(v, detalle)
        except ticket.TicketError as e:
            messagebox.showerror("Ticket", str(e), parent=self)


class _AnularDialog(ctk.CTkToplevel):
    def __init__(self, parent, venta):
        super().__init__(parent)
        self.title("Anular venta")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.venta = venta
        self._build_ui()
        self.update_idletasks()
        dialogos.centrar_sobre(self, parent, 360, self.winfo_reqheight())
        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.e_motivo.focus()

    def _build_ui(self):
        v = self.venta
        ctk.CTkLabel(self, text=f"Anular venta del {formato.fecha(v['fecha'])}\nTotal: ${v['total']:.2f}",
                     text_color=theme.TEXT_PRIMARY, justify="left").pack(
            anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(self,
                     text="Devuelve el stock vendido al inventario.\n"
                          "El registro queda en el historial marcado como anulado.",
                     text_color=theme.TEXT_SECONDARY, justify="left",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=24, pady=(0, 10))

        ctk.CTkLabel(self, text="Motivo:", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24, pady=(0, 2))
        self.e_motivo = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_motivo.pack(padx=24)

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=18)
        ctk.CTkButton(botones, text="Cancelar", width=100,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self.destroy).pack(side="left", padx=6)
        ctk.CTkButton(botones, text="Anular venta", width=140,
                      fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                      command=self._confirmar).pack(side="left", padx=6)

    def _confirmar(self):
        motivo = self.e_motivo.get().strip()
        if not motivo:
            messagebox.showerror("Error", "Tenés que indicar un motivo para anular la venta.",
                                  parent=self)
            return
        try:
            db.anular_venta(self.venta["id"], motivo)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.destroy()
