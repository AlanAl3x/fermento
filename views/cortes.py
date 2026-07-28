import csv

import customtkinter as ctk
from tkinter import messagebox, filedialog

import database as db
from views import formato, theme, widgets

# Cortes se pagina de a 30 (ver `widgets.Paginador`). El tamaño sale de que un
# corte es aproximadamente diario, así que ~30 cortes ≈ un mes: cada página es
# más o menos "el mes". Van del más reciente al más antiguo (ORDER BY fecha DESC).
_POR_PAGINA_CORTES = 30


def _exportar_corte_csv(parent, corte):
    """Diálogo para guardar el desglose por producto de un corte como CSV."""
    try:
        detalle = db.get_corte_detalle(corte["id"])
    except db.DBError as e:
        messagebox.showerror("Error de base de datos", str(e), parent=parent)
        return

    # El nombre de archivo sugerido usa la fecha en formato ISO (AAAA-MM-DD),
    # no el DD-MM-AAAA que se muestra en pantalla: así los archivos quedan
    # ordenados cronológicamente por nombre en el explorador de Windows.
    nombre_sugerido = f"corte_{corte['id']}_{corte['fecha'][:10]}.csv"
    ruta = filedialog.asksaveasfilename(
        parent=parent, title="Exportar corte a CSV",
        defaultextension=".csv", initialfile=nombre_sugerido,
        filetypes=[("CSV", "*.csv")])
    if not ruta:
        return

    try:
        # utf-8-sig (con BOM) para que Excel en Windows muestre bien los
        # acentos; sin el BOM, Excel suele mostrar "Ã³" en vez de "ó".
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Corte", corte["id"], "Fecha", formato.fecha(corte["fecha"])])
            w.writerow(["Cantidad de ventas", corte["cantidad_ventas"]])
            w.writerow(["Total", f"{corte['total_ventas']:.2f}"])
            # Margen total: en blanco si NINGÚN producto de este corte tenía
            # costo cargado -- no se muestra un 0 que se leería como "costo
            # cero real" (ver misma convención en Productos/Análisis).
            if corte["costo_total"] > 0:
                w.writerow(["Margen de ganancia total", f"{corte['total_ventas'] - corte['costo_total']:.2f}"])
                if any(item["costo_total"] == 0 for item in detalle):
                    w.writerow(["", "Nota: incluye productos sin costo cargado (tratados como costo 0)"])
            else:
                w.writerow(["Margen de ganancia total", ""])
            w.writerow([])
            w.writerow(["Producto", "Cantidad", "Total", "Costo", "Margen de ganancia"])
            for item in detalle:
                if item["costo_total"] > 0:
                    costo_txt = f"{item['costo_total']:.2f}"
                    margen_txt = f"{item['total'] - item['costo_total']:.2f}"
                else:
                    costo_txt = ""
                    margen_txt = ""
                w.writerow([item["nombre_producto"], item["cantidad"], f"{item['total']:.2f}",
                           costo_txt, margen_txt])
        messagebox.showinfo("Exportado", f"Corte exportado a:\n{ruta}", parent=parent)
    except OSError as e:
        messagebox.showerror("Error al exportar", str(e), parent=parent)


class CortesFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._build_ui()

    def _build_ui(self):
        # ── Resumen de ventas pendientes + botón "Hacer corte" ─────────────────
        resumen = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=6)
        resumen.pack(fill="x", padx=20, pady=(20, 10))

        self._lbl_resumen = ctk.CTkLabel(resumen, text="", text_color=theme.TEXT_PRIMARY,
                                         anchor="w", font=ctk.CTkFont(size=13))
        self._lbl_resumen.pack(side="left", padx=14, pady=12, fill="x", expand=True)

        self._btn_corte = ctk.CTkButton(resumen, text="Hacer corte",
                                        fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
                                        command=self._hacer_corte)
        self._btn_corte.pack(side="right", padx=14, pady=12)

        # ── Lista de cortes ya hechos ────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(6, 0))
        ctk.CTkLabel(header, text="Cortes anteriores", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Exportar todas las ventas", width=180,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self._exportar_ventas_detalle_csv).pack(side="right", padx=(0, 8))

        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=6)
        enc.pack(fill="x", padx=20, pady=(8, 2))
        ctk.CTkLabel(enc, text="Fecha", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, anchor="w").pack(
            side="left", expand=True, fill="x", padx=10, pady=6)
        ctk.CTkLabel(enc, text="Ventas", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=70, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(enc, text="Total", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=100, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(enc, text="", width=180).pack(side="left", padx=6)

        # Barra de paginación anclada al fondo (side="bottom" antes de la
        # lista, para no scrollear hasta el final para cambiar de página).
        self._pag = widgets.Paginador(self, on_cambio=self._al_paginar,
                                      por_pagina=_POR_PAGINA_CORTES)
        self._pag.pack(side="bottom", fill="x", padx=20, pady=(0, 12))

        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.lista.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        self.refresh()

    def refresh(self):
        try:
            pendiente = db.preview_corte()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            pendiente = {"cantidad_ventas": 0, "total_ventas": 0.0}

        if pendiente["cantidad_ventas"] == 0:
            self._lbl_resumen.configure(text="No hay ventas pendientes de cortar.")
            self._btn_corte.configure(state="disabled")
        else:
            self._lbl_resumen.configure(
                text=f"Pendiente de cortar: {pendiente['cantidad_ventas']} venta(s) — "
                     f"${pendiente['total_ventas']:.2f}")
            self._btn_corte.configure(state="normal")

        for w in self.lista.winfo_children():
            w.destroy()

        try:
            cortes = db.get_cortes()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        # El "último corte" (el único con botón Deshacer) se calcula sobre la
        # lista COMPLETA, no sobre la página: si no, en una página que no sea
        # la primera aparecería un Deshacer sobre un corte que no es el último.
        # Como van ORDER BY fecha DESC, ese corte cae siempre en la página 1.
        pagina = self._pag.pagina_de(cortes)
        if not pagina:
            ctk.CTkLabel(self.lista, text="Todavía no se hizo ningún corte.",
                         text_color=theme.TEXT_DISABLED).pack(pady=20)
            return

        id_ultimo_corte = max(c["id"] for c in cortes)
        for corte in pagina:
            self._build_fila(corte, es_ultimo=(corte["id"] == id_ultimo_corte))

    def _al_paginar(self):
        """El paginador cambió de página: redibujar y volver arriba del scroll."""
        self.refresh()
        try:
            self.lista._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def _build_fila(self, corte, es_ultimo=False):
        fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
        fila.pack(fill="x", pady=2)

        ctk.CTkLabel(fila, text=formato.fecha(corte["fecha"]), anchor="w", text_color=theme.TEXT_PRIMARY).pack(
            side="left", expand=True, fill="x", padx=10, pady=8)
        ctk.CTkLabel(fila, text=str(corte["cantidad_ventas"]), text_color=theme.TEXT_SECONDARY,
                     width=70, anchor="center").pack(side="left", padx=6)
        ctk.CTkLabel(fila, text=f"${corte['total_ventas']:.2f}", text_color=theme.TEXT_PRIMARY,
                     width=100, anchor="center").pack(side="left", padx=6)

        ctk.CTkButton(fila, text="Ver detalle", width=100,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ACCENT_TEXT,
                      command=lambda c=corte: self._ver_detalle(c)).pack(side="left", padx=(6, 4), pady=6)
        ctk.CTkButton(fila, text="CSV", width=60,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=lambda c=corte: _exportar_corte_csv(self, c)).pack(side="left", padx=(0, 6))

        if es_ultimo:
            ctk.CTkButton(fila, text="Deshacer", width=90,
                          fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                          command=lambda c=corte: self._deshacer_corte(c)).pack(side="left", padx=(0, 6))

    def _hacer_corte(self):
        try:
            pendiente = db.preview_corte()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        if pendiente["cantidad_ventas"] == 0:
            messagebox.showinfo("Sin ventas pendientes",
                                "No hay ventas pendientes de cortar.", parent=self)
            return

        detalle_txt = "\n".join(
            f"  {d['nombre']}: {d['cantidad']} — ${d['total']:.2f}" for d in pendiente["desglose"]
        )
        if not messagebox.askyesno(
                "Confirmar corte",
                f"Se van a cerrar {pendiente['cantidad_ventas']} venta(s) por un total de "
                f"${pendiente['total_ventas']:.2f}.\n\nDesglose:\n{detalle_txt}\n\n"
                "Esta acción no se puede deshacer. ¿Continuar?",
                parent=self):
            return

        try:
            db.hacer_corte()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        # Sin modal de "Corte #N registrado": el corte recién hecho aparece
        # primero en la lista al refrescar y el resumen de pendientes vuelve a
        # cero -- el resultado ya está a la vista. Mismo criterio con el que se
        # sacó el modal de éxito del flujo de venta (2026-07-20). La
        # confirmación previa SÍ se queda: ahí el desglose por producto no
        # está en pantalla, a diferencia del carrito.
        self._pag.reset()  # el corte nuevo está en la página 1
        self.refresh()

    def _deshacer_corte(self, corte):
        if not messagebox.askyesno(
                "Deshacer corte",
                f"Se va a deshacer el corte #{corte['id']} ({formato.fecha(corte['fecha'])}).\n\n"
                f"Sus {corte['cantidad_ventas']} venta(s) por ${corte['total_ventas']:.2f} "
                "volverán a quedar pendientes de cortar, y el corte se borra.\n\n"
                "Esta acción no se puede deshacer. ¿Continuar?",
                parent=self):
            return

        try:
            db.deshacer_ultimo_corte()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        # Igual que al hacer el corte: sin modal de éxito. El corte desaparece
        # de la lista y sus ventas reaparecen en el resumen de pendientes.
        self.refresh()

    def _ver_detalle(self, corte):
        d = _DetalleCorteDialog(self, corte)
        self.wait_window(d)

    def _exportar_ventas_detalle_csv(self):
        try:
            detalle = db.get_ventas_detalle_export()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        if not detalle:
            messagebox.showinfo("Sin datos", "Todavía no hay ventas para exportar.", parent=self)
            return

        ruta = filedialog.asksaveasfilename(
            parent=self, title="Exportar ventas detalladas a CSV",
            defaultextension=".csv", initialfile="ventas_detalle.csv",
            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        try:
            # Formato "largo" a nivel de venta individual: una fila por
            # producto vendido, con la fecha/hora exacta de esa venta
            # puntual -- sirve para analizar qué se vende más a qué hora
            # del día.
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Venta ID", "Fecha", "Producto", "Cantidad",
                           "Precio unitario", "Subtotal", "Costo unitario", "Margen de ganancia"])
                for item in detalle:
                    # Costo/Margen en blanco si esa línea no tenía costo
                    # cargado al momento de la venta (congelado en 0) --
                    # no es lo mismo que "costo cero real".
                    if item["costo_unitario"] > 0:
                        costo_txt = f"{item['costo_unitario']:.2f}"
                        margen_txt = f"{item['subtotal'] - item['costo_subtotal']:.2f}"
                    else:
                        costo_txt = ""
                        margen_txt = ""
                    w.writerow([item["venta_id"], formato.fecha(item["fecha"]), item["producto"],
                               item["cantidad"], f"{item['precio_unitario']:.2f}",
                               f"{item['subtotal']:.2f}", costo_txt, margen_txt])
            messagebox.showinfo("Exportado", f"Ventas exportadas a:\n{ruta}", parent=self)
        except OSError as e:
            messagebox.showerror("Error al exportar", str(e), parent=self)


class _DetalleCorteDialog(ctk.CTkToplevel):
    def __init__(self, parent, corte):
        super().__init__(parent)
        self.title(f"Corte #{corte['id']} — {formato.fecha(corte['fecha'])}")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self._corte = corte
        self._build_ui(corte)

    def _build_ui(self, corte):
        ctk.CTkLabel(self, text=f"Fecha: {formato.fecha(corte['fecha'])}", anchor="w",
                     text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(self, text=f"{corte['cantidad_ventas']} venta(s)", anchor="w",
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(0, 6))

        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=4)
        enc.pack(fill="x", padx=20, pady=(0, 2))
        for txt in ["Producto", "Cant.", "Total", "Margen"]:
            ctk.CTkLabel(enc, text=txt, text_color=theme.TEXT_SECONDARY,
                         font=ctk.CTkFont(weight="bold")).pack(
                side="left", expand=True, fill="x", padx=6, pady=4)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=170, width=440)
        scroll.pack(fill="x", padx=20)

        try:
            detalle = db.get_corte_detalle(corte["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            detalle = []

        for item in detalle:
            fila = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=4)
            fila.pack(fill="x", pady=1)
            for txt in [item["nombre_producto"], str(item["cantidad"]), f"${item['total']:.2f}"]:
                ctk.CTkLabel(fila, text=txt, text_color=theme.TEXT_PRIMARY).pack(
                    side="left", expand=True, fill="x", padx=6, pady=5)

            if item["costo_total"] > 0:
                margen_item = item["total"] - item["costo_total"]
                texto_margen = f"${margen_item:.2f}"
                color_margen = theme.SUCCESS if margen_item >= 0 else theme.DANGER
            else:
                texto_margen = "—"
                color_margen = theme.TEXT_DISABLED
            ctk.CTkLabel(fila, text=texto_margen, text_color=color_margen).pack(
                side="left", expand=True, fill="x", padx=6, pady=5)

        ctk.CTkLabel(self, text=f"Total: ${corte['total_ventas']:.2f}", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="e").pack(anchor="e", padx=28, pady=(10, 2))

        if corte["costo_total"] > 0:
            margen_corte = corte["total_ventas"] - corte["costo_total"]
            texto_margen_corte = f"Margen: ${margen_corte:.2f}"
            # Los productos sin costo cargado suman costo 0 a este total
            # (no se excluyen), así que si hay alguno el número queda
            # optimista -- se avisa en vez de mostrarlo como si fuera
            # completo, mismo criterio que el detalle de una venta.
            if any(item["costo_total"] == 0 for item in detalle):
                texto_margen_corte += "  (algunos productos sin costo cargado)"
            color_margen_corte = theme.SUCCESS if margen_corte >= 0 else theme.DANGER
        else:
            texto_margen_corte = "Margen: — (sin costos cargados)"
            color_margen_corte = theme.TEXT_DISABLED
        ctk.CTkLabel(self, text=texto_margen_corte, text_color=color_margen_corte,
                     font=ctk.CTkFont(size=12), anchor="e").pack(anchor="e", padx=28, pady=(0, 10))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=(0, 16))
        ctk.CTkButton(botones, text="Exportar CSV", width=120,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=lambda: _exportar_corte_csv(self, self._corte)).pack(side="left", padx=6)
        ctk.CTkButton(botones, text="Cerrar", width=100,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self.destroy).pack(side="left", padx=6)
