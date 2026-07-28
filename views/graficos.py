from datetime import datetime

import numpy as np
import customtkinter as ctk
from tkinter import messagebox
from matplotlib import colormaps
from matplotlib.colors import to_rgb, LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import database as db
from views import formato, theme, widgets

# Fondo del gráfico: negro puro (no theme.BG_CARD) a pedido del usuario,
# para que las barras de colores resalten más.
_FONDO_GRAFICO = "#000000"


def _colores(n):
    """N colores distintos para N barras (una barra, un color). Cicla
    sobre la paleta cualitativa "tab20" de matplotlib (20 colores) si hay
    más barras que colores -- a partir de la barra 21 se repiten."""
    paleta = colormaps["tab20"].colors
    return [paleta[i % len(paleta)] for i in range(n)]


def _barra_gradiente(ax, y, valor, color, alto=0.6):
    """Dibuja una barra horizontal con degradé (de una versión oscurecida
    del color a su tono pleno) en vez de un relleno plano -- se ve menos
    "chata"/genérica que un bloque de un solo tono sólido. El degradé usa
    el MISMO hue de principio a fin (no mezcla colores entre sí), así que
    la identidad de cada producto por color no se pierde.

    Soporta valores negativos (ej. margen negativo, un producto vendido a
    pérdida): la barra crece hacia la izquierda de 0 en vez de la derecha,
    con el degradé invertido para que el tono pleno siga quedando en la
    punta (lejos de cero) y el oscurecido cerca de cero, en ambos casos.
    """
    if valor == 0:
        return  # nada que dibujar; la etiqueta "0" ya la pone el llamador
    rgb = to_rgb(color)
    oscuro = tuple(c * 0.22 for c in rgb)
    gradiente = np.linspace(0, 1, 256).reshape(1, -1)
    if valor < 0:
        cmap = LinearSegmentedColormap.from_list("barra", [rgb, oscuro])
        extent = (valor, 0, y - alto / 2, y + alto / 2)
    else:
        cmap = LinearSegmentedColormap.from_list("barra", [oscuro, rgb])
        extent = (0, valor, y - alto / 2, y + alto / 2)
    im = ax.imshow(gradiente, extent=extent, aspect="auto", cmap=cmap,
                   zorder=2, interpolation="bilinear")
    izquierda, derecha = (valor, 0) if valor < 0 else (0, valor)
    recorte = Rectangle((izquierda, y - alto / 2), derecha - izquierda, alto,
                        transform=ax.transData)
    im.set_clip_path(recorte)


