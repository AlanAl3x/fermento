# Pantalla "Ajustes": la configuración que se define una vez y casi no se
# vuelve a tocar, separada del uso diario.
#
# Las reglas de descuento por antigüedad vivían en el header de Productos,
# al lado de "+ Agregar producto" -- pero agregar un producto es semanal y
# las reglas se tocan una vez cada varios meses. Dos cosas de frecuencia muy
# distinta compitiendo por la misma atención.
#
# Cada bloque muestra un RESUMEN en vivo de cómo está configurado hoy, para
# poder verificarlo de un vistazo sin abrir ningún diálogo -- que es lo que
# se hace la mayoría de las veces que uno entra acá.

import os

import customtkinter as ctk
from tkinter import messagebox

import database as db
from version import VERSION
from views import theme
from views.dialogos import centrar_sobre as _centrar_sobre


class AjustesFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Ajustes", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(self, text="Configuración que se define una vez y casi no se toca.",
                     text_color=theme.TEXT_SECONDARY,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(0, 14))

        # ── Descuento por antigüedad ──────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=8)
        card.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(card, text="Descuento por antigüedad", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(card,
                     text="A partir de cuántos días desde que se horneó, y qué % de descuento "
                          "se aplica al vender. No cambia el precio de lista del producto: el "
                          "descuento se calcula al momento de la venta, tanda por tanda.",
                     text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11),
                     wraplength=620, justify="left", anchor="w").pack(
            anchor="w", padx=16, pady=(0, 10))

        self._lbl_generales = ctk.CTkLabel(
            card, text="", text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12),
            wraplength=620, justify="left", anchor="w")
        self._lbl_generales.pack(anchor="w", padx=16, pady=(0, 2))

        self._lbl_propias = ctk.CTkLabel(
            card, text="", text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
            wraplength=620, justify="left", anchor="w")
        self._lbl_propias.pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkButton(card, text="Configurar reglas", width=170,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ACCENT_TEXT,
                      command=self._abrir_reglas).pack(anchor="w", padx=16, pady=(0, 16))

        self._card_programa()
        self.refresh()

    def _card_programa(self):
        """Versión instalada y dónde están los datos.

        Las dos cosas se muestran acá por el mismo motivo: la app corre en la
        panadería y quien la mantiene no está sentado ahí. La versión permite
        contestar por teléfono si la actualización quedó aplicada (un .exe
        viejo funciona igual de bien que uno nuevo, así que una actualización
        que no se instaló no da ninguna señal). La ruta permite contestar
        dónde está el historial de ventas para copiarlo a un USB -- y sobre
        todo, hace visible el caso en que los datos NO quedaron en la carpeta
        esperada (ver el plan B de `rutas.py`), que si no se vería desde el
        mostrador como "se borraron todas las ventas".
        """
        card = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=8)
        card.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(card, text="Programa y datos", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 2))

        ctk.CTkLabel(card, text=f"Fermento — versión {VERSION}",
                     text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12),
                     anchor="w").pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(card,
                     text="Las ventas, los respaldos y los tickets se guardan en esta carpeta. "
                          "Actualizar el programa no la toca. Conviene copiarla a un USB o a la "
                          "nube cada tanto: el respaldo automático protege contra un archivo "
                          "dañado, no contra que se rompa la computadora.",
                     text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11),
                     wraplength=620, justify="left", anchor="w").pack(
            anchor="w", padx=16, pady=(0, 6))

        ctk.CTkLabel(card, text=str(db.BASE_DIR), text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=12), wraplength=620, justify="left",
                     anchor="w").pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkButton(card, text="Abrir carpeta de datos", width=190,
                      fg_color=theme.NAV_INACTIVE, hover_color=theme.NAV_INACTIVE_HOVER,
                      text_color=theme.TEXT_PRIMARY,
                      command=self._abrir_carpeta_datos).pack(
            anchor="w", padx=16, pady=(0, 16))

    def _abrir_carpeta_datos(self):
        # `os.startfile` es solo de Windows, que es la única plataforma donde
        # se distribuye la app (mismo criterio que `views/ticket.py`, que lo
        # usa para abrir el PDF con el visor del sistema).
        try:
            os.startfile(db.BASE_DIR)
        except OSError as e:
            messagebox.showerror("No se pudo abrir la carpeta",
                                 f"{db.BASE_DIR}\n\n{e}", parent=self)

    def refresh(self):
        try:
            reglas = db.get_reglas_descuento()
            reglas_prod = db.get_reglas_descuento_producto()
            productos = db.get_productos(solo_activos=False)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        if reglas:
            escalones = "   ·   ".join(
                f"desde el día {r['dias']}: -{r['porcentaje']:.0f}%" for r in reglas)
            self._lbl_generales.configure(
                text=f"Reglas generales:   {escalones}", text_color=theme.TEXT_PRIMARY)
        else:
            self._lbl_generales.configure(
                text="Sin reglas generales: el pan se vende siempre a precio de lista, "
                     "sin importar de qué tanda sea.",
                text_color=theme.TEXT_DISABLED)

        # Un producto con reglas propias NO combina con las generales: las
        # reemplaza por completo (ver database.py::precio_vigente). Vale la
        # pena nombrarlos acá porque es la excepción fácil de olvidar.
        if reglas_prod:
            nombres = {p["id"]: p["nombre"] for p in productos}
            listado = ", ".join(sorted(nombres.get(pid, f"producto #{pid}")
                                       for pid in reglas_prod))
            self._lbl_propias.configure(
                text=f"Con reglas propias (reemplazan a las generales): {listado}")
        else:
            self._lbl_propias.configure(
                text="Ningún producto tiene reglas propias: todos usan las generales.")

    def _abrir_reglas(self):
        d = _DialogoReglas(self)
        self.wait_window(d)
        self.refresh()


