import customtkinter as ctk
from tkinter import messagebox
import database as db
from views import formato, theme, ticket


class NuevaVentaFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        # lote_id -> {producto_id, nombre, precio, cantidad, stock, descuento_pct}
        # Se indexa por lote (tanda), no por producto -- el mismo
        # producto puede tener dos líneas de carrito distintas si hay pan
        # viejo Y nuevo, cada una con su propio precio.
        self.carrito: dict = {}
        # Reglas de descuento por antigüedad vigentes (generales + por
        # producto), refrescadas en cada refresh().
        self._reglas: list = []
        self._reglas_prod: dict = {}
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Nueva Venta", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 10))

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        contenido.columnconfigure(0, weight=2)
        contenido.columnconfigure(1, weight=3)
        contenido.rowconfigure(0, weight=1)

        # ── Columna izquierda: catálogo ───────────────────────────────────────
        izq = ctk.CTkFrame(contenido, fg_color=theme.BG_CARD_HEADER)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        izq.rowconfigure(2, weight=1)
        izq.columnconfigure(0, weight=1)

        ctk.CTkLabel(izq, text="Productos disponibles", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, pady=(10, 4), padx=10)

        # Buscador en vivo, mismo patrón que Productos (filtra la lista ya
        # traída, sin ir a la BD por cada letra). Acá hace más falta que allá:
        # el catálogo se edita una vez por semana y se vende decenas de veces
        # por día, con gente esperando.
        self._filtro_var = ctk.StringVar()
        self._filtro_var.trace_add("write", lambda *a: self.refresh())
        ctk.CTkEntry(izq, textvariable=self._filtro_var,
                     placeholder_text="Buscar por nombre o N°...",
                     fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                     border_color=theme.BORDER).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 6))

        self.panel_productos = ctk.CTkScrollableFrame(izq, fg_color="transparent")
        self.panel_productos.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 8))

        # ── Columna derecha: carrito ──────────────────────────────────────────
        der = ctk.CTkFrame(contenido, fg_color=theme.BG_CARD_HEADER)
        der.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        der.rowconfigure(1, weight=1)
        der.columnconfigure(0, weight=1)

        ctk.CTkLabel(der, text="Carrito", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, pady=(10, 4))

        self.panel_carrito = ctk.CTkScrollableFrame(der, fg_color="transparent")
        self.panel_carrito.grid(row=1, column=0, sticky="nsew", padx=6)

        # ── Aviso post-venta ──────────────────────────────────────────────────
        # Reemplaza al messagebox "Venta registrada / ¿generar ticket?".
        # Vender es la acción más repetida del día: un modal por venta obliga
        # a soltar el mouse y confirmar mientras hay gente esperando. Acá el
        # aviso aparece en la misma pantalla, con el ticket a un click, y se
        # va solo -- no bloquea empezar a cargar la venta siguiente.
        self._aviso_job = None
        self._aviso = ctk.CTkFrame(der, fg_color=theme.SUCCESS, corner_radius=6)
        self._aviso.columnconfigure(0, weight=1)
        self._aviso_lbl = ctk.CTkLabel(self._aviso, text="", anchor="w",
                                       text_color=theme.TEXT_PRIMARY,
                                       font=ctk.CTkFont(weight="bold"))
        self._aviso_lbl.grid(row=0, column=0, sticky="w", padx=(10, 6), pady=7)
        self._aviso_btn = ctk.CTkButton(
            self._aviso, text="Ticket", width=80,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.ACCENT_TEXT)
        self._aviso_btn.grid(row=0, column=1, pady=7)
        ctk.CTkButton(self._aviso, text="✕", width=28,
                      fg_color="transparent", hover_color=theme.SUCCESS_HOVER,
                      text_color=theme.TEXT_PRIMARY,
                      command=self._ocultar_aviso).grid(row=0, column=2, padx=(4, 6), pady=7)
        self._aviso.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 0))
        self._aviso.grid_remove()

        # Pie: total + con cuánto paga + botones
        pie = ctk.CTkFrame(der, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", padx=10, pady=10)

        fila_total = ctk.CTkFrame(pie, fg_color="transparent")
        fila_total.pack(fill="x")

        self.lbl_total = ctk.CTkLabel(fila_total, text="Total: $0.00",
                                      text_color=theme.TEXT_PRIMARY,
                                      font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_total.pack(side="left")

        # "Paga con" es OPCIONAL: si queda vacío la venta se registra igual
        # y el ticket sale sin las líneas de pago y cambio. Es el mismo
        # criterio que el resto del flujo de venta -- nada que se pueda
        # saltear debe frenar la acción más repetida del día. El cambio se
        # calcula mientras se tipea y NO al confirmar: el vendedor lo
        # necesita con el billete en la mano, antes de darle a Confirmar.
        self._pago_var = ctk.StringVar()
        self._pago_var.trace_add("write", lambda *a: self._actualizar_cambio())
        # Ancho fijo aunque esté vacío: el label se packea a la derecha del
        # campo, así que si creciera con el texto correría el campo hacia la
        # izquierda justo mientras se está tipeando adentro. Reservar el
        # lugar desde el arranque deja la fila quieta.
        self.lbl_cambio = ctk.CTkLabel(fila_total, text="", anchor="e", width=160,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_cambio.pack(side="right", padx=(10, 0))
        ctk.CTkEntry(fila_total, textvariable=self._pago_var, width=90,
                     justify="right", placeholder_text="opcional",
                     fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                     border_color=theme.BORDER).pack(side="right", padx=(6, 0))
        ctk.CTkLabel(fila_total, text="Paga con:", text_color=theme.TEXT_SECONDARY,
                     font=ctk.CTkFont(size=12)).pack(side="right", padx=(12, 0))

        fila_botones = ctk.CTkFrame(pie, fg_color="transparent")
        fila_botones.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(fila_botones, text="Confirmar venta",
                      fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
                      command=self._confirmar).pack(side="right")
        ctk.CTkButton(fila_botones, text="Limpiar",
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self._limpiar).pack(side="right", padx=8)

    # ── Refresco del catálogo ─────────────────────────────────────────────────

    def refresh(self):
        for w in self.panel_productos.winfo_children():
            w.destroy()

        try:
            productos = db.get_productos()
            reglas = db.get_reglas_descuento()
            reglas_prod = db.get_reglas_descuento_producto()
            lotes_todos = db.get_lotes_todos()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        self._reglas = reglas
        self._reglas_prod = reglas_prod
        if not productos:
            ctk.CTkLabel(self.panel_productos,
                         text="No hay productos activos.\nAgrega uno en la sección Productos.",
                         text_color=theme.TEXT_DISABLED, justify="center").pack(pady=20)
            return

        filtro = self._filtro_var.get().strip().lower()
        if filtro:
            # Mismo criterio que la lista de Productos (nombre por contenido,
            # N° de item por principio), compartido a propósito en
            # `formato.coincide_busqueda()`: acá se busca con gente esperando
            # y lo último que puede pasar es que el número que se usa todos
            # los días filtre distinto según la pantalla.
            productos = [p for p in productos
                         if formato.coincide_busqueda(p, filtro)]
        if not productos:
            ctk.CTkLabel(self.panel_productos,
                         text="No hay productos que coincidan con la búsqueda.",
                         text_color=theme.TEXT_DISABLED, justify="center").pack(pady=20)
            return

        # Los agotados van al fondo, agrupados: a media tarde, con media
        # panadería vendida, sus tarjetas quedaban *entre* el vendedor y lo
        # que sí se puede vender. No se ocultan del todo porque saber qué se
        # terminó sigue sirviendo en el mostrador (para avisarle al cliente).
        con_stock = [p for p in productos if lotes_todos.get(p["id"])]
        agotados = [p for p in productos if not lotes_todos.get(p["id"])]

        for p in con_stock:
            self._tarjeta_producto(p, lotes_todos[p["id"]], reglas, reglas_prod)

        if agotados:
            ctk.CTkLabel(self.panel_productos, text="AGOTADOS",
                         text_color=theme.TEXT_DISABLED, anchor="w",
                         font=ctk.CTkFont(size=10, weight="bold")).pack(
                anchor="w", padx=10, pady=(12, 2))
            for p in agotados:
                self._tarjeta_producto(p, [], reglas, reglas_prod)

    def _tarjeta_producto(self, p, lotes, reglas, reglas_prod):
        card = ctk.CTkFrame(self.panel_productos, fg_color=theme.BG_CARD, corner_radius=6)
        card.pack(fill="x", pady=2)
        # El N° de item va delante del nombre y en chico: no es lo que se
        # lee de un vistazo (eso sigue siendo el nombre), pero es lo que
        # confirma que el número tipeado en el buscador cayó donde se
        # quería antes de apretar "+ Agregar". Si falta (base sin migrar),
        # no se dibuja nada -- un guion ahí sería ruido en cada tarjeta.
        encabezado = ctk.CTkFrame(card, fg_color="transparent")
        encabezado.pack(fill="x", padx=10, pady=(8, 2))
        if p["codigo"] is not None:
            ctk.CTkLabel(encabezado, text=str(p["codigo"]),
                         text_color=theme.TEXT_SECONDARY if lotes else theme.TEXT_DISABLED,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(encabezado, text=p["nombre"], anchor="w",
                     text_color=theme.TEXT_PRIMARY if lotes else theme.TEXT_DISABLED,
                     font=ctk.CTkFont(weight="bold")).pack(side="left")

        if not lotes:
            ctk.CTkLabel(card, text="Sin stock", text_color=theme.TEXT_DISABLED,
                         anchor="w", font=ctk.CTkFont(size=11)).pack(
                anchor="w", padx=10, pady=(0, 8))
            return

        # Un producto puede tener pan de más de una tanda al mismo
        # tiempo (pan de hoy Y pan de hace 3 días sin vender) -- un
        # "+ Agregar" por lote, cada uno con su propio precio según SU
        # antigüedad, en vez de un único precio por producto.
        for lote in lotes:
            precio_l, dias_l, pct_l = db.precio_vigente(
                {"id": p["id"], "precio": p["precio"], "fecha_horneado": lote["fecha_horneado"]},
                reglas, reglas_prod)

            fila_lote = ctk.CTkFrame(card, fg_color="transparent")
            fila_lote.pack(fill="x", padx=10, pady=(0, 6))

            edad = formato.edad_tanda(dias_l) or "sin fecha"
            if pct_l:
                texto = (f"${precio_l:.2f} (antes ${p['precio']:.2f}, -{pct_l:.0f}%)  "
                         f"·  {edad}  ·  Stock: {lote['stock']}")
                color = theme.WARNING
            else:
                texto = f"${p['precio']:.2f}  ·  {edad}  ·  Stock: {lote['stock']}"
                color = theme.TEXT_SECONDARY
            ctk.CTkLabel(fila_lote, text=texto, text_color=color, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left", fill="x", expand=True)

            ctk.CTkButton(
                fila_lote, text="+ Agregar", width=90,
                fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                text_color=theme.ACCENT_TEXT,
                command=lambda p=p, lote=lote, precio_l=precio_l, pct_l=pct_l:
                    self._agregar(p, lote, precio_l, pct_l)
            ).pack(side="right")

    # ── Lógica del carrito ────────────────────────────────────────────────────

    def _agregar(self, p, lote, precio_efectivo, pct):
        lote_id = lote["id"]
        en_carrito = self.carrito.get(lote_id, {}).get("cantidad", 0)
        if en_carrito >= lote["stock"]:
            messagebox.showwarning(
                "Stock insuficiente",
                f"Solo hay {lote['stock']} unidad(es) disponible(s) de '{p['nombre']}' "
                "en esta tanda.",
                parent=self)
            return
        if lote_id in self.carrito:
            self.carrito[lote_id]["cantidad"] += 1
        else:
            self.carrito[lote_id] = {
                "producto_id": p["id"],
                "nombre": p["nombre"],
                "precio": precio_efectivo,
                "descuento_pct": pct,
                "cantidad": 1,
                "stock": lote["stock"],
            }
        self._refrescar_carrito()

    def _cambiar_cantidad(self, lote_id, delta):
        nueva = self.carrito[lote_id]["cantidad"] + delta
        if nueva <= 0:
            self._quitar(lote_id)
            return
        if delta > 0:
            # Verificar stock actualizado del lote desde la BD
            try:
                lote = db.get_lote(lote_id)
            except db.DBError as e:
                messagebox.showerror("Error de base de datos", str(e), parent=self)
                return
            if lote and nueva > lote["stock"]:
                messagebox.showwarning(
                    "Stock insuficiente",
                    f"Solo hay {lote['stock']} unidad(es) de '{self.carrito[lote_id]['nombre']}' "
                    "en esta tanda.",
                    parent=self)
                return
        self.carrito[lote_id]["cantidad"] = nueva
        self._refrescar_carrito()

    def _quitar(self, lote_id):
        self.carrito.pop(lote_id, None)
        self._refrescar_carrito()

    def _limpiar(self):
        self.carrito.clear()
        self._pago_var.set("")
        self._refrescar_carrito()

    # ── Pago y cambio ─────────────────────────────────────────────────────────

    def _total_carrito(self):
        return sum(i["precio"] * i["cantidad"] for i in self.carrito.values())

    def _leer_pago(self):
        """
        Con cuánto paga el cliente, tal como está escrito en el campo.
        Devuelve (monto, error): monto None y error None si el campo está
        vacío (es opcional), o monto None y un texto de error si lo que
        hay no es un número.

        Se toleran el "$" y la coma decimal ("100,50") porque es lo que
        sale de tipear rápido en el mostrador. La coma NO se usa como
        separador de miles a propósito: en un campo de efectivo se
        escribe "1000", no "1,000", y aceptar las dos lecturas haría que
        "100,50" fuera ambiguo entre $100.50 y $10,050.
        """
        txt = self._pago_var.get().strip().replace("$", "").replace(" ", "")
        if not txt:
            return None, None
        try:
            return float(txt.replace(",", ".")), None
        except ValueError:
            return None, "Monto inválido"

    def _actualizar_cambio(self):
        monto, error = self._leer_pago()
        if error:
            self.lbl_cambio.configure(text=error, text_color=theme.WARNING)
            return
        if monto is None:
            self.lbl_cambio.configure(text="")
            return
        cambio = monto - self._total_carrito()
        if cambio < -0.005:
            self.lbl_cambio.configure(text=f"Falta ${-cambio:,.2f}", text_color=theme.DANGER)
        else:
            # El `max(0.0, ...)` no es paranoia: pagando JUSTO, la resta de
            # dos float da -0.0 o un residuo negativo minúsculo, y el
            # formateo lo imprime como "$-0.00" -- se veía así en la
            # primera versión. Todo lo que caiga en esta rama y no sea
            # positivo es cambio cero.
            self.lbl_cambio.configure(text=f"Cambio: ${max(0.0, cambio):,.2f}",
                                      text_color=theme.ACCENT)

    def _refrescar_carrito(self):
        for w in self.panel_carrito.winfo_children():
            w.destroy()

        if not self.carrito:
            ctk.CTkLabel(self.panel_carrito,
                         text="El carrito está vacío.\nUsa '+ Agregar' en los productos.",
                         text_color=theme.TEXT_DISABLED, justify="center").pack(pady=20)
            self.lbl_total.configure(text="Total: $0.00")
            self._actualizar_cambio()
            return

        total = 0.0
        for lote_id, item in self.carrito.items():
            subtotal = item["precio"] * item["cantidad"]
            total += subtotal

            fila = ctk.CTkFrame(self.panel_carrito,
                                fg_color=theme.BG_CARD, corner_radius=6)
            fila.pack(fill="x", pady=2)

            nombre_txt = item["nombre"]
            if item.get("descuento_pct"):
                nombre_txt += f"  (-{item['descuento_pct']:.0f}% antigüedad)"
            color_nombre = theme.WARNING if item.get("descuento_pct") else theme.TEXT_PRIMARY
            ctk.CTkLabel(fila, text=nombre_txt, anchor="w", text_color=color_nombre,
                         font=ctk.CTkFont(weight="bold")).pack(
                side="left", padx=8, pady=6, fill="x", expand=True)

            controles = ctk.CTkFrame(fila, fg_color="transparent")
            controles.pack(side="right", padx=6, pady=4)

            ctk.CTkButton(controles, text="−", width=30,
                          fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                          command=lambda lid=lote_id: self._cambiar_cantidad(lid, -1)).pack(side="left")
            ctk.CTkLabel(controles, text=str(item["cantidad"]), text_color=theme.TEXT_PRIMARY,
                         width=32, anchor="center").pack(side="left")
            ctk.CTkButton(controles, text="+", width=30,
                          fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                          command=lambda lid=lote_id: self._cambiar_cantidad(lid, 1)).pack(side="left")
            ctk.CTkLabel(controles, text=f"${subtotal:.2f}", text_color=theme.TEXT_PRIMARY,
                         width=70, anchor="e").pack(side="left", padx=(8, 4))
            ctk.CTkButton(controles, text="✕", width=30,
                          fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                          command=lambda lid=lote_id: self._quitar(lid)).pack(side="left")

        self.lbl_total.configure(text=f"Total: ${total:.2f}")
        # El cambio depende del total, así que se recalcula con cada
        # movimiento del carrito y no solo cuando se tipea el pago.
        self._actualizar_cambio()

    # ── Confirmar venta ───────────────────────────────────────────────────────

    def _confirmar(self):
        if not self.carrito:
            messagebox.showwarning("Carrito vacío",
                                   "Agrega al menos un producto antes de confirmar.",
                                   parent=self)
            return

        # El pago se valida ANTES de tocar la base: registrar la venta y
        # después avisar que el monto estaba mal dejaría el stock ya
        # descontado y obligaría a anular.
        pago, error_pago = self._leer_pago()
        if error_pago:
            messagebox.showwarning(
                "Pago inválido",
                "Lo escrito en 'Paga con' no es un monto válido.\n\n"
                "Escribí solo el número (por ejemplo 100 o 100.50), o dejalo "
                "vacío si no querés que el ticket muestre el cambio.",
                parent=self)
            return

        items = [
            {
                "producto_id": v["producto_id"],
                "lote_id": lote_id,
                "nombre": v["nombre"],
                "cantidad": v["cantidad"],
                "precio_unitario": v["precio"],
                "subtotal": v["precio"] * v["cantidad"],
            }
            for lote_id, v in self.carrito.items()
        ]

        # Verificar stock en tiempo real antes de registrar
        try:
            errores = db.verificar_stock(items)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        if errores:
            messagebox.showerror(
                "Stock insuficiente",
                "No hay suficiente stock para:\n\n" + "\n".join(errores),
                parent=self)
            return

        total = sum(i["subtotal"] for i in items)
        # Pagar con MENOS que el total sí frena la venta, a diferencia de
        # dejar el campo vacío: no es un dato que falte, es un dato que no
        # cierra, y el ticket saldría con un cambio negativo. El medio
        # centavo de tolerancia es por el redondeo de los REAL.
        if pago is not None and pago < total - 0.005:
            messagebox.showwarning(
                "El pago no alcanza",
                f"El total es ${total:,.2f} y en 'Paga con' dice ${pago:,.2f}.\n\n"
                "Corregí el monto, o dejá el campo vacío si no querés registrarlo.",
                parent=self)
            return
        # Sin diálogo de "¿estás seguro?": el carrito completo y el total
        # están a la vista justo al lado del botón, así que la confirmación
        # no aportaba información nueva -- solo un click más en la acción
        # más frecuente del día. Una venta mal registrada se anula desde
        # Historial y devuelve el stock (ver anular_venta()).
        try:
            venta_id = db.registrar_venta(items, pago)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        # max(0.0, ...) por lo mismo que en _actualizar_cambio(): pagar justo
        # deja un -0.0 que se imprime como "$-0.00".
        cambio = None if pago is None else max(0.0, pago - total)
        self.carrito.clear()
        self._pago_var.set("")
        self._refrescar_carrito()
        self.refresh()
        self._mostrar_aviso(venta_id, total, cambio)

    # ── Aviso post-venta ──────────────────────────────────────────────────────

    def _mostrar_aviso(self, venta_id, total, cambio=None):
        # No todos los clientes quieren ticket, así que no se genera solo;
        # queda como botón acá, visible pero sin frenar la venta siguiente.
        # El cambio se repite acá porque al confirmar se limpia el carrito
        # (y con él el "Cambio:" del pie): justo cuando hay que contarlo.
        texto = f"✓ Venta #{venta_id} registrada — ${total:,.2f}"
        if cambio is not None:
            texto += f"  ·  Cambio: ${cambio:,.2f}"
        self._aviso_lbl.configure(text=texto)
        self._aviso_btn.configure(command=lambda: self._generar_ticket(venta_id))
        self._aviso.grid()
        if self._aviso_job:
            self.after_cancel(self._aviso_job)
        # 12s: alcanza para decidir si el cliente quiere ticket, y se va solo
        # para que no quede un aviso viejo colgado sobre la venta siguiente.
        self._aviso_job = self.after(12000, self._ocultar_aviso)

    def _ocultar_aviso(self):
        if self._aviso_job:
            self.after_cancel(self._aviso_job)
            self._aviso_job = None
        self._aviso.grid_remove()

    def _generar_ticket(self, venta_id):
        try:
            venta = db.get_venta(venta_id)
            detalle = db.get_detalle_venta(venta_id)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return
        try:
            ticket.generar_y_abrir(venta, detalle)
        except ticket.TicketError as e:
            messagebox.showerror("Ticket", str(e), parent=self)
            return
        # Ticket ya generado: el aviso cumplió su función, se va sin esperar
        # los 12s (si no, invita a generarlo dos veces).
        self._ocultar_aviso()