class GraficosPanel(ctk.CTkFrame):
    """Dos gráficos de barras sobre los cortes de caja: total vendido por
    corte en el tiempo, y ranking de productos más vendidos. Ambos se
    recalculan sobre el mismo filtro de rango de fechas (por fecha del
    CORTE, no de cada venta -- son datos ya congelados por hacer_corte(),
    igual criterio que el resto de la sub-pestaña Cortes)."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._desde = None
        self._hasta = None
        self._metrica_ranking = "cantidad"  # o "total" ($) -- toggle en el ranking
        self._top_n = 10  # None = sin límite, mostrar todos
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Análisis", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")

        # `on_manual` solo corre si el usuario tocó Filtrar/Limpiar: filtrar a
        # mano deja de reflejar cualquier preset, así que se apaga el dorado.
        # Los presets, en cambio, aplican su rango con `set_rango()` (que no
        # dispara este callback) para no apagarse a sí mismos.
        self._filtro = widgets.FiltroFechas(
            self, on_cambio=self._set_rango, on_manual=self._olvidar_preset)
        self._filtro.pack(fill="x", padx=20, pady=(0, 4))

        # Presets: atajos para los rangos más comunes, sin tener que
        # tipear fechas a mano cada vez que se entra a mirar el negocio.
        # El que está aplicado se resalta en dorado, igual criterio que
        # las pestañas activas en el resto de la app (Historial, sidebar).
        self._presets = widgets.BotonesPreset(self, self._filtro, [
            ("7", "Últimos 7 cortes", 140, lambda: self._rango_ultimos_cortes(7)),
            ("30", "Últimos 30 cortes", 150, lambda: self._rango_ultimos_cortes(30)),
            ("mes", "Este mes", 100, self._rango_este_mes),
        ])
        self._presets.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(self, text="El rango filtra por la fecha en que se hizo cada corte, no la de cada venta.",
                     text_color=theme.TEXT_DISABLED, font=ctk.CTkFont(size=11)).pack(
            anchor="w", padx=20, pady=(0, 10))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ── Franja de cabecera ────────────────────────────────────────────────
        # Tres números antes de cualquier gráfico. El del medio ("Rematado")
        # es el que no existía en ningún lado: con precios que bajan solos por
        # antigüedad, dos cortes con el mismo total pueden ser negocios muy
        # distintos, y las barras no distinguían pan fresco a precio pleno de
        # pan de tres días liquidado. Va como texto y no como cuarto gráfico
        # a propósito -- es un número que se lee de un vistazo, no una serie.
        cabecera = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cabecera.pack(fill="x", pady=(0, 14))
        franja = ctk.CTkFrame(cabecera, fg_color="transparent")
        franja.pack(fill="x")
        for col in range(3):
            franja.columnconfigure(col, weight=1, uniform="kpi")
        self._kpi_vendido = self._tarjeta_kpi(franja, 0, "Vendido", theme.TEXT_PRIMARY)
        self._kpi_rematado = self._tarjeta_kpi(franja, 1, "Rematado por antigüedad", theme.WARNING)
        self._kpi_margen = self._tarjeta_kpi(franja, 2, "Margen real", theme.SUCCESS)

        # Nota al pie de la franja: aparece solo cuando hay algo que aclarar
        # (cortes sin el dato de precio de lista, o sin costo cargado). Si
        # los tres números son completos, no ocupa lugar.
        # Es el último hijo de `cabecera`, así que volver a empaquetarlo lo
        # devuelve a su lugar (debajo de las tarjetas) sin reordenar nada.
        self._kpi_nota = ctk.CTkLabel(cabecera, text="", text_color=theme.TEXT_DISABLED,
                                      font=ctk.CTkFont(size=11), anchor="w", justify="left",
                                      wraplength=900)
        self._kpi_nota.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(self.scroll, text="Total vendido por corte", text_color=theme.TEXT_PRIMARY,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", pady=(0, 4))
        self._frame_totales = ctk.CTkFrame(self.scroll, fg_color=_FONDO_GRAFICO, corner_radius=6)
        self._frame_totales.pack(fill="x", pady=(0, 20))

        ranking_header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        ranking_header.pack(fill="x", pady=(0, 4))
        # El título cambia con la métrica: "Producto más vendido" era fijo y
        # ya mentía con "Margen ($)". Cada métrica responde una pregunta
        # distinta, así que conviene que el encabezado la nombre en vez de
        # obligar a deducirla del botón dorado.
        self._lbl_ranking = ctk.CTkLabel(
            ranking_header, text="", text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_ranking.pack(side="left")
        toggle = ctk.CTkFrame(ranking_header, fg_color="transparent")
        toggle.pack(side="right")
        self._btn_metrica_cantidad = ctk.CTkButton(
            toggle, text="Cantidad", width=84,
            command=lambda: self._cambiar_metrica_ranking("cantidad"))
        self._btn_metrica_cantidad.pack(side="left", padx=(0, 6))
        self._btn_metrica_total = ctk.CTkButton(
            toggle, text="Monto", width=72,
            command=lambda: self._cambiar_metrica_ranking("total"))
        self._btn_metrica_total.pack(side="left", padx=(0, 6))
        self._btn_metrica_margen = ctk.CTkButton(
            toggle, text="Margen", width=72,
            command=lambda: self._cambiar_metrica_ranking("margen"))
        self._btn_metrica_margen.pack(side="left", padx=(0, 6))
        self._btn_metrica_pleno = ctk.CTkButton(
            toggle, text="% pleno", width=80,
            command=lambda: self._cambiar_metrica_ranking("pleno"))
        self._btn_metrica_pleno.pack(side="left")
        self._botones_metrica = {"cantidad": self._btn_metrica_cantidad,
                                 "total": self._btn_metrica_total,
                                 "margen": self._btn_metrica_margen,
                                 "pleno": self._btn_metrica_pleno}
        self._actualizar_botones_metrica()

        top_n_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        top_n_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(top_n_row, text="Mostrar top:", text_color=theme.TEXT_SECONDARY).pack(
            side="left", padx=(0, 6))
        self._e_top_n = ctk.CTkEntry(top_n_row, width=60, fg_color=theme.BG_INPUT,
                                     text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self._e_top_n.insert(0, "10")
        self._e_top_n.pack(side="left", padx=(0, 6))
        self._e_top_n.bind("<Return>", lambda e: self._aplicar_top_n())
        ctk.CTkButton(top_n_row, text="Aplicar", width=80,
                      fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                      command=self._aplicar_top_n).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(top_n_row, text="(vacío = mostrar todos)", text_color=theme.TEXT_DISABLED,
                     font=ctk.CTkFont(size=11)).pack(side="left")

        self._frame_ranking = ctk.CTkFrame(self.scroll, fg_color=_FONDO_GRAFICO, corner_radius=6)
        self._frame_ranking.pack(fill="x", pady=(0, 20))

        self.refresh()

    @staticmethod
    def _tarjeta_kpi(padre, columna, titulo, color_valor):
        """Una tarjeta de la franja. Devuelve el label del valor (lo único
        que cambia al refrescar); el rótulo se arma una sola vez."""
        card = ctk.CTkFrame(padre, fg_color=theme.BG_CARD, corner_radius=6)
        card.grid(row=0, column=columna, sticky="ew", padx=(0 if columna == 0 else 6, 0))
        ctk.CTkLabel(card, text=titulo, text_color=theme.TEXT_DISABLED,
                     font=ctk.CTkFont(size=11), anchor="w").pack(
            anchor="w", padx=12, pady=(9, 0))
        valor = ctk.CTkLabel(card, text="—", text_color=color_valor,
                             font=ctk.CTkFont(size=20, weight="bold"), anchor="w")
        valor.pack(anchor="w", padx=12, pady=(0, 9))
        return valor

    def refresh(self):
        self._actualizar_kpis()
        self._dibujar_totales()
        self._dibujar_ranking()

    def _actualizar_kpis(self):
        try:
            r = db.get_resumen_analisis(self._desde, self._hasta)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        if r["cortes_totales"] == 0:
            for lbl in (self._kpi_vendido, self._kpi_rematado, self._kpi_margen):
                lbl.configure(text="—")
            self._mostrar_nota("No hay cortes en el rango seleccionado.")
            return

        self._kpi_vendido.configure(text=f"${r['total']:,.0f}")

        notas = []
        # Rematado: cuánto se dejó de cobrar por el descuento por antigüedad.
        # Solo tiene sentido sobre cortes que guardaron el precio de lista.
        if r["cortes_con_lista"] == 0:
            self._kpi_rematado.configure(text="sin datos", text_color=theme.TEXT_DISABLED)
            notas.append("El remate por antigüedad se empieza a registrar en las ventas "
                         "hechas desde esta versión: los cortes anteriores no guardaron el "
                         "precio de lista y no se puede reconstruir.")
        else:
            monto = f"${r['rematado']:,.0f}"
            self._kpi_rematado.configure(text=f"{monto}  ({r['rematado_pct']:.0f}%)",
                                         text_color=theme.WARNING)
            if r["cortes_con_lista"] < r["cortes_totales"]:
                notas.append(f"Remate calculado sobre {r['cortes_con_lista']} de "
                             f"{r['cortes_totales']} cortes del rango (el resto es anterior "
                             "al registro del precio de lista).")

        # Margen: el criterio de "costo en 0 = sin datos" es el mismo que
        # usa el ranking; no se muestra un margen igual al total como si
        # fuera 100% de ganancia.
        if r["costo_total"] <= 0:
            self._kpi_margen.configure(text="sin datos", text_color=theme.TEXT_DISABLED)
            notas.append("Sin costo cargado en los productos no se puede calcular el margen.")
        else:
            # $ y % juntos, mismo formato que "Rematado": el monto dice
            # cuánta plata quedó y el porcentaje si el negocio es
            # eficiente. Uno solo de los dos se malinterpreta -- un mes
            # con más margen en $ puede tener peor margen en %.
            self._kpi_margen.configure(
                text=f"${r['margen']:,.0f}  ({r['margen_pct']:.0f}%)",
                text_color=theme.SUCCESS if r["margen"] >= 0 else theme.DANGER)
            # Aviso de margen parcial: el número de arriba trata el costo
            # faltante como 0, así que queda OPTIMISTA. Mismo espíritu que
            # el aviso de stock bajo en Inventario -- es el dato que hace
            # falta para saber si conviene confiar en el número.
            if r["sin_costo_total"] > 0:
                pct = r["sin_costo_total"] / r["total"] * 100 if r["total"] else 0
                nombres = r["sin_costo_nombres"]
                lista = ", ".join(nombres[:3]) + ("…" if len(nombres) > 3 else "")
                notas.append(f"El margen está optimista: ${r['sin_costo_total']:,.0f} "
                             f"({pct:.0f}%) de lo vendido en el rango es de productos sin "
                             f"costo cargado ({lista}) y cuenta como si costaran $0. "
                             "Cargales el costo en Productos para que el número cierre.")

        self._mostrar_nota("  ".join(notas))

    def _mostrar_nota(self, texto):
        self._kpi_nota.configure(text=texto)
        if texto:
            self._kpi_nota.pack(fill="x", pady=(6, 0))
        else:
            self._kpi_nota.pack_forget()

    def _set_rango(self, desde_iso, hasta_iso):
        """Callback de `widgets.FiltroFechas`: llega ya validado y en ISO,
        venga de los campos o de un preset."""
        self._desde = desde_iso
        self._hasta = hasta_iso
        self.refresh()

    def _olvidar_preset(self):
        """El usuario filtró a mano: ningún preset queda "seleccionado"."""
        self._presets.olvidar()

    def _rango_ultimos_cortes(self, n):
        """Rango que arranca en el más viejo de los últimos n cortes.
        Devuelve None (y avisa) si no se puede calcular: ahí el preset no
        queda seleccionado, porque no está representando nada."""
        try:
            cortes = db.get_cortes()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return None
        if not cortes:
            messagebox.showinfo("Sin datos", "Todavía no hay cortes registrados.", parent=self)
            return None
        cortes_desc = sorted(cortes, key=lambda c: c["fecha"], reverse=True)
        ultimos = cortes_desc[:n]
        return ultimos[-1]["fecha"][:10], None  # el más viejo de los últimos n

    @staticmethod
    def _rango_este_mes():
        hoy = datetime.now()
        return f"{hoy.year:04d}-{hoy.month:02d}-01", None

    def _cambiar_metrica_ranking(self, metrica):
        self._metrica_ranking = metrica
        self._actualizar_botones_metrica()
        self._dibujar_ranking()

    # Cada métrica nombra su propia pregunta. "% pleno" es la única que se
    # ordena de peor a mejor (ver _dibujar_ranking), y el título lo dice.
    _TITULOS_RANKING = {
        "cantidad": "El más vendido",
        "total":    "El que más facturó",
        "margen":   "El de más margen",
        "pleno":    "Lo que más se remata",
    }

    def _actualizar_botones_metrica(self):
        activo = {"fg_color": theme.ACCENT, "hover_color": theme.ACCENT_HOVER,
                  "text_color": theme.ACCENT_TEXT}
        inactivo = {"fg_color": theme.NEUTRAL, "hover_color": theme.NEUTRAL_HOVER,
                    "text_color": theme.TEXT_PRIMARY}
        for key, btn in self._botones_metrica.items():
            btn.configure(**(activo if key == self._metrica_ranking else inactivo))
        self._lbl_ranking.configure(text=self._TITULOS_RANKING[self._metrica_ranking])

    def _aplicar_top_n(self):
        txt = self._e_top_n.get().strip()
        if txt == "":
            self._top_n = None
            self._dibujar_ranking()
            return
        try:
            n = int(txt)
            if n <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Error",
                "El límite tiene que ser un número entero mayor a 0 (o vacío para mostrar todos).",
                parent=self)
            return
        self._top_n = n
        self._dibujar_ranking()

    @staticmethod
    def _limpiar_frame(frame):
        for w in frame.winfo_children():
            w.destroy()

    @staticmethod
    def _estilo_ejes(fig, ax):
        """Estilo compartido de los dos gráficos: fondo negro puro (para
        que resalten las barras de colores), sin bordes arriba/derecha,
        grilla sólida y recesiva (un gris apenas visible sobre negro,
        nunca punteada)."""
        fig.patch.set_facecolor(_FONDO_GRAFICO)
        ax.set_facecolor(_FONDO_GRAFICO)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("bottom", "left"):
            ax.spines[lado].set_color("#333333")
        ax.tick_params(colors=theme.TEXT_SECONDARY, labelsize=9)
        ax.set_axisbelow(True)

    def _dibujar_totales(self):
        self._limpiar_frame(self._frame_totales)
        try:
            cortes = db.get_cortes()
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        if self._desde:
            cortes = [c for c in cortes if c["fecha"][:10] >= self._desde]
        if self._hasta:
            cortes = [c for c in cortes if c["fecha"][:10] <= self._hasta]
        cortes = sorted(cortes, key=lambda c: c["fecha"])  # cronológico, viejo -> nuevo

        if not cortes:
            ctk.CTkLabel(self._frame_totales, text="No hay cortes en el rango seleccionado.",
                         text_color=theme.TEXT_DISABLED).pack(pady=30)
            return

        etiquetas = [formato.fecha(c["fecha"])[:10] for c in cortes]
        valores = [c["total_ventas"] for c in cortes]
        x = range(len(valores))

        # Segunda serie: lo que habría entrado si nada se hubiera rematado.
        # Se arma reemplazando la parte del corte que SÍ tiene precio de
        # lista guardado por su valor de lista, y dejando el resto como
        # está -- por eso es `total - lista_cobrado + lista_total` y no
        # simplemente `lista_total`, que solo cubre una parte del corte.
        # Un corte sin el dato queda en NaN y matplotlib corta la línea
        # ahí: preferible un hueco antes que dibujar las dos series
        # pegadas, que se leería como "ese día no se remató nada".
        lista = []
        for c in cortes:
            if (c["lista_total"] or 0) > 0:
                lista.append(c["total_ventas"] - c["lista_cobrado"] + c["lista_total"])
            else:
                lista.append(float("nan"))
        hay_lista = any(v == v for v in lista)  # NaN != NaN

        # Línea de tiempo (no barras): el eje X es tiempo, y una línea lee
        # mejor la tendencia corte a corte que columnas sueltas. Relleno
        # sutil bajo la línea para que pese más visualmente sin sumar otro
        # color.
        fig = Figure(figsize=(8, 3.6), dpi=100)
        ax = fig.add_subplot(111)
        if hay_lista:
            # La de lista va punteada y sin marcadores: es una referencia,
            # no una serie que se mire por su propio valor. Lo que importa
            # es el HUECO entre ambas -- eso es lo rematado, así que se
            # pinta en el mismo naranja que el número "Rematado" de la
            # franja de arriba. La línea de lista queda por debajo en
            # zorder para que la real siga siendo la protagonista.
            ax.plot(x, lista, color=theme.WARNING, linewidth=1.4, linestyle=(0, (5, 3)),
                    alpha=0.9, zorder=2, label="Si nada se remataba")
            ax.fill_between(x, valores, lista, color=theme.WARNING, alpha=0.18, zorder=1)
        ax.plot(x, valores, color=theme.ACCENT, linewidth=2.4, solid_capstyle="round",
               marker="o", markersize=7, markerfacecolor=theme.ACCENT,
               markeredgecolor=_FONDO_GRAFICO, markeredgewidth=1.4, zorder=4,
               label="Cobrado")
        ax.fill_between(x, valores, color=theme.ACCENT, alpha=0.15, zorder=3)
        self._estilo_ejes(fig, ax)
        if hay_lista:
            # Leyenda solo cuando hay dos series: con una sola, el título
            # del gráfico ya dice todo y una leyenda sería ruido.
            # loc="best": la deja donde menos tape la curva. Con "upper left"
            # fijo se montaba encima de los datos cuando el pico cae temprano.
            leyenda = ax.legend(loc="best", fontsize=8.5, framealpha=1,
                                facecolor=_FONDO_GRAFICO, edgecolor="#333333")
            for texto in leyenda.get_texts():
                texto.set_color(theme.TEXT_SECONDARY)
        ax.yaxis.grid(True, color="#333333", linewidth=0.6)
        ax.xaxis.grid(False)
        ax.set_ylim(bottom=0)
        muchas = len(etiquetas) > 8
        ax.set_xticks(list(x))
        ax.set_xticklabels(etiquetas, rotation=45 if muchas else 0, ha="right" if muchas else "center")
        ax.set_ylabel("Total ($)", color=theme.TEXT_SECONDARY, fontsize=9)

        # Con pocos puntos (ej. después de filtrar "últimos 7 cortes") se
        # etiqueta cada uno -- a esa escala no satura. Con muchos, solo el
        # pico y el más reciente, dejando el resto al eje (el valor exacto
        # de cada uno ya está en la tabla de Historial > Cortes).
        if len(valores) <= 15:
            a_etiquetar = set(x)
        else:
            idx_max = max(x, key=lambda i: valores[i])
            a_etiquetar = {idx_max, len(valores) - 1}
        for i in a_etiquetar:
            ax.annotate(f"${valores[i]:.0f}", (i, valores[i]), textcoords="offset points",
                       xytext=(0, 8), ha="center", color=theme.TEXT_PRIMARY, fontsize=8.5)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._frame_totales)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _dibujar_ranking(self):
        self._limpiar_frame(self._frame_ranking)
        try:
            ranking = db.get_ranking_productos(self._desde, self._hasta)
        except db.DBError as e:
            messagebox.showerror("Error de base de datos", str(e), parent=self)
            return

        if not ranking:
            ctk.CTkLabel(self._frame_ranking, text="No hay ventas cortadas en el rango seleccionado.",
                         text_color=theme.TEXT_DISABLED).pack(pady=30)
            return

        if self._metrica_ranking == "pleno":
            # Un producto sin ninguna venta con precio de lista guardado no
            # tiene con qué comparar -- se excluye, igual que los sin costo
            # en "Margen ($)", en vez de dibujarle un 100% falso.
            ranking = [r for r in ranking if r["pleno_pct"] is not None]
            if not ranking:
                ctk.CTkLabel(self._frame_ranking,
                             text="Todavía no hay ventas con precio de lista registrado en este rango.\n"
                                  "El dato se guarda desde la versión del 2026-07-20 en adelante.",
                             text_color=theme.TEXT_DISABLED, wraplength=600, justify="left").pack(pady=30)
                return
            # ÚNICA métrica que ordena de MENOR a mayor, y no es una
            # inconsistencia caprichosa: acá lo interesante es el peor, no
            # el mejor. Con el orden descendente de las otras tres, un top
            # 10 mostraría los productos que nunca se rematan y escondería
            # justamente los que hay que dejar de hornear de más.
            ranking = sorted(ranking, key=lambda r: r["pleno_pct"])
        elif self._metrica_ranking == "margen":
            # costo_total == 0 significa que ningún producto de ese rango
            # tenía costo cargado en el momento de venderse -- se excluye
            # en vez de mostrar un margen falso (= total, "100%").
            ranking = [r for r in ranking if r["costo_total"] > 0]
            if not ranking:
                ctk.CTkLabel(self._frame_ranking,
                             text="No hay productos con costo cargado para calcular margen en este rango.",
                             text_color=theme.TEXT_DISABLED, wraplength=600).pack(pady=30)
                return
            ranking = sorted(ranking, key=lambda r: r["margen"], reverse=True)
        elif self._metrica_ranking == "total":
            # "cantidad" y "total" son las mismas claves que devuelve
            # get_ranking_productos(); reordenar acá según la métrica
            # elegida porque la consulta siempre viene ordenada por cantidad.
            ranking = sorted(ranking, key=lambda r: r["total"], reverse=True)

        top = ranking if self._top_n is None else ranking[:self._top_n]
        nombres = [r["nombre"] for r in top]
        # "pleno" es la única métrica cuya clave en el dict no coincide con
        # el nombre del toggle (es un porcentaje calculado, no una suma).
        clave = "pleno_pct" if self._metrica_ranking == "pleno" else self._metrica_ranking
        valores = [r[clave] for r in top]
        y_pos = list(range(len(top)))

        # El alto de la figura crece con la cantidad de barras -- con el
        # límite configurable el usuario puede pedir bastantes más de 10.
        alto_fig = max(3.0, 0.4 * len(top) + 1.2)
        fig = Figure(figsize=(8, alto_fig), dpi=100)
        ax = fig.add_subplot(111)
        colores = _colores(len(valores))
        for y, valor, color, fila in zip(y_pos, valores, colores, top):
            _barra_gradiente(ax, y, valor, color)
            if self._metrica_ranking == "margen":
                # El $ y el % van juntos en la etiqueta en vez de ser dos
                # métricas distintas del toggle: la barra ya está dibujada
                # en $ (que es lo que se compara entre productos) y el %
                # es el dato que dice si ese monto es eficiente o solo
                # grande. Sumar un quinto botón no entraba a lo ancho.
                texto = f"${valor:.0f}"
                if fila["margen_pct"] is not None:
                    texto += f"  ({fila['margen_pct']:.0f}%)"
            elif self._metrica_ranking == "total":
                texto = f"${valor:.0f}"
            elif self._metrica_ranking == "pleno":
                texto = f"{valor:.0f}%"
            else:
                texto = f"{valor:d}"
            # La etiqueta va del lado de la punta de la barra (derecha si
            # es positiva, izquierda si es negativa) -- relevante sobre
            # todo para "Margen", que puede ser negativo.
            if valor < 0:
                xytext, ha = (-6, 0), "right"
            else:
                xytext, ha = (6, 0), "left"
            ax.annotate(texto, (valor, y), textcoords="offset points", xytext=xytext,
                       va="center", ha=ha, color=theme.TEXT_PRIMARY, fontsize=9)

        self._estilo_ejes(fig, ax)
        ax.xaxis.grid(True, color="#333333", linewidth=0.6)
        ax.yaxis.grid(False)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(nombres)
        ax.set_ylim(-0.5, len(top) - 0.5)
        ax.invert_yaxis()  # arriba, el primero del orden elegido más arriba

        minimo = min(valores + [0])
        maximo = max(valores + [0])
        # "margen" lleva más pad porque su etiqueta trae dos valores
        # ($ y %) y con el 0.18 del resto se salía del área del gráfico.
        factor = 0.28 if self._metrica_ranking == "margen" else 0.18
        pad = (maximo - minimo) * factor or 1
        ax.set_xlim(minimo - (pad if minimo < 0 else 0), maximo + pad)
        if minimo < 0:
            ax.axvline(0, color="#333333", linewidth=0.8, zorder=1)

        if self._metrica_ranking == "pleno":
            # Referencia en 100%: es "no se remató nada", el techo de la
            # métrica. Sin ella, un gráfico donde todos rondan el 90% se
            # ve igual de dramático que uno donde rondan el 40%.
            ax.axvline(100, color=theme.SUCCESS, linewidth=1.2,
                       linestyle=(0, (4, 3)), zorder=1)
            ax.set_xlim(0, max(maximo, 100) + pad)

        etiquetas_eje = {"total": "Total vendido ($)",
                         "margen": "Margen ($; el % es sobre lo que facturó ese producto)",
                         "cantidad": "Cantidad vendida",
                         "pleno": "De cada $100 de precio de lista, cuánto entró (100% = nunca se remató)"}
        ax.set_xlabel(etiquetas_eje[self._metrica_ranking], color=theme.TEXT_SECONDARY, fontsize=9)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._frame_ranking)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