# ── Dialogo reglas de descuento por antigüedad ────────────────────────────────

class _DialogoReglas(ctk.CTkToplevel):
    """Lista editable de reglas (día -> % de descuento), generales o de UN
    producto puntual según el selector "Aplicar a". A diferencia de los
    otros diálogos, no se cierra solo al guardar una regla -- se queda
    abierto para cargar varias de una sentada, y el usuario lo cierra con
    Escape o la X cuando termina.

    "General" = reglas_descuento (todos los productos que no tengan
    reglas propias). Elegir un producto edita reglas_descuento_producto
    para ESE producto -- si tiene alguna fila, reemplaza por completo a
    las generales para él (ver database.py::precio_vigente)."""

    _OPCION_GENERAL = "Todos los productos (general)"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Reglas de descuento por antigüedad")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self._producto_id = None
        self._build_ui()
        self.update_idletasks()
        _centrar_sobre(self, parent, 400, self.winfo_reqheight())
        self.bind("<Escape>", lambda e: self.destroy())
        self.e_dias.focus()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Reglas de descuento por antigüedad",
                     text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self,
                     text="A partir de cuántos días desde que se horneó, y qué % de "
                          "descuento se aplica solo al vender.",
                     text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11),
                     wraplength=350, justify="left").pack(anchor="w", padx=24, pady=(0, 10))

        try:
            self._productos = db.get_productos()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            self._productos = []

        ctk.CTkLabel(self, text="Aplicar a:", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24)
        opciones = [self._OPCION_GENERAL] + [p["nombre"] for p in self._productos]
        self._combo = ctk.CTkOptionMenu(
            self, values=opciones, width=350, fg_color=theme.BG_INPUT,
            button_color=theme.NEUTRAL, button_hover_color=theme.NEUTRAL_HOVER,
            text_color=theme.TEXT_PRIMARY, command=self._cambiar_producto)
        self._combo.set(self._OPCION_GENERAL)
        self._combo.pack(padx=24, pady=(2, 8))

        self._nota = ctk.CTkLabel(self, text="", text_color=theme.TEXT_DISABLED,
                                  font=ctk.CTkFont(size=11), wraplength=350, justify="left")
        self._nota.pack(padx=24, anchor="w")

        self.lista = ctk.CTkFrame(self, fg_color="transparent")
        self.lista.pack(fill="x", padx=24, pady=(6, 0))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=24, pady=(14, 6), fill="x")
        ctk.CTkLabel(form, text="Día:", text_color=theme.TEXT_PRIMARY).pack(side="left")
        self.e_dias = ctk.CTkEntry(form, width=60, fg_color=theme.BG_INPUT,
                                   text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_dias.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(form, text="Descuento %:", text_color=theme.TEXT_PRIMARY).pack(side="left")
        self.e_pct = ctk.CTkEntry(form, width=70, fg_color=theme.BG_INPUT,
                                  text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_pct.pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._guardar_regla())
        ctk.CTkButton(self, text="Agregar / actualizar regla", fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
                      command=self._guardar_regla).pack(pady=(4, 18))

        self._refresh_lista()

    def _cambiar_producto(self, seleccion):
        if seleccion == self._OPCION_GENERAL:
            self._producto_id = None
        else:
            prod = next(p for p in self._productos if p["nombre"] == seleccion)
            self._producto_id = prod["id"]
        self._refresh_lista()

    def _refresh_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        try:
            if self._producto_id is None:
                reglas = db.get_reglas_descuento()
                self._nota.configure(
                    text="Se aplican a todo producto que no tenga reglas propias cargadas.")
            else:
                reglas = db.get_reglas_de_producto(self._producto_id)
                self._nota.configure(
                    text=("Todavía sin reglas propias -- este producto usa las generales."
                          if not reglas else
                          "Reglas propias de este producto: reemplazan a las generales "
                          "solo para él."))
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        if not reglas:
            ctk.CTkLabel(self.lista, text="Todavía no hay reglas cargadas.",
                         text_color=theme.TEXT_DISABLED).pack(pady=6)
        for r in reglas:
            fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
            fila.pack(fill="x", pady=2)
            ctk.CTkLabel(fila, text=f"Desde el día {r['dias']}: -{r['porcentaje']:.0f}%",
                         text_color=theme.TEXT_PRIMARY, anchor="w").pack(
                side="left", padx=10, pady=6, fill="x", expand=True)
            ctk.CTkButton(fila, text="Borrar", width=64, fg_color=theme.DANGER,
                          hover_color=theme.DANGER_HOVER,
                          command=lambda dias=r["dias"]: self._borrar(dias)).pack(
                side="right", padx=6, pady=4)

    def _guardar_regla(self):
        try:
            dias = int(self.e_dias.get().strip())
            if dias < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El día debe ser un entero >= 0.", parent=self)
            return
        try:
            pct = float(self.e_pct.get().strip().replace(",", "."))
            if not (0 < pct <= 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El descuento debe ser un número entre 0 y 100.",
                                 parent=self)
            return
        try:
            if self._producto_id is None:
                db.set_regla_descuento(dias, pct)
            else:
                db.set_regla_descuento_producto(self._producto_id, dias, pct)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.e_dias.delete(0, "end")
        self.e_pct.delete(0, "end")
        self.e_dias.focus()
        self._refresh_lista()

    def _borrar(self, dias):
        try:
            if self._producto_id is None:
                db.eliminar_regla_descuento(dias)
            else:
                db.eliminar_regla_descuento_producto(self._producto_id, dias)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self._refresh_lista()
