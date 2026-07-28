from datetime import date

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import database as db
from views import formato, theme
from views.dialogos import centrar_sobre as _centrar_sobre


class ProductosFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        # Columna por la que se ordena y dirección. Arranca en "nombre"
        # ascendente (A-Z), el orden que tenía la lista antes de que esto
        # fuera clickeable.
        self._orden_col = "nombre"
        self._orden_asc = True
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Productos", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Agregar producto",
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ACCENT_TEXT,
                      command=self._abrir_agregar).pack(side="right")
        # "Reglas de descuento" se fue a la sección Ajustes: se configura una
        # vez cada varios meses y acá competía por la atención con "+ Agregar
        # producto", que se usa muchísimo más seguido.

        # Búsqueda: filtra la lista en vivo por nombre (sin distinguir
        # mayúsculas/minúsculas) a medida que se escribe, sin ir a la BD --
        # el catálogo de una panadería es chico, no hace falta una consulta
        # nueva por cada letra tipeada.
        busqueda = ctk.CTkFrame(self, fg_color="transparent")
        busqueda.pack(fill="x", padx=20, pady=(0, 10))
        self._filtro_var = ctk.StringVar()
        self._filtro_var.trace_add("write", lambda *a: self.refresh())
        ctk.CTkEntry(busqueda, textvariable=self._filtro_var,
                     placeholder_text="Buscar producto por nombre...",
                     width=300, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                     border_color=theme.BORDER).pack(side="left")

        # Encabezado de columnas: "Nombre", "Precio" y "Stock" son
        # clickeables para ordenar -- un clic en una columna nueva ordena
        # ascendente con flecha "▼"; un clic de nuevo sobre la misma
        # columna invierte el orden y pasa la flecha a "▲". Solo la
        # columna activa muestra flecha.
        enc = ctk.CTkFrame(self, fg_color=theme.BG_CARD_HEADER, corner_radius=6)
        enc.pack(fill="x", padx=20, pady=(0, 2))

        self._btn_col_nombre = ctk.CTkButton(
            enc, text="Nombre", anchor="w", fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("nombre"))
        self._btn_col_nombre.pack(side="left", expand=True, fill="x", padx=10, pady=6)

        self._btn_col_precio = ctk.CTkButton(
            enc, text="Precio", width=90, fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("precio"))
        self._btn_col_precio.pack(side="left", padx=6, pady=6)

        self._btn_col_margen = ctk.CTkButton(
            enc, text="Margen", width=110, fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("margen"))
        self._btn_col_margen.pack(side="left", padx=6, pady=6)

        self._btn_col_stock = ctk.CTkButton(
            enc, text="Stock", width=70, fg_color="transparent",
            hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(weight="bold"), command=lambda: self._click_orden("stock"))
        self._btn_col_stock.pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(enc, text="Acciones", font=ctk.CTkFont(weight="bold"),
                     text_color=theme.TEXT_SECONDARY, width=150, anchor="w").pack(
            side="left", padx=10, pady=6)

        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Aviso de productos con descuento por antigüedad activo hoy --
        # mismo patrón que el aviso de stock bajo en Inventario: se arma
        # acá pero no se packea hasta refresh(), y si no hay nada que
        # avisar queda sin packear (no se ve ni una franja vacía).
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
            productos = db.get_productos(solo_activos=False)
            reglas = db.get_reglas_descuento()
            reglas_prod = db.get_reglas_descuento_producto()
            lotes_todos = db.get_lotes_todos()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        self._actualizar_alerta_descuento(productos, reglas, reglas_prod, lotes_todos)

        filtro = self._filtro_var.get().strip().lower()
        if filtro:
            productos = [p for p in productos if filtro in p["nombre"].lower()]

        claves = {
            "nombre": lambda p: p["nombre"].lower(),
            "precio": lambda p: p["precio"],
            # Sin costo cargado (0) = margen desconocido, no "100% de margen".
            # Se ordena como el valor más bajo posible para no mezclarse
            # con productos que sí tienen margen calculado.
            "margen": lambda p: (p["precio"] - p["costo"]) if p["costo"] > 0 else float("-inf"),
            "stock": lambda p: p["stock"],
        }
        productos.sort(key=claves[self._orden_col], reverse=not self._orden_asc)

        flecha = " ▼" if self._orden_asc else " ▲"
        self._btn_col_nombre.configure(text="Nombre" + (flecha if self._orden_col == "nombre" else ""))
        self._btn_col_precio.configure(text="Precio" + (flecha if self._orden_col == "precio" else ""))
        self._btn_col_margen.configure(text="Margen" + (flecha if self._orden_col == "margen" else ""))
        self._btn_col_stock.configure(text="Stock" + (flecha if self._orden_col == "stock" else ""))

        if not productos:
            texto = ("No hay productos que coincidan con la búsqueda." if filtro
                     else "No hay productos registrados.")
            ctk.CTkLabel(self.lista, text=texto, text_color=theme.TEXT_DISABLED).pack(pady=20)
            return

        for p in productos:
            self._build_fila(p, reglas, reglas_prod, lotes_todos)

    def _click_orden(self, col):
        if self._orden_col == col:
            self._orden_asc = not self._orden_asc
        else:
            self._orden_col = col
            self._orden_asc = True
        self.refresh()

    def _actualizar_alerta_descuento(self, productos, reglas, reglas_prod, lotes_todos):
        """Lotes con descuento por antigüedad activo hoy, de productos
        activos. Si no hay ninguno, se despackea el aviso entero (no queda
        ni una franja de color vacía) -- mismo criterio que el aviso de
        stock bajo."""
        con_descuento = []
        for p in productos:
            if not p["activo"]:
                continue
            for lote in lotes_todos.get(p["id"], []):
                _, dias, pct = db.precio_vigente(
                    {"id": p["id"], "precio": p["precio"], "fecha_horneado": lote["fecha_horneado"]},
                    reglas, reglas_prod)
                if pct:
                    con_descuento.append((p, lote, dias, pct))

        if not con_descuento:
            self._alerta_frame.pack_forget()
            return

        lineas = [f"• {p['nombre']} ({lote['stock']} u., {formato.edad_tanda(dias).lower()}): -{pct:.0f}%"
                 for p, lote, dias, pct in con_descuento]
        self._alerta_label.configure(
            text="⚠ Tandas con descuento por antigüedad activo hoy:\n" + "\n".join(lineas))
        self._alerta_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

    def _build_fila(self, p, reglas, reglas_prod, lotes_todos):
        fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
        fila.pack(fill="x", pady=2)

        lotes = lotes_todos.get(p["id"], [])

        info_nombre = ctk.CTkFrame(fila, fg_color="transparent")
        info_nombre.pack(side="left", expand=True, fill="x", padx=10, pady=8)
        nombre = p["nombre"] + ("  (inactivo)" if not p["activo"] else "")
        color_nombre = theme.TEXT_DISABLED if not p["activo"] else theme.TEXT_PRIMARY
        ctk.CTkLabel(info_nombre, text=nombre, text_color=color_nombre,
                     anchor="w").pack(anchor="w")

        # Un producto puede tener pan de más de una tanda al mismo
        # tiempo (pan de hoy Y pan de hace 3 días sin vender) -- cada lote
        # se muestra en su propia línea con su propio precio, en vez de
        # una sola antigüedad/precio por producto.
        if not lotes:
            ctk.CTkLabel(info_nombre, text="Sin stock", text_color=theme.TEXT_DISABLED,
                         font=ctk.CTkFont(size=10), anchor="w").pack(anchor="w")
        for lote in lotes:
            precio_l, dias_l, pct_l = db.precio_vigente(
                {"id": p["id"], "precio": p["precio"], "fecha_horneado": lote["fecha_horneado"]},
                reglas, reglas_prod)
            edad_l = formato.edad_tanda(dias_l) or "sin fecha"
            if pct_l:
                texto_l = (f"{lote['stock']} u. · {edad_l} · "
                          f"${precio_l:.2f} (-{pct_l:.0f}%)")
                color_l = theme.WARNING
            else:
                texto_l = f"{lote['stock']} u. · {edad_l} · ${p['precio']:.2f}"
                color_l = theme.TEXT_DISABLED
            ctk.CTkLabel(info_nombre, text=texto_l, text_color=color_l,
                         font=ctk.CTkFont(size=10), anchor="w").pack(anchor="w")

        ctk.CTkLabel(fila, text=f"${p['precio']:.2f}", text_color=theme.TEXT_SECONDARY,
                     width=90, anchor="center").pack(side="left", padx=4)

        if p["costo"] > 0:
            margen_abs = p["precio"] - p["costo"]
            margen_pct = (margen_abs / p["precio"] * 100) if p["precio"] > 0 else 0
            texto_margen = f"${margen_abs:.2f} ({margen_pct:.0f}%)"
            color_margen = theme.SUCCESS if margen_abs > 0 else theme.DANGER
        else:
            texto_margen = "—"
            color_margen = theme.TEXT_DISABLED
        ctk.CTkLabel(fila, text=texto_margen, text_color=color_margen,
                     width=110, anchor="center").pack(side="left", padx=4)

        ctk.CTkLabel(fila, text=str(p["stock"]), text_color=theme.TEXT_SECONDARY,
                     width=70, anchor="center").pack(side="left", padx=4)

        if p["activo"]:
            # Una sola acción visible por fila. Registrar la tanda del día
            # es lo único que se hace a diario; editar el precio o dar de
            # baja un producto es esporádico y se va al menú "⋯". Con 15
            # productos, tres botones por fila eran 45 botones compitiendo
            # por la atención para cubrir un uso que el 90% de las veces es
            # el mismo. El botón dice "+ Tanda" (no "Lotes"): nombra la
            # acción concreta con la palabra que usa el panadero.
            ctk.CTkButton(fila, text="+ Tanda", width=100,
                          fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
                          command=lambda p=p: self._abrir_stock(p)).pack(
                side="left", padx=(4, 2), pady=6)
            btn_mas = ctk.CTkButton(fila, text="⋯", width=34,
                                    fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                                    text_color=theme.TEXT_PRIMARY)
            btn_mas.configure(command=lambda p=p, b=btn_mas: self._menu_acciones(p, b))
            btn_mas.pack(side="left", padx=(2, 8), pady=6)
        else:
            ctk.CTkButton(fila, text="Reactivar", width=100,
                          fg_color=theme.WARNING, hover_color=theme.WARNING_HOVER,
                          command=lambda p=p: self._reactivar(p)).pack(
                side="left", padx=(4, 8), pady=6)

    def _menu_acciones(self, p, boton):
        """Menú "⋯" con las acciones ocasionales de un producto.

        Usa `tk.Menu` nativo porque CustomTkinter no trae menú contextual;
        va estilado a mano (bg/fg/active*) para que no aparezca el bloque
        gris claro de Windows encima del modo oscuro de la app.
        """
        menu = tk.Menu(self, tearoff=0,
                       bg=theme.BG_CARD_HEADER, fg=theme.TEXT_PRIMARY,
                       activebackground=theme.ACCENT, activeforeground=theme.ACCENT_TEXT,
                       activeborderwidth=0, bd=0, relief="flat")
        menu.add_command(label="  Editar producto…",
                         command=lambda: self._abrir_editar(p))
        menu.add_separator()
        menu.add_command(label="  Eliminar producto",
                         command=lambda: self._desactivar(p))
        # Se despliega pegado al borde inferior izquierdo del "⋯", como
        # cualquier menú desplegable, en vez de aparecer bajo el mouse.
        try:
            menu.tk_popup(boton.winfo_rootx(),
                          boton.winfo_rooty() + boton.winfo_height())
        finally:
            menu.grab_release()

    def _abrir_agregar(self):
        d = _DialogoProducto(self, "Agregar producto")
        self.wait_window(d)
        self.refresh()

    def _abrir_editar(self, p):
        d = _DialogoProducto(self, "Editar producto", producto=p)
        self.wait_window(d)
        self.refresh()

    def _abrir_stock(self, p):
        d = _DialogoLotes(self, p)
        self.wait_window(d)
        self.refresh()

    def _desactivar(self, p):
        if messagebox.askyesno(
                "Confirmar",
                f"¿Desactivar '{p['nombre']}'?\n"
                "No aparecerá en ventas nuevas pero el historial se conserva.",
                parent=self):
            try:
                db.desactivar_producto(p["id"])
            except db.DBError as e:
                messagebox.showerror("Error de base de datos", str(e), parent=self)
                return
            self.refresh()

    def _reactivar(self, p):
        try:
            db.reactivar_producto(p["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.refresh()


# ── Dialogo agregar / editar ──────────────────────────────────────────────────

class _DialogoProducto(ctk.CTkToplevel):
    def __init__(self, parent, titulo, producto=None):
        super().__init__(parent)
        self.title(titulo)
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.producto = producto
        self._build_ui()
        # Alto calculado según el contenido: "Agregar" tiene un campo más
        # (Stock inicial) que "Editar", así que una altura fija se queda
        # corta en uno de los dos casos y esconde el botón "Guardar".
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

        ctk.CTkLabel(self, text="Precio ($):", text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=24, pady=(12, 2))
        self.e_precio = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_precio.pack(padx=24)

        ctk.CTkLabel(self, text="Costo interno ($, opcional -- para calcular margen):",
                     text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=24, pady=(12, 2))
        self.e_costo = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                    text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_costo.pack(padx=24)
        self.e_costo.insert(0, "0")

        if not self.producto:
            ctk.CTkLabel(self, text="Stock inicial:", text_color=theme.TEXT_PRIMARY).pack(
                anchor="w", padx=24, pady=(12, 2))
            self.e_stock = ctk.CTkEntry(self, width=312, fg_color=theme.BG_INPUT,
                                        text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
            self.e_stock.pack(padx=24)
            self.e_stock.insert(0, "0")

        if self.producto:
            self.e_nombre.insert(0, self.producto["nombre"])
            self.e_precio.insert(0, f"{self.producto['precio']:.2f}")
            self.e_costo.delete(0, "end")
            self.e_costo.insert(0, f"{self.producto['costo']:.2f}")

        ctk.CTkButton(self, text="Guardar", fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
                      command=self._guardar).pack(pady=18)

    def _guardar(self):
        nombre = self.e_nombre.get().strip()
        if not nombre:
            messagebox.showerror("Error", "El nombre no puede estar vacío.", parent=self)
            return
        try:
            # Acepta coma decimal ("12,50") además de punto ("12.50").
            precio = float(self.e_precio.get().strip().replace(",", "."))
            if precio <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El precio debe ser un número mayor a 0.", parent=self)
            return

        try:
            # A diferencia del precio, el costo puede ser 0 (todavía no
            # cargado) -- no es obligatorio para poder seguir vendiendo.
            texto_costo = self.e_costo.get().strip().replace(",", ".")
            costo = float(texto_costo) if texto_costo else 0.0
            if costo < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El costo interno debe ser un número >= 0 (o vacío).",
                                 parent=self)
            return

        try:
            if self.producto:
                db.update_producto(self.producto["id"], nombre, precio, costo)
            else:
                try:
                    stock = int(self.e_stock.get().strip())
                    if stock < 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "El stock debe ser un entero >= 0.", parent=self)
                    return
                db.add_producto(nombre, precio, stock, costo)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        self.destroy()


# ── Dialogo de tandas (tabla `lotes`) de un producto ────────────────────────

class _DialogoLotes(ctk.CTkToplevel):
    """Gestión de las tandas de UN producto: corregir la cantidad de una
    existente, darla de baja, o registrar una nueva.

    OJO con el vocabulario: en pantalla se dice siempre "tanda" (la
    palabra del panadero), pero el modelo de datos sigue diciendo "lote"
    (tabla `lotes`, `lote_id`, `db.agregar_lote()`...). La frontera es a
    propósito -- renombrar la BD obligaría a una migración por un cambio
    puramente cosmético. Al tocar acá: texto visible en tandas,
    identificadores en lotes. No se cierra solo al guardar -- se queda abierto para varias
    acciones seguidas, mismo patrón que el diálogo de reglas de descuento
    (views/ajustes.py)."""

    def __init__(self, parent, producto):
        super().__init__(parent)
        self.title(f"Tandas — {producto['nombre']}")
        self.configure(fg_color=theme.BG_APP)
        self.resizable(False, False)
        self.grab_set()
        self.producto = producto
        self._build_ui()
        self.update_idletasks()
        _centrar_sobre(self, parent, 400, self.winfo_reqheight())
        self.bind("<Escape>", lambda e: self.destroy())

    def _build_ui(self):
        ctk.CTkLabel(self, text=f"Tandas de \"{self.producto['nombre']}\"",
                     text_color=theme.TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self,
                     text="Cada tanda se lleva su propia antigüedad y su propio precio -- "
                          "podés corregir la cantidad de una puntual (si se rompió algo) "
                          "o darla de baja del todo.",
                     text_color=theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11),
                     wraplength=350, justify="left").pack(anchor="w", padx=24, pady=(0, 10))

        self.lista = ctk.CTkFrame(self, fg_color="transparent")
        self.lista.pack(fill="x", padx=24)

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=24, pady=(14, 6), fill="x")
        ctk.CTkLabel(form, text="Tanda nueva -- unidades:",
                     text_color=theme.TEXT_PRIMARY).pack(side="left")
        self.e_nuevas = ctk.CTkEntry(form, width=80, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.e_nuevas.pack(side="left", padx=(8, 0))

        self.bind("<Return>", lambda e: self._agregar_lote())
        ctk.CTkButton(self, text="Registrar tanda nueva", fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
                      command=self._agregar_lote).pack(pady=(4, 18))

        self.e_nuevas.focus()
        self._refresh_lista()

    def _refresh_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        try:
            lotes = db.get_lotes(self.producto["id"])
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        if not lotes:
            ctk.CTkLabel(self.lista, text="Sin stock cargado.",
                         text_color=theme.TEXT_DISABLED).pack(pady=6)
        for lote in lotes:
            dias = (date.today() - date.fromisoformat(lote["fecha_horneado"])).days
            fila = ctk.CTkFrame(self.lista, fg_color=theme.BG_CARD, corner_radius=6)
            fila.pack(fill="x", pady=2)
            ctk.CTkLabel(
                fila, text=f"{formato.fecha(lote['fecha_horneado'])} ({formato.edad_tanda(dias).lower()})",
                text_color=theme.TEXT_PRIMARY, anchor="w").pack(
                side="left", padx=10, pady=6, fill="x", expand=True)
            e_cant = ctk.CTkEntry(fila, width=55, fg_color=theme.BG_INPUT,
                                  text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
            e_cant.insert(0, str(lote["stock"]))
            e_cant.pack(side="left", padx=4)
            ctk.CTkButton(fila, text="Guardar", width=64, fg_color=theme.SUCCESS,
                          hover_color=theme.SUCCESS_HOVER,
                          command=lambda lid=lote["id"], e=e_cant: self._corregir(lid, e)).pack(
                side="left", padx=4, pady=6)
            ctk.CTkButton(fila, text="Borrar", width=60, fg_color=theme.DANGER,
                          hover_color=theme.DANGER_HOVER,
                          command=lambda lid=lote["id"]: self._eliminar(lid)).pack(
                side="left", padx=(4, 8))

    def _corregir(self, lote_id, entry):
        try:
            nuevo = int(entry.get().strip())
            if nuevo < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "La cantidad debe ser un entero >= 0.", parent=self)
            return
        try:
            db.corregir_stock_lote(lote_id, nuevo)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self._refresh_lista()

    def _eliminar(self, lote_id):
        if not messagebox.askyesno("Confirmar", "¿Dar de baja esta tanda entera?", parent=self):
            return
        try:
            db.eliminar_lote(lote_id)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self._refresh_lista()

    def _agregar_lote(self):
        try:
            unidades = int(self.e_nuevas.get().strip())
            if unidades <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Las unidades deben ser un entero > 0.", parent=self)
            return
        try:
            db.agregar_lote(self.producto["id"], unidades)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self.e_nuevas.delete(0, "end")
        self.e_nuevas.focus()
        self._refresh_lista()
