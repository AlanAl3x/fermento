from datetime import datetime

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import database as db
from views import theme
from views.dialogos import centrar_sobre as _centrar_sobre

_BARRA_ANCHO = 130
_BARRA_ALTO = 14


def _fmt_stock(valor):
    """Sin decimales de más: 25 en vez de 25.0, pero conserva 12.5 tal cual."""
    return f"{valor:g}"


def _barra_stock(parent, actual, inicial, minimo, bajo):
    """Barrita del stock de UN insumo, dibujada dentro de su propia fila.

    Es una barra por fila y no un gráfico único a propósito: los insumos
    tienen magnitudes y unidades incomparables (145 kg de harina contra 3,2
    kg de levadura, más litros de leche). En un eje compartido la levadura
    sería una raya de dos píxeles -- justo el insumo que suele estar bajo el
    mínimo. **Cada barra se escala contra su propio máximo**, así todas se
    leen igual de bien.

    - relleno sólido = stock actual (naranja si está bajo el mínimo, igual
      criterio de color que el número y el aviso de stock bajo);
    - tramo tenue a continuación = con cuánto arrancó el día (`inicial`);
      None cuando ese insumo no se movió hoy, y ahí no se dibuja nada;
    - línea roja = el mínimo configurado (`stock_minimo`, 0 = sin umbral).

    Se usa `tk.Canvas` porque customtkinter no trae nada para dibujar
    formas; se le fija el `bg` de la fila a mano para que no aparezca un
    rectángulo gris claro sobre el modo oscuro (mismo cuidado que con el
    `tk.Menu` de Productos).
    """
    canvas = tk.Canvas(parent, width=_BARRA_ANCHO, height=_BARRA_ALTO,
                       bg=theme.BG_CARD, highlightthickness=0, bd=0)

    # Aire a la derecha (1.08) para que una línea de mínimo que coincida con
    # el tope no quede pegada al borde y se lea como si no estuviera.
    tope = max(actual, inicial or 0, minimo or 0) * 1.08
    if tope <= 0:
        return canvas  # insumo en 0 y sin mínimo: no hay nada que dibujar

    def x(valor):
        return max(0, min(_BARRA_ANCHO, valor / tope * _BARRA_ANCHO))

    canvas.create_rectangle(0, 0, _BARRA_ANCHO, _BARRA_ALTO, fill=theme.BG_INPUT, width=0)
    if inicial is not None:
        canvas.create_rectangle(0, 0, x(inicial), _BARRA_ALTO, fill=theme.NEUTRAL, width=0)
    canvas.create_rectangle(0, 0, x(actual), _BARRA_ALTO,
                            fill=theme.WARNING if bajo else theme.ACCENT, width=0)
    if inicial is not None and inicial < actual:
        # Repuesto: el stock subió, así que la sombra queda tapada por el
        # relleno. Se marca con una línea de dónde arrancó el día, para que
        # "se repuso" no se vea igual que "no se movió".
        canvas.create_line(x(inicial), 0, x(inicial), _BARRA_ALTO,
                           fill=theme.TEXT_DISABLED, width=2)
    if minimo and minimo > 0:
        canvas.create_line(x(minimo), 0, x(minimo), _BARRA_ALTO,
                           fill=theme.DANGER, width=2)
    return canvas


