import sys
from tkinter import messagebox

import actualizaciones
import customtkinter as ctk
import database as db
import registro
import version
from views import branding, theme
from views.productos import ProductosFrame
from views.inventario import InventarioFrame
from views.nueva_venta import NuevaVentaFrame
from views.historial import HistorialFrame
from views.graficos import GraficosPanel
from views.ajustes import AjustesFrame

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Cuanto antes: a partir de acá, lo que reviente adentro de un botón
        # o un `bind` queda anotado en vez de perderse en un stderr que en
        # el .exe no existe.
        registro.enganchar_tk(self)
        self.title("Panadería — Sistema de ventas")
        self.geometry("1050x680")
        self.minsize(820, 560)
        self.configure(fg_color=theme.BG_APP)

        icono = branding.icono_ventana()
        if icono:
            try:
                self.iconbitmap(str(icono))
            except Exception:
                pass  # ícono ausente/corrupto no debe impedir arrancar la app

        db.respaldar_db()
        try:
            db.init_db()
        except db.DBError as e:
            messagebox.showerror("Error al iniciar", str(e))
            self.destroy()
            sys.exit(1)

        # ── Barra lateral de navegación ───────────────────────────────────────
        nav = ctk.CTkFrame(self, width=170, corner_radius=0, fg_color=theme.BG_SIDEBAR)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        self._nav = nav  # lo necesita el aviso de versión nueva, que llega después
        self._btn_version = None

        # Marca de agua: el emblema de fondo, detrás de todo lo demás en la
        # barra lateral. Se crea primero para quedar debajo en el orden de
        # apilado (los widgets creados después se dibujan encima). Se
        # regenera cada vez que cambia el alto de la barra (maximizar,
        # restaurar, redimensionar) para que siga sangrando por el borde
        # inferior en vez de quedar "flotando" a mitad de una ventana más
        # alta que el tamaño con el que se generó originalmente.
        self._marca_agua_lbl = None
        self._marca_agua_actual = None
        self._marca_agua_job = None
        marca_agua = branding.marca_agua_sidebar(ancho=170, alto=720)
        if marca_agua:
            self._marca_agua_actual = marca_agua
            self._marca_agua_lbl = ctk.CTkLabel(nav, image=marca_agua, text="")
            self._marca_agua_lbl.place(x=0, y=0)
            nav.bind("<Configure>", self._on_nav_resize)

        logo = branding.logo_sidebar(ancho=128)
        if logo:
            ctk.CTkLabel(nav, image=logo, text="").pack(pady=(24, 16))
        else:
            ctk.CTkLabel(nav, text="Panadería", text_color=theme.TEXT_PRIMARY,
                         font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(24, 20))

        # Dos bloques con rótulo, en vez de una lista plana de cinco botones
        # iguales: "Día a día" es lo que se toca con el local abierto y
        # "Revisar" lo que se consulta después (cerrando caja, viendo cómo
        # viene el mes). Dentro de cada bloque, el orden sigue la frecuencia
        # de uso real, no el orden en que se fueron creando las pantallas.
        # Los rótulos son deliberadamente tenues (TEXT_DISABLED, 10px): están
        # para agrupar, no para competir con los botones.
        self._nav_rotulo(nav, "DÍA A DÍA", primero=True)

        self._btn_venta = ctk.CTkButton(
            nav, text="Nueva venta", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("nueva_venta"))
        self._btn_venta.pack(pady=5, padx=14)

        self._btn_productos = ctk.CTkButton(
            nav, text="Productos", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("productos"))
        self._btn_productos.pack(pady=5, padx=14)

        self._btn_inventario = ctk.CTkButton(
            nav, text="Inventario", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("inventario"))
        self._btn_inventario.pack(pady=5, padx=14)

        self._nav_rotulo(nav, "REVISAR")

        self._btn_historial = ctk.CTkButton(
            nav, text="Historial", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("historial"))
        self._btn_historial.pack(pady=5, padx=14)

        self._btn_analisis = ctk.CTkButton(
            nav, text="Análisis", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("analisis"))
        self._btn_analisis.pack(pady=5, padx=14)

        # Ajustes va anclado abajo del todo (`side="bottom"`), separado de las
        # cinco secciones operativas: es configuración que se toca una vez
        # cada varios meses, así que no debe sumarse a la lista de cosas que
        # el ojo recorre cada vez que se busca una pantalla de uso diario.
        self._btn_ajustes = ctk.CTkButton(
            nav, text="⚙  Ajustes", width=140, text_color=theme.TEXT_PRIMARY,
            command=lambda: self._mostrar("ajustes"))
        self._btn_ajustes.pack(side="bottom", pady=(6, 18), padx=14)

        # ── Área de contenido ─────────────────────────────────────────────────
        self._contenido = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._contenido.pack(side="left", fill="both", expand=True)

        self._frames = {
            "productos":    ProductosFrame(self._contenido),
            "inventario":   InventarioFrame(self._contenido),
            "nueva_venta":  NuevaVentaFrame(self._contenido),
            "historial":    HistorialFrame(self._contenido),
            "analisis":     GraficosPanel(self._contenido),
            "ajustes":      AjustesFrame(self._contenido),
        }

        self._nav_buttons = {
            "productos":    self._btn_productos,
            "inventario":   self._btn_inventario,
            "nueva_venta":  self._btn_venta,
            "historial":    self._btn_historial,
            "analisis":     self._btn_analisis,
            "ajustes":      self._btn_ajustes,
        }

        self._frame_actual = None
        # Arranca en Nueva Venta, no en Productos: vender es lo que se hace
        # decenas de veces por día, mientras que el catálogo se toca una vez
        # por semana. Abrir en Productos costaba un click en cada venta.
        self._mostrar("nueva_venta")

        # Lo último de todo, y en un hilo aparte: la ventana ya está armada y
        # usable antes de que esto siquiera intente salir a internet. Si no
        # hay conexión no pasa nada -- ver `actualizaciones.py`.
        actualizaciones.buscar_en_segundo_plano(self, self._avisar_version_nueva)

    @staticmethod
    def _nav_rotulo(nav, texto, primero=False):
        """Rótulo de un bloque de la barra lateral.

        Sin línea divisoria: el espacio en blanco más el rótulo ya separan
        los bloques, y una línea encima de la marca de agua del emblema
        agregaría ruido justo donde se buscó que hubiera textura sutil.
        """
        ctk.CTkLabel(nav, text=texto, text_color=theme.TEXT_DISABLED,
                     font=ctk.CTkFont(size=10, weight="bold"), anchor="w").pack(
            fill="x", padx=20, pady=(0 if primero else 14, 3))

    def _avisar_version_nueva(self, etiqueta):
        """Un botón discreto al pie de la barra lateral, no un modal.

        Corre en el hilo de Tk (`actualizaciones` se encarga del puente). El
        aviso NO interrumpe: aparece arriba de "⚙ Ajustes", en dorado, y
        espera. Un `messagebox` al arrancar frenaría la primera venta del día
        por algo que puede resolverse cuando cierren -- y va en contra del
        criterio de toda la app, que sacó los modales del flujo de venta.

        Se dibuja una sola vez: si por lo que sea llegaran dos avisos, el
        segundo no apila otro botón.
        """
        if self._btn_version:
            return
        self._btn_version = ctk.CTkButton(
            # lstrip("v") porque el tag viene como "v1.1.0" y en pantalla
            # "Versión v1.1.0" se lee mal.
            self._nav, text=f"↑  Versión {etiqueta.lstrip('v')} lista", width=140,
            fg_color="transparent", hover_color=theme.NAV_INACTIVE_HOVER,
            text_color=theme.ACCENT, font=ctk.CTkFont(size=11),
            command=lambda: self._detalle_version_nueva(etiqueta))
        # side="bottom" apila hacia arriba, y "⚙ Ajustes" ya está packeado,
        # así que este queda justo encima y Ajustes sigue al fondo.
        self._btn_version.pack(side="bottom", pady=(0, 2), padx=14)

    def _detalle_version_nueva(self, etiqueta):
        """Acá sí va un diálogo: lo pidió el usuario al tocar el aviso."""
        abrir = messagebox.askyesno(
            "Hay una versión nueva",
            f"Tenés instalada la versión {version.VERSION} y ya salió la "
            f"{etiqueta.lstrip('v')}.\n\n"
            "Actualizar no borra ninguna venta: el historial vive en la carpeta "
            "Datos, que no se toca.\n\n"
            "¿Abrir la página de descarga en el navegador?",
            parent=self)
        if abrir and not actualizaciones.abrir_pagina():
            messagebox.showinfo(
                "No se pudo abrir el navegador",
                f"Entrá a mano a:\n\n{actualizaciones.URL_DESCARGA}", parent=self)

    def _on_nav_resize(self, event):
        # <Configure> se dispara muchas veces seguidas mientras se arrastra
        # el borde de la ventana; se posterga la regeneración 150ms y se
        # cancela la anterior para no reprocesar la imagen en cada evento.
        if self._marca_agua_job:
            self.after_cancel(self._marca_agua_job)
        alto = event.height
        self._marca_agua_job = self.after(150, lambda: self._regenerar_marca_agua(alto))

    def _regenerar_marca_agua(self, alto):
        self._marca_agua_job = None
        if alto < 100 or not self._marca_agua_lbl:
            return
        nueva = branding.marca_agua_sidebar(ancho=170, alto=alto)
        if nueva:
            self._marca_agua_actual = nueva  # evita que el GC se la lleve
            self._marca_agua_lbl.configure(image=nueva)

    def _mostrar(self, nombre):
        if self._frame_actual:
            self._frame_actual.pack_forget()
        frame = self._frames[nombre]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "refresh"):
            try:
                frame.refresh()
            except db.DBError as e:
                messagebox.showerror("Error de base de datos", str(e), parent=self)
        self._frame_actual = frame

        for key, btn in self._nav_buttons.items():
            if key == nombre:
                btn.configure(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                              text_color=theme.ACCENT_TEXT)
            else:
                btn.configure(fg_color=theme.NAV_INACTIVE, hover_color=theme.NAV_INACTIVE_HOVER,
                              text_color=theme.TEXT_PRIMARY)


if __name__ == "__main__":
    # Antes de construir la ventana: si la app se rompe ARMÁNDOSE (ícono
    # corrupto, base ilegible, permisos), no llega a existir ningún widget
    # que pueda avisar, y sin esto no quedaría rastro de por qué no abrió.
    registro.iniciar()
    try:
        app = App()
    except Exception:
        registro.error("La aplicación no pudo iniciar")
        raise
    app.mainloop()