class InventarioFrame(ctk.CTkFrame):
    """Control manual de stock de insumos (harina, levadura, etc.), separado
    del catálogo de productos que se venden. No hay ningún descuento
    automático todavía -- el stock se ajusta a mano, igual que Productos
    antes de que existiera el carrito de Nueva Venta."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._orden_col = "nombre"
        self._orden_asc = True
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Inventario", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Agregar insumo",
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ACCENT_TEXT,
                      command=self._abrir_agregar).pack(side="right")

        busqueda = ctk.CTkFrame(self, fg_color="transparent")
        busqueda.pack(fill="x", padx=20, pady=(0, 10))
        self._filtro_var = ctk.StringVar()
        self._filtro_var.trace_add("write", lambda *a: self.refresh())
        ctk.CTkEntry(busqueda, textvariable=self._filtro_var,
                     placeholder_text="Buscar insumo por nombre...",
                     width=300, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                     border_color=theme.BORDER).pack(side="left")

        ctk.CTkLabel(self,
                     text="En «Hoy»: la barra llena es el stock actual, el tramo tenue es con "
                          "cuánto arrancaste el día, y la línea roja es el mínimo.",
                     text_color=theme.TEXT_DISABLED, font=ctk.CTkFont(size=11),
                     anchor="w").pack(anchor="w", padx=20, pady=(0, 8))

        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=6)
        enc.pack(fill="x", padx=20, pady=(0, 2))

        self._btn_col_nombre = ctk.CTkButton(
            enc, text="Nombre", anchor="w", fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("nombre"))
        self._btn_col_nombre.pack(side="left", expand=True, fill="x", padx=10, pady=6)

        ctk.CTkLabel(enc, text="Unidad", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=80, anchor="center").pack(
            side="left", padx=6, pady=6)

        self._btn_col_stock = ctk.CTkButton(
            enc, text="Stock", width=80, fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("stock"))
        self._btn_col_stock.pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(enc, text="Hoy", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=_BARRA_ANCHO, anchor="center").pack(
            side="left", padx=6, pady=6)

        ctk.CTkLabel(enc, text="Acciones", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=230, anchor="w").pack(
            side="left", padx=10, pady=6)

        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Aviso de stock bajo: se packea/despackea dinámicamente en
        # refresh() (side="bottom", empaquetado DESPUÉS de self.lista para
        # que Tkinter le reserve espacio abajo). Si no hay ningún insumo
        # por debajo de su mínimo, queda sin packear -- no se ve nada.
        self._alerta_frame = ctk.CTkFrame(self, fg_color=theme.WARNING, corner_radius=6)
        self._alerta_label = ctk.CTkLabel(
            self._alerta_frame, text="", text_color=theme.ACCENT_TEXT, anchor="w",
            justify="left", font=ctk.CTkFont(size=12, weight="bold"), wraplength=700)
        self._alerta_label.pack(fill="x", padx=14, pady=10)

        self.refresh()

    def refresh(self):
        for w in self.lista.winfo_children():
            w.destroy()

        try:
            insumos = db.get_insumos(solo_activos=False)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        self._actualizar_alerta_stock_bajo(insumos)

        filtro = self._filtro_var.get().strip().lower()
        if filtro:
            insumos = [i for i in insumos if filtro in i["nombre"].lower()]

        claves = {
            "nombre": lambda i: i["nombre"].lower(),
            "stock": lambda i: i["stock"],
        }
        insumos.sort(key=claves[self._orden_col], reverse=not self._orden_asc)

        flecha = " ▼" if self._orden_asc else " ▲"
        self._btn_col_nombre.configure(text="Nombre" + (flecha if self._orden_col == "nombre" else ""))
        self._btn_col_stock.configure(text="Stock" + (flecha if self._orden_col == "stock" else ""))

        if not insumos:
            texto = ("No hay insumos que coincidan con la búsqueda." if filtro
                     else "No hay insumos registrados.")
            ctk.CTkLabel(self.lista, text=texto, text_color=theme.TEXT_DISABLED).pack(pady=20)
            return

        for i in insumos:
            self._build_fila(i)

    def _actualizar_alerta_stock_bajo(self, insumos):
        """Insumo con "stock bajo" = activo, con un mínimo configurado
        (stock_minimo > 0 -- 0 significa que no se configuró alerta para
        ese insumo) y stock actual <= ese mínimo. Si no hay ninguno, se
        despackea el aviso entero (no queda ni una franja de color vacía)."""
        bajos = [i for i in insumos
                if i["activo"] and i["stock_minimo"] > 0 and i["stock"] <= i["stock_minimo"]]

        if not bajos:
            self._alerta_frame.pack_forget()
            return

        lineas = [f"• {i['nombre']}: {_fmt_stock(i['stock'])} {i['unidad']} "
                 f"(mínimo {_fmt_stock(i['stock_minimo'])} {i['unidad']})" for i in bajos]
        self._alerta_label.configure(
            text="⚠ Insumos con poco stock:\n" + "\n".join(lineas))
        self._alerta_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

    def _click_orden(self, col):
        if self._orden_col == col:
            self._orden_asc = not self._orden_asc
        else:
            self._orden_col = col
            self._orden_asc = True
        self.refresh()

    def _build_fila(self, i):
        fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
        fila.pack(fill="x", pady=2)

        nombre = i["nombre"] + ("  (inactivo)" if not i["activo"] else "")
        color_nombre = theme.TEXT_DISABLED if not i["activo"] else theme.TEXT_PRIMARY
        ctk.CTkLabel(fila, text=nombre, text_color=color_nombre,
                     anchor="w").pack(side="left", expand=True, fill="x", padx=10, pady=8)
        ctk.CTkLabel(fila, text=i["unidad"], text_color=theme.TEXT_SECONDARY,
                     width=80, anchor="center").pack(side="left", padx=4)
        stock_bajo = i["activo"] and i["stock_minimo"] > 0 and i["stock"] <= i["stock_minimo"]
        color_stock = theme.WARNING if stock_bajo else theme.TEXT_SECONDARY
        ctk.CTkLabel(fila, text=_fmt_stock(i["stock"]), text_color=color_stock,
                     width=80, anchor="center").pack(side="left", padx=4)

        # La sombra solo tiene sentido si la marca es de HOY: un insumo que
        # no se tocó en tres días mostraría el arranque de aquel día como si
        # fuera el de hoy. Sin movimiento de hoy, barra sólida y nada más.
        hoy = datetime.now().strftime("%Y-%m-%d")
        inicial = i["stock_inicial_dia"] if i.get("fecha_inicial") == hoy else None
        _barra_stock(fila, i["stock"], inicial, i["stock_minimo"], stock_bajo).pack(
            side="left", padx=6)

        if i["activo"]:
            ctk.CTkButton(fila, text="Editar", width=70,
                          fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                          text_color=theme.ACCENT_TEXT,
                          command=lambda i=i: self._abrir_editar(i)).pack(side="left", padx=4, pady=6)
            ctk.CTkButton(fila, text="Stock", width=70,
                          fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
                          command=lambda i=i: self._abrir_stock(i)).pack(side="left", padx=4)
            ctk.CTkButton(fila, text="Eliminar", width=80,
                          fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                          command=lambda i=i: self._desactivar(i)).pack(side="left", padx=4)
        else:
            ctk.CTkButton(fila, text="Reactivar", width=80,
                          fg_color=theme.WARNING, hover_color=theme.WARNING_HOVER,
                          command=lambda i=i: self._reactivar(i)).pack(side="left", padx=4, pady=6)

    def _abrir_agregar(self):
        d = _DialogoInsumo(self, "Agregar insumo")
        self.wait_window(d)
        self.refresh()

    def _abrir_editar(self, i):
        d = _DialogoInsumo(self, "Editar insumo", insumo=i)
        self.wait_window(d)
        self.refresh()

    def _abrir_stock(self, i):
        d = _DialogoStockInsumo(self, i)
        self.wait_window(d)
        self.refresh()

    def _desactivar(self, i):
        if messagebox.askyesno(
                "Confirmar",
                f"¿Desactivar '{i['nombre']}'?\n"
                "No aparecerá en la lista activa pero el historial se conserva.",
                parent=self):
            try:
                db.desactivar_insumo(i["id"])
            except db.DBError as e:
                messagebox.showerror("Error de base de datos", str(e), parent=self)
                return
            self.refresh()

    def _reactivar(self, i):
        try:
            db.reactivar_insumo(i["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.refresh()


# ── Dialogo agregar / editar ──────────────────────────────────────────────────

class _DialogoInsumo(ctk.CTkToplevel):
    def __init__(self, parent, titulo, insumo=None):
        super().__init__(parent)
        self.title(titulo)
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.insumo = insumo
        self._build_ui()
        # Alto calculado según el contenido: "Agregar" tiene un campo más
        # (Stock inicial) que "Editar" -- mismo criterio que _DialogoProducto.
        self.update_idletasks()
        _centrar_sobre(self, parent, 360, self.winfo_reqheight())
        self.bind("<Return>", lambda e: self._guardar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.e_nombre.focus()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Nombre:", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24, pady=(20, 2))
        self.e_nombre = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_nombre.pack(padx=24)

        ctk.CTkLabel(self, text="Unidad (kg, L, unidades...):", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24, pady=(12, 2))
        self.e_unidad = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_unidad.pack(padx=24)

        if not self.insumo:
            ctk.CTkLabel(self, text="Stock inicial:", text_color=theme.TEXT_PRIMARY).pack(
                anchor="w", padx=24, pady=(12, 2))
            self.e_stock = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                        text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
            self.e_stock.pack(padx=24)
            self.e_stock.insert(0, "0")

        ctk.CTkLabel(self, text="Stock mínimo (alerta, opcional):", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24, pady=(12, 2))
        self.e_stock_minimo = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                          text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_stock_minimo.pack(padx=24)
        self.e_stock_minimo.insert(0, "0")

        if self.insumo:
            self.e_nombre.insert(0, self.insumo["nombre"])
            self.e_unidad.insert(0, self.insumo["unidad"])
            self.e_stock_minimo.delete(0, "end")
            self.e_stock_minimo.insert(0, _fmt_stock(self.insumo["stock_minimo"]))

        ctk.CTkButton(self, text="Guardar", fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
                      command=self._guardar).pack(pady=18)

    def _guardar(self):
        nombre = self.e_nombre.get().strip()
        if not nombre:
            messagebox.showerror("Error", "El nombre no puede estar vacío.", parent=self)
            return
        unidad = self.e_unidad.get().strip()
        if not unidad:
            messagebox.showerror("Error", "La unidad no puede estar vacía.", parent=self)
            return

        try:
            # Acepta coma decimal ("12,5") además de punto ("12.5"). Vacío
            # equivale a "0" -- sin umbral de alerta configurado.
            texto_minimo = self.e_stock_minimo.get().strip().replace(",", ".")
            stock_minimo = float(texto_minimo) if texto_minimo else 0.0
            if stock_minimo < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Error", "El stock mínimo debe ser un número >= 0 (o vacío para no alertar).",
                parent=self)
            return

        try:
            if self.insumo:
                db.update_insumo(self.insumo["id"], nombre, unidad, stock_minimo)
            else:
                try:
                    stock = float(self.e_stock.get().strip().replace(",", "."))
                    if stock < 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "El stock debe ser un número >= 0.", parent=self)
                    return
                db.add_insumo(nombre, unidad, stock, stock_minimo)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        self.destroy()


# ── Dialogo ajuste de stock ───────────────────────────────────────────────────

class _DialogoStockInsumo(ctk.CTkToplevel):
    def __init__(self, parent, insumo):
        super().__init__(parent)
        self.title(f"Ajustar stock — {insumo['nombre']}")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.insumo = insumo
        self._build_ui()
        self.update_idletasks()
        _centrar_sobre(self, parent, 300, self.winfo_reqheight())
        self.bind("<Return>", lambda e: self._guardar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.e.focus()

    def _build_ui(self):
        ctk.CTkLabel(self, text=f"Stock actual: {_fmt_stock(self.insumo['stock'])} {self.insumo['unidad']}",
                     text_color=theme.TEXT_PRIMARY).pack(pady=(20, 6))
        ctk.CTkLabel(self, text="Nuevo stock:", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24)
        self.e = ctk.CTkEntry(self, width=252, fg_color=theme.BG_INPUT,
                              text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e.pack(padx=24)
        self.e.insert(0, _fmt_stock(self.insumo["stock"]))
        ctk.CTkButton(self, text="Actualizar", fg_color=theme.SUCCESS,
                      hover_color=theme.SUCCESS_HOVER,
                      command=self._guardar).pack(pady=16)

    def _guardar(self):
        try:
            nuevo = float(self.e.get().strip().replace(",", "."))
            if nuevo < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El stock debe ser un número >= 0.", parent=self)
            return
        try:
            db.ajustar_stock_insumo(self.insumo["id"], nuevo)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.destroy()
