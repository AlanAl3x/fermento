# Panadería — Sistema de Ventas

Documentación técnica del proyecto.

**Última actualización:** 2026-07-21
**Desarrollado por:** Alan (con asistencia de Claude Code)
**Lenguaje:** Python 3.x
**UI:** customtkinter (modo oscuro, paleta de marca "Fermento")
**Base de datos:** SQLite (archivo local `panaderia.db`)

> Para arquitectura, decisiones de diseño y el estado actual del proyecto, ver `CLAUDE.md`. Este documento es la referencia operativa: instalación, empaquetado, reglas de negocio e historial de cambios.

## Descripción general

Aplicación de escritorio para la gestión de ventas de una panadería. Permite registrar los panes disponibles con su precio y stock, registrar pedidos (que pueden incluir varios tipos de pan), hacer cortes de caja periódicos, y consultar el historial de ventas y cortes. El stock se descuenta automáticamente al confirmar cada venta.

- **Usuario objetivo:** una sola persona operando en Windows 10/11.
- **Distribución final:** ejecutable `.exe` generado con PyInstaller.
- **Navegación:** barra lateral fija con cinco secciones (Productos, Inventario, Nueva venta, Historial, Análisis). Historial tiene sub-pestañas Ventas / Cortes. Inventario controla el stock de insumos (harina, levadura, etc.), separado de Productos. Análisis muestra gráficos comparativos entre cortes. Cada pantalla recarga sus datos desde la BD al navegar hacia ella.

## Estructura de archivos

```
panaderia/
├── main.py              Punto de entrada. Inicializa la BD y levanta la ventana principal.
├── database.py          Toda la lógica de SQLite (conexión, consultas, transacciones).
├── rutas.py             BASE_DIR: la carpeta donde la app escribe (base, backups, tickets, log).
├── registro.py          Log de errores a panaderia_error.log.
├── test_dinero.py       Pruebas automáticas de las cuentas (ver "Pruebas" más abajo).
├── empezar_de_cero.py   Vacía la base para arrancar con datos reales (se corre una sola vez).
├── requirements.txt     customtkinter, pillow, matplotlib, reportlab
├── CLAUDE.md            Contexto condensado del proyecto (arquitectura, decisiones).
├── DOCUMENTACION.md      Este archivo.
├── panaderia.db          Base de datos SQLite (se crea automáticamente al primer uso).
├── backups/              Copias de panaderia.db con timestamp, autogeneradas en cada arranque (máx. 30).
├── tickets/              PDFs de tickets de venta generados (respaldo digital, se crea sola al primer ticket).
├── FermentoLogo.jpeg     Logo de la marca. No borrar/mover (ver views/branding.py).
├── assets/fermento.ico   Ícono de ventana/barra de tareas, autogenerado.
└── views/
    ├── theme.py          Paleta de colores del modo oscuro.
    ├── branding.py       Genera los assets visuales desde FermentoLogo.jpeg.
    ├── formato.py        Conversor de fecha ISO -> DD-MM-AAAA para mostrar.
    ├── productos.py      Pantalla de catálogo de productos.
    ├── inventario.py     Pantalla "Inventario": control manual de stock de insumos.
    ├── nueva_venta.py    Pantalla de registro de ventas (carrito).
    ├── historial.py      Historial: contenedor de sub-pestañas Ventas / Cortes.
    ├── ticket.py         Ticket de venta en PDF (A4, para impresora convencional) + apertura del visor.
    ├── cortes.py         Sub-pestaña Cortes: hacer corte, listado, detalle, CSV.
    └── graficos.py       Pantalla "Análisis" (sección propia del sidebar): total por corte y ranking de productos.
```

El esquema completo de la base de datos (tablas y columnas) y la lista de funciones de `database.py` no se repiten acá — están comentados directamente en el código, que es la fuente de verdad. Un resumen rápido del modelo de datos está en `CLAUDE.md`.

## Instalación y ejecución (modo desarrollo)

**Requisitos:** Python 3.9+ y pip.

```bash
pip install -r requirements.txt
python main.py
```

La base de datos `panaderia.db` se crea automáticamente en la misma carpeta si no existe.

## Pruebas

```bash
python -m unittest test_dinero -v
```

Sin instalar nada: `unittest` viene con Python. **No tocan `panaderia.db`** — cada prueba corre contra una base temporal y vacía que se borra al terminar (`_BaseDinero` apunta `database.DB_PATH` a un archivo descartable antes de cada una).

Cubren la matemática de la plata y de la mercadería: el total de una venta contra sus líneas, el de un corte contra las ventas que incluye, que anular devuelva exactamente el stock descontado y al lote correcto, que un corte no vuelva a contar lo del anterior ni incluya anuladas, que precio y costo queden congelados en la venta, y los escalones del descuento por antigüedad. Nada de interfaz: no se abre ninguna ventana.

**Correrlas antes de tocar `database.py`**, y de nuevo después. Si una falla, lo que cambió movió una cuenta.

## Arrancar con datos reales (borrar la demo)

**Ya se hizo, el 2026-07-26.** `panaderia.db` está vacía y esperando los datos reales: la demo de 30 días (301 ventas, 31 cortes, $130.605 que nunca existieron, generada el 2026-07-21 para revisar la app con las pantallas llenas) se borró con este script. El respaldo quedó en `backups/ANTES-DE-BORRAR_2026-07-26_13-16-53_demo.db`. Lo de abajo queda documentado por si alguna vez hay que volver a vaciar la base.

Con la app cerrada:

```bash
python empezar_de_cero.py
```

Muestra qué hay adentro, pide escribir `BORRAR`, deja un respaldo en `backups/ANTES-DE-BORRAR_...db` y vacía todas las tablas. **No borra el archivo ni toca la estructura**: la app abre después exactamente igual.

Deja los contadores de id en cero, así que la primera venta real es la **#1** y no la #302. Después hay que cargar productos e insumos reales desde la app y revisar las reglas de descuento en Ajustes — el script vacía todo, incluido el catálogo (decisión de Alan: los precios de la demo no son los suyos).

El prefijo `ANTES-DE-BORRAR_` mantiene ese respaldo **fuera de la rotación automática** de 30 copias, que solo borra las que se llaman `panaderia_*.db`. Mismo criterio que `ANTES-DE-BORRAR_2026-07-21_pruebas.db`, el respaldo de la base original.

## Empaquetado y actualización (distribución en Windows sin Python instalado)

### Armar el paquete

```bash
pip install pyinstaller       # una sola vez
python empaquetar.py
```

Deja en `dist/` un ZIP listo para mandar: **`Fermento-v1.0.0.zip`** (~41 MB; la carpeta descomprimida son ~87 MB). El número de versión sale de `version.py` — **subirlo ahí antes de empaquetar**, así el nombre del archivo y lo que la app muestra en Ajustes no pueden quedar desincronizados.

El script regenera el ícono, compila, copia el logo y el `.ico` al lado del `.exe`, escribe un `LEEME.txt` con las instrucciones para quien instala, y comprime.

### La estructura, y por qué actualizar no borra nada

Instalada, la app queda partida en dos carpetas hermanas:

```
%USERPROFILE%\Fermento\        (o sea: C:\Users\<usuario>\Fermento)
├─ Datos\        <- base, backups, tickets, log. La crea la app sola.
└─ Programa\     <- el .exe y sus librerías. Viene en el ZIP.
```

- **Instalar**: crear la carpeta `Fermento` dentro de la carpeta personal del usuario y descomprimir el ZIP ahí. Abrir `Programa\Fermento.exe`. La carpeta `Datos\` se crea sola en el primer arranque.
- **Actualizar**: cerrar la app, **borrar `Programa\` entera**, descomprimir el ZIP nuevo en la misma carpeta `Fermento`, abrir.

**Por qué la carpeta personal del usuario y no `C:\Fermento`** (que era la recomendación original): crear una carpeta en la raíz del disco dispara UAC y, con una cuenta estándar, directamente pide contraseña de administrador — una traba justo en el paso 1, con la panadería esperando. **Y por qué tampoco Documentos ni Escritorio**: si la máquina tiene la copia de seguridad de carpetas de OneDrive activada, esas dos se sincronizan solas, y una base SQLite sobre una carpeta que se sincroniza en segundo plano se puede corromper (además de subir 87 MB de programa a la nube en cada actualización). `%USERPROFILE%` es escribible sin permisos y OneDrive no lo toca.

La app no depende de esta ruta: `rutas.py` solo necesita que `Datos\` sea hermana de la carpeta del `.exe`, así que la instalación funciona igual en cualquier carpeta escribible, e incluso se puede mover entera de lugar. La ruta es una recomendación del manual, no un requisito del código.

**El ZIP no contiene ningún dato** — ni base, ni backups, ni tickets, ni log. Eso no es un descuido: es la garantía principal del formato. Mientras el paquete no traiga un `panaderia.db` adentro, ninguna actualización puede pisar el historial de ventas, ni siquiera si quien actualiza se equivoca de carpeta o descomprime encima sin borrar nada primero. La alternativa (programa y datos mezclados en una sola carpeta, como estaba antes) depende de que nadie se equivoque nunca, y ese error no se deshace.

Los cambios de esquema de una versión nueva los aplica `init_db()` sola al abrir, sobre la base que ya estaba. Y como `respaldar_db()` corre **antes** de `init_db()`, el primer arranque después de actualizar deja en `backups/` una copia del estado exacto previo a la migración.

### Por qué `--onedir` y no `--onefile`

Un solo `.exe` es más cómodo de mandar, pero descomprime ~200 MB (matplotlib, customtkinter, Pillow, reportlab) al `%TEMP%` **en cada arranque**: en la máquina de la panadería (i5-6500T) son varios segundos cada vez que abren la app, todos los días. En modo carpeta arranca directo. De paso da menos falsos positivos de antivirus, que es un problema real de los ejecutables autoextraíbles sin firmar.

### Detalles que no se deducen del comando

- **`--collect-data customtkinter`** no es opcional: customtkinter carga sus temas y fuentes desde archivos `.json` que abre en runtime, así que PyInstaller no los detecta siguiendo los imports. Sin esa bandera el `.exe` compila bien y revienta al abrir — la peor forma de fallar, porque no se ve hasta la máquina destino.
- **El logo y el `.ico` se copian al lado del `.exe`**, no van adentro del bundle: `views/branding.py` los busca en `rutas.APP_DIR`. Así se puede reemplazar el JPEG sin recompilar. Si falta el JPEG, la app abre igual con "Panadería" como texto de respaldo.
- **El ícono se regenera en cada build** (`branding.icono_ventana(regenerar=True)`). PyInstaller lo incrusta en tiempo de compilación, así que un `.ico` viejo solo se notaría mirando el escritorio de la panadería.
- **Windows muestra una alerta de SmartScreen** la primera vez, porque el `.exe` no está firmado: "Más información" → "Ejecutar de todas formas". Firmarlo requiere un certificado pago.
- **Respaldo aparte**: la app copia `panaderia.db` a `backups/` en cada arranque (30 últimas). Eso protege contra un archivo dañado o borrado sin querer, **no** contra que se rompa la computadora — para eso hay que copiar `Datos\` a un USB o a la nube cada tanto. Ajustes tiene un botón "Abrir carpeta de datos" justamente para eso.

### Publicar una versión nueva (GitHub)

El repositorio es **público**: <https://github.com/AlanAl3x/fermento>. El código se versiona ahí y el ZIP se distribuye por **Releases**, no por el repo — GitHub rechaza archivos de más de 100 MB y desaconseja los de más de 50, y un binario de 41 MB por versión inflaría el historial para siempre. Por eso `dist/` está en `.gitignore`.

Para sacar una versión nueva, en este orden:

```bash
# 1. Subir el número de versión (fuente única: lo leen el ZIP y la pantalla de Ajustes)
#    editar version.py

# 2. Si cambió algo que se vea en pantalla, regenerar el manual
python generar_manual.py

# 3. Armar el paquete
python empaquetar.py

# 4. Subir el código
git add -A && git commit -m "..." && git push

# 5. Publicar la release con el ZIP adjunto
gh release create v1.1.0 dist/Fermento-v1.1.0.zip --title "Fermento v1.1.0" --notes-file notas.md
```

El enlace **<https://github.com/AlanAl3x/fermento/releases/latest>** siempre apunta a la más reciente: es el que se le manda a la panadería y no cambia entre versiones. Verificado que la descarga funciona **sin iniciar sesión** (HTTP 200 anónimo) — eso solo es cierto porque el repo es público; en uno privado los assets de release exigen autenticación.

**Qué no puede subirse nunca**, ya cubierto por `.gitignore` pero conviene tenerlo presente al agregar archivos: `panaderia.db`, `backups/`, `tickets/`, `panaderia_error.log` y cualquier carpeta `Datos/`. Son las ventas reales del negocio, y una vez en GitHub quedan en el historial aunque se borren después — sacarlas obliga a reescribir la historia del repo. El repo se creó el 2026-07-27, con la base ya vacía, justamente para que no hubiera nada real que filtrar.

### El manual para la panadería

`Fermento - Manual de instalacion y uso.docx` (11 páginas) es el único documento del proyecto escrito **para el usuario final**, no para quien programa. Cinco partes: instalar, actualizar, dónde están los datos, qué hace cada pantalla, y qué hacer si algo falla. Sin tecnicismos y con los pasos de Windows escritos uno por uno ("clic derecho → Extraer todo…").

`empaquetar.py` lo copia dentro de `Programa\`, así que viaja en el ZIP: mandado por separado se pierde en el chat, y quien instala lo necesita justo cuando todavía no tiene la app abierta para preguntar nada.

**Al cambiar algo que se vea en pantalla, revisar si el manual quedó desactualizado** — es el que va a leer la gente del mostrador, y un manual que miente es peor que no tener manual.

### Verificado end-to-end (2026-07-26)

Sobre una instalación limpia en carpeta temporal: descomprimir → abrir (arranca en ~6,5 s en frío, sin errores en el log) → crea `Datos\` con la base → se cargaron productos, insumos, una venta y un corte → **se borró `Programa\` entera y se descomprimió el ZIP de nuevo** → la app volvió a abrir y los datos estaban intactos (misma venta, mismos $48, `PRAGMA integrity_check` en `ok`), más un respaldo automático nuevo en `backups/`.

**Repetido el 2026-07-27 sobre la ruta real** (`%USERPROFILE%\Fermento`, tras cambiar la recomendación desde `C:\Fermento`): la carpeta se creó sin pedir permisos de administrador, el ZIP dejó solo `Programa\`, la app arrancó en 8 s con el log limpio, y `Datos\` quedó como hermana del programa — **sin caer al plan B de `%LOCALAPPDATA%`**, que es la confirmación de que la ruta nueva es escribible y `rutas.py` resuelve bien.

## Validaciones implementadas

- El nombre del producto no puede estar vacío.
- El precio debe ser un número mayor a 0 (acepta coma o punto decimal).
- El stock no puede ser negativo.
- No se puede agregar al carrito más unidades que el stock disponible.
- Al confirmar la venta se reverifica el stock en la BD (protección ante condiciones de carrera).
- No se puede confirmar una venta con el carrito vacío.
- Productos eliminados no aparecen en Nueva Venta pero sí en el Historial.
- No se pueden hacer cortes vacíos (sin ventas pendientes).
- Anular una venta requiere un motivo (no puede quedar vacío).
- No se puede anular una venta que ya fue incluida en un corte cerrado.
- El nombre y la unidad de un insumo no pueden estar vacíos; el stock y el stock mínimo deben ser números >= 0 (acepta decimales).
- El costo interno de un producto es opcional, pero si se carga debe ser un número >= 0 (acepta decimales).
- El N° de item, si se escribe, debe ser un entero mayor a 0; dejarlo vacío es válido y significa “asignalo vos” al dar de alta o “dejalo como está” al editar.
- Dos productos no pueden compartir el N° de item, ni siquiera con uno de ellos dado de baja (lo impide un índice único en la base, además del aviso de la pantalla).

## Pendientes / futuras mejoras

**Funcional**
- [x] ~~Deshacer/borrar el último corte de caja~~ → implementado el
      2026-07-10 (ver Historial de cambios).
- [x] ~~Impresión de ticket en impresora convencional~~ → implementado el
      2026-07-12 como PDF con vista previa (ver Historial de cambios).
      Siguen pendientes las variantes que dependen de hardware/contacto:
      impresora térmica cuando se consiga una, y envío del ticket al
      cliente (WhatsApp descartado -- API oficial pesada para un local
      solo, vías no oficiales frágiles y contra los términos de servicio;
      Telegram técnicamente simple pero un bot no puede escribirle a un
      cliente que no escribió primero; y de fondo `ventas` no guarda
      ningún contacto del cliente hoy). Variante chica y viable ya si se
      pide: mandarse a uno mismo una copia del ticket por Telegram como
      respaldo. Máquina Mercado Pago Point: proyecto aparte (Android/SDK),
      evaluar si se llega a conseguir una. Detalle en `CLAUDE.md`.
- [~] **Mejorar el uso de margen en Análisis** (pedido el 2026-07-11,
      hecho en parte el 2026-07-21 -- ver Historial de cambios).
      **Implementado**: margen total del rango filtrado (ya existía como
      tarjeta "Margen real" desde el 2026-07-10), margen en % junto al $
      tanto en la franja como en la etiqueta de cada barra del ranking, y
      el aviso de margen optimista cuando hay productos sin costo cargado
      en el rango. **Sigue pendiente**, las dos ideas que no entran en la
      mobiliaria actual de la pantalla: línea de tendencia de margen a
      través del tiempo (el dato está en `cortes.costo_total`, pero el
      gráfico de cortes ya tiene dos series y una tercera lo satura --
      habría que decidir si va ahí, en un gráfico chico aparte, o si no
      va), y desglosar costo + margen en el ranking en vez del neto
      (pide barras apiladas o segundo eje: es rediseño, no un agregado).
      Restricción vigente del usuario para ambas: **Análisis tiene que
      seguir simple**.
- [x] ~~Búsqueda/filtro en la lista de productos~~ → implementado el
      2026-07-10 (ver Historial de cambios).
- [x] ~~Filtro por fecha en el historial~~ → implementado el 2026-07-10
      en la sub-pestaña Ventas (ver Historial de cambios).
- [x] ~~Gráficos y comparativas entre cortes/períodos~~ → implementado el
      2026-07-10, nueva sub-pestaña "Gráficos" en Historial (ver Historial
      de cambios).
- [x] ~~Botón para eliminar una venta/factura~~ → implementado como
      **anulación** el 2026-07-09 (ver Historial de cambios).
- [x] ~~Exportación de ventas detalladas a CSV~~ → implementado el
      2026-07-10, botón "Exportar todas las ventas" junto a Cortes (ver
      Historial de cambios).
- [x] ~~Sección de Inventario para control de insumos (harina, levadura,
      etc.)~~ → implementado el 2026-07-10 como control manual, sin
      vínculo con las ventas (ver Historial de cambios).
- [x] ~~Costo interno por producto (para poder sacar márgenes)~~ →
      implementado el 2026-07-10: campo "Costo interno" en Productos +
      columna "Margen" calculada en la lista (ver Historial de cambios).
- [x] ~~Margen agregado a nivel de corte/período~~ → implementado el
      2026-07-10: costo congelado en la venta (`detalle_venta.costo_unitario`),
      propagado a Cortes y Análisis (ver Historial de cambios).
- [ ] **Descuento automático de insumos según receta**: al registrar una
      venta, descontar del stock de Inventario los insumos que consumió
      esa venta (ej. 1 medialuna = 0.05kg harina + ...). Requiere UI para
      definir recetas por producto y tocar `registrar_venta()`. Bastante
      más complejo que el control manual actual de Inventario -- se dejó
      para después a propósito (discutido el 2026-07-10).

**Interfaz — segunda tanda de simplificación** (diagnosticada y aplicada
completa el 2026-07-21; detalle y criterio en `CLAUDE.md`)
- [x] **Nueva Venta: agotados al fondo, agrupados bajo el rótulo "AGOTADOS".**
- [x] **Buscador en Nueva Venta**, mismo patrón que Productos.
- [x] **Modales de éxito de Cortes quitados** (hacer y deshacer); las
      confirmaciones previas se mantienen.
- [x] **`_a_iso()` duplicada** → `views/formato.py::a_iso()`.
- [x] **Dos diálogos de Historial centran a mano** → `dialogos.centrar_sobre()`.
- [x] **Bloque de filtro Desde/Hasta duplicado** → `views/widgets.py::FiltroFechas`.
- [ ] **"Costo interno" → "Costo"** en el diálogo de Productos, aplicando
      el criterio de usar la palabra del usuario y no la del modelo.

**Robustez** (baja prioridad)
- [x] `PRAGMA foreign_keys = ON` — hecho el 2026-07-24, junto con la migración que lo hace posible.
- [x] Log de errores a archivo (`panaderia_error.log`) — hecho el 2026-07-22.
- [x] Pruebas automáticas de las cuentas (`test_dinero.py`) — hecho el 2026-07-24.
- [ ] Montos en centavos (INTEGER) en vez de REAL. Se midió y **no hay deriva de float** en la base actual; queda como mejora teórica, no como problema observado. Tocaría todas las columnas de plata de seis tablas más toda la interfaz: no encararlo salvo que aparezca un descuadre real.

## Historial de cambios

### 2026-09-09 — Número de item para los productos

- **Qué hace**: cada producto tiene ahora un **N° de item**: un número corto, propio, que se ve en la primera columna de Productos, se puede ordenar por él, y sirve para buscar escribiendo el número en vez del nombre. Al dar de alta viene sugerido el siguiente libre, así que quien no lo quiera usar solo aprieta Guardar y sigue.
- **Es una columna nueva (`productos.codigo`) y NO el `id` de la base, a propósito.** El `id` es la identidad interna: apuntan a él las ventas (`detalle_venta`), las tandas (`lotes`) y las reglas de descuento por producto. Si el número que el usuario edita fuera ese, renumerar un producto reescribiría el historial de ventas. Que sean dos números distintos es el punto: el de adentro no se toca nunca, el de afuera se acomoda a lo que le sirva a la panadería. Hay una prueba dedicada a eso (`test_cambiar_el_numero_no_mueve_ninguna_venta`).
- **La migración numera el catálogo que ya existía con el propio `id` de cada producto.** Son únicos por definición, así que no puede generar repetidos, y el catálogo queda numerado de entrada en vez de obligar a editar producto por producto para estrenar la columna. Después se cambian a gusto.
- **Que no haya dos números iguales lo garantiza un índice único en la base, no la validación de la pantalla.** El diálogo valida antes de guardar para poder decir *cuál* producto tiene ese número — incluso si está dado de baja y no se ve en la lista, que es justo el caso en que “ese número está libre” parece obvio y no lo es —, pero chequear y guardar son dos pasos, y la app abierta dos veces sin querer ya se contempla en el resto del sistema. Mismo criterio de siempre: mensaje claro en la UI, garantía en la base.
- **El índice no puede impedir que la app abra.** Si por lo que sea la base ya tuviera números repetidos, crearlo falla, se registra en el log y se sigue: quedarse sin la restricción es mucho menos grave que una panadería que no puede vender a las 5 de la mañana. Mismo criterio que el backup automático y que la migración de claves foráneas.
- **El número sugerido es el mayor + 1, y no el primer hueco.** Los huecos aparecen al dar de baja productos; rellenarlos haría que un producto nuevo herede el número de uno viejo, que es exactamente lo que confunde a quien estaba buscando por número. Por lo mismo se cuenta a los productos inactivos: uno dado de baja conserva su número (sigue en el historial y se puede reactivar), así que reciclarlo explotaría en cuanto alguien apriete “Reactivar”.
- **Buscar el número es por el principio; buscar el nombre, por cualquier parte.** Escribir “10” trae el 10 y el 102, pero no el 210 — en el nombre, en cambio, lo natural es encontrar “cho” dentro de “Concha de chocolate”. Buscar el número como subcadena traería resultados que no espera nadie parado en el mostrador.
- **Un número repetido avisa con título propio**, “Número de item repetido” y no “Error de base de datos”: no falló nada, falta corregir un dato, y el mensaje dice quién lo está usando. Por dentro es `CodigoEnUso`, que hereda de `DBError` para que cualquier pantalla que ya atrapaba errores de base lo siga cubriendo.
- Verificado: **8 pruebas nuevas en `test_dinero.py` (48 en total, todas pasan)** — alta automática, número elegido a mano, choque entre dos productos, editar a uno ocupado, guardar sin cambiar el propio número, el número de un producto dado de baja, que no se rellenen huecos, y que renumerar no mueva ninguna venta.
- **Todavía no sirve para vender**: el buscador de Nueva Venta sigue filtrando solo por nombre. Por ahora el N° de item es un identificador de catálogo.

### 2026-08-31 — El ticket, rehecho para el rollo de 80 mm
- **El problema, con evidencia en la mano**: Alan mandó la foto de dos tickets de la misma venta, el nuestro al lado del que imprime el sistema que estaban usando mientras tanto. El nuestro era una miniatura ilegible. La causa no era el tamaño de la letra: el PDF se armaba en **hoja A4** con una columna de 120 mm centrada, y al mandarlo a la impresora de rollo el visor achicaba la página entera para que entrara. Todo se reducía en la misma proporción, así que **agrandar las fuentes dentro del A4 no habría cambiado nada**. Lo que cambió es el **tamaño de página**: ahora el PDF mide exactamente el ancho del rollo y no hay nada que escalar.
- **El alto es variable y se calcula con dos pasadas de la misma función.** Un ticket de un producto y uno de diez no miden lo mismo, y reportlab necesita el alto antes de dibujar el primer trazo. `_armar(..., dibujar=False)` hace todas las cuentas —incluido partir los nombres largos, que requiere medir texto— sin estampar nada, y devuelve el alto; después se crea la página y se corre la misma función dibujando. La alternativa (una fórmula aparte tipo "50 mm + 9 mm por producto") se desincroniza en silencio en cuanto alguien agrega un renglón al pie.
- **Desapareció el salto de página**: en un rollo el ticket es una tira continua, así que la página crece hacia abajo lo que haga falta y todo el manejo de `showPage()` de la versión A4 se fue.
- **Dos renglones por producto en vez de cuatro columnas.** En 72 mm útiles, "Producto / Cant. / P. unit. / Subtotal" solo entra achicando la letra hasta donde no se lee — el problema que este cambio venía a resolver. Ahora va el nombre a todo el ancho arriba y "2 x $35.00" con el importe a la derecha abajo. Los nombres largos **se parten entre palabras** en lugar de recortarse con "…": en A4 sobraba ancho, acá no, y el nombre del producto es justo lo que el cliente revisa.
- **Se sumó lo que Alan pidió del ticket de referencia**: la dirección del local bajo el nombre, el conteo de artículos, y las líneas **PAGO CON / SU CAMBIO**. Se sacó "Comprobante sin valor fiscal" (pedido durante la misma sesión): en el mostrador nadie confunde este papel con una factura, y en un rollo cada renglón del pie es papel que se gasta en cada venta.
- **`ventas.pago` es una columna nueva, opcional y NULL-able a propósito.** NULL significa "no se anotó con cuánto pagó" y el ticket omite las dos líneas; un `DEFAULT 0` habría hecho que todas las ventas anteriores dijeran "SU CAMBIO: $0.00", o sea "pagó justo", que es un hecho distinto. **Ningún corte ni reporte la suma**: el corte cuadra contra la mercadería vendida, y sumar el pago lo inflaría con plata que volvió al cliente. Las dos cosas tienen prueba propia (`PagoDelCliente` en `test_dinero.py`, 4 pruebas nuevas, 40 en total), y las tres mutaciones que se probaron contra ellas fueron detectadas.
- **En Nueva Venta hay un campo "Paga con" con el cambio calculado en vivo.** Es opcional, como el resto del flujo de venta: vacío registra igual. Pagar de **menos** sí frena la venta —no es un dato que falte, es un dato que no cierra— y se valida antes de tocar la base, porque registrar y avisar después dejaría el stock ya descontado. Acepta "$" y coma decimal. El aviso verde post-venta repite el cambio, porque al confirmar se limpia el carrito y con él el número del pie, justo cuando hay que contarlo.
- **Dos bugs encontrados probando, no leyendo**:
  - Pagando justo, el cambio se mostraba como **`$-0.00`**: `pago - total` da `-0.0` y el formateo lo imprime con signo. Va con `max(0.0, ...)` en los tres lugares donde el cambio se muestra.
  - El campo "Paga con" **se corría hacia la izquierda mientras se tipeaba adentro**, porque el label del cambio crecía a su derecha y empujaba la fila. Se le fijó el ancho para que reserve el lugar desde el arranque.
- **De paso, `_CAJA_EMBLEMA` venía cortando la base del trigo desde siempre.** Midiendo el JPEG: la tinta del emblema llega al `0.6848` del alto y la caja de recorte cortaba en `0.64` — se perdían unas 12 filas de píxeles. Nadie lo había visto porque los tres consumidores lo disimulaban (el ícono es chico, la marca de agua va tenue y sangrando por el borde, y en el ticket A4 el emblema salía en miniatura); apareció recién con el emblema grande del rollo. Quedó en `0.70`, con margen medido: la palabra "FERMENTO" del logo arranca en el `0.7237`. Como la caja es compartida, el arreglo mejora también el ícono y la marca de agua; el `.ico` se regeneró.
- **Al imprimir hay que dejar la escala en "Tamaño real" / 100 %.** La página ya viene del tamaño del papel; un "ajustar a la página" del visor puede volver a achicarla. Quedó anotado en el manual.
- Verificado: los cuatro casos límite del PDF (venta de un renglón, venta larga, sin pago registrado, venta anulada con montos de siete cifras y un nombre impartible), la migración sobre una copia de la base —idempotente y sin perder filas—, una base con ventas hechas **antes** de la columna (quedan en NULL, con total y stock intactos, y su ticket sale sin las dos líneas), y el flujo completo de la pantalla de venta con sus tres estados de cambio. Las 40 pruebas pasan.

### 2026-07-28 — La app avisa sola cuando hay una versión nueva
- **El problema**: con las versiones publicándose en GitHub, seguía sin haber forma de que la panadería se enterara. Un `.exe` viejo funciona igual de bien que uno nuevo, así que una actualización pendiente no da ninguna señal — había que avisar por teléfono.
- **Qué hace ahora**: al abrir, la app consulta la última release publicada. Si hay una posterior a la instalada, aparece un botón dorado al pie de la barra lateral: *"↑ Versión 1.2.0 lista"*. Al tocarlo, explica qué pasa y ofrece abrir la página de descarga.
- **No interrumpe.** El aviso es un botón, no un `messagebox` al arrancar: frenar la primera venta del día con un modal por algo que se resuelve cuando cierren va en contra del criterio con el que se sacaron los modales del flujo de venta. Al tocarlo sí aparece un diálogo, porque ahí lo pidió el usuario.
- **La app sigue funcionando sin internet, igual de rápido.** Es la primera vez que toca la red, así que la consulta va en un hilo aparte con timeout de 6 segundos, lanzada recién cuando la ventana ya está armada. Medido con un dominio inexistente: falla en **0,06 s** y no muestra nada. Tampoco lo anota en el log — quedarse sin internet no es un error de la aplicación, y llenar el log de eso taparía lo que sí importa.
- **Botón "Buscar actualizaciones" en Ajustes**, que a diferencia del chequeo automático **contesta siempre**: "estás al día", "hay una versión nueva" o "no hay conexión". Ahí el silencio sería un error, porque el usuario apretó un botón esperando una respuesta. Se deshabilita mientras consulta, para que tres clics no disparen tres diálogos encimados.
- **El diálogo aclara que actualizar no borra ventas.** Es exactamente la duda que frena a alguien de actualizar, y decirlo en el momento en que decide es más útil que tenerlo solo en el manual.
- **Sin dependencias nuevas**: `urllib` viene con Python, mismo criterio que descartó `tkcalendar` y `pytest`.
- **14 pruebas nuevas** (`test_actualizaciones.py`), sobre la comparación de versiones y sin tocar la red. Existen por un error puntual: comparar versiones como texto hace que `"1.10.0" < "1.9.0"`, o sea que funcionaría perfecto durante nueve versiones y después dejaría de avisar para siempre, en silencio y en la máquina de otro. Se comparan como tuplas de enteros.

### 2026-07-26 — Instalable y actualizable: programa y datos en carpetas separadas
- **El pedido**: instalar la app en la computadora de la panadería (i5-6500T, 8 GB, Windows 64 bits, sin Python) y poder mandarle actualizaciones después **sin que se borre la base de datos**.
- **Lo que había**: `--onefile` y la base al lado del `.exe`, todo en una carpeta. Reemplazar el ejecutable ya respetaba los datos, pero la protección dependía de que quien actualiza no se equivocara nunca: alcanzaba con descomprimir "la carpeta nueva" encima para pisar el historial de ventas con una base vacía. Ese error no se deshace.
- **Ahora**: el programa vive en `%USERPROFILE%\Fermento\Programa\` y los datos en `%USERPROFILE%\Fermento\Datos\`, carpetas hermanas. Actualizar es borrar `Programa\` y descomprimir el ZIP nuevo. **El paquete no contiene ningún dato**, así que pisar la base dejó de ser posible por construcción, no por cuidado.
- **`--onedir` en vez de `--onefile`**: un solo `.exe` descomprime ~200 MB al `%TEMP%` en cada arranque; en esa máquina son varios segundos cada vez que abren la app. En modo carpeta arranca directo (~6,5 s en frío la primera vez, instantáneo después).
- **`--collect-data customtkinter`**: sin eso el `.exe` compila y revienta al abrir, porque customtkinter lee sus temas de archivos `.json` en runtime y PyInstaller no los ve siguiendo imports. Es exactamente el tipo de fallo que no aparece en la máquina de desarrollo.
- **`empaquetar.py`**: un comando arma todo (regenera el ícono, compila, copia logo e ícono, escribe un `LEEME.txt` para quien instala, comprime). El ZIP se nombra con la versión de `version.py`.
- **Versión visible en Ajustes**, junto a la ruta de la carpeta de datos y un botón para abrirla. Las dos cosas existen por lo mismo: la app corre en la panadería y quien la mantiene no está ahí. Un `.exe` viejo funciona igual de bien que uno nuevo, así que una actualización que no se instaló no da ninguna señal; y la ruta contesta "dónde están las ventas" para copiarlas a un USB.
- **Plan B si la carpeta no es escribible** (lo instalaron en `Program Files`): los datos van a `%LOCALAPPDATA%\Fermento\Datos`. Por eso Ajustes muestra **siempre** la ruta real — un fallback silencioso se vería desde el mostrador como "se borraron todas las ventas".
- **Ícono del ejecutable arreglado**: el `.ico` tenía tamaños (16,15), (32,29) y (48,44) — no cuadrados, y sin el de 256 que Windows usa en el escritorio, así que estiraba el de 48 y se veía borroso y deformado. Dos causas: el recorte del emblema no es cuadrado y Pillow respeta la relación de aspecto, y además no agranda (descartaba en silencio los tamaños mayores que la fuente). Ahora el emblema se centra en un lienzo cuadrado de 256 con 8% de aire, sobre el negro tomado del propio logo, y se guardan los 7 tamaños.
- **`icono_ventana()` ya no puede tumbar el arranque**: escribía el `.ico` sin `try`, y `main.py` la llama antes de que exista un widget capaz de mostrar un error. Con el programa en una carpeta de solo lectura, eso era una app que no abre y no dice por qué. Ahora se queda sin ícono y sigue.
- **Deduplicado**: `views/branding.py` tenía su propio `BASE_DIR` calcado del de `rutas.py`. Ahora usa `rutas.APP_DIR`, y la distinción entre "lo que se actualiza" (programa) y "lo que no se toca nunca" (datos) se lee de un solo lugar.
- **Manual para la panadería** (`Fermento - Manual de instalacion y uso.docx`, 11 páginas): instalar, actualizar, dónde viven los datos, para qué sirve cada pantalla y qué hacer si algo falla, en lenguaje sin tecnicismos. Va adentro del ZIP, no aparte.
- **Probado end-to-end**, incluido el ciclo completo de actualización sobre una instalación con ventas cargadas (ver la sección de empaquetado).

### 2026-07-26 — Se borró la demo: la base arranca en cero
- **Qué cambió**: se ejecutó `empezar_de_cero.py` sobre la base real. Las 301 ventas, 31 cortes, 707 líneas de detalle, 60 tandas, 10 productos, 8 insumos y 4 reglas de la demo ya no están. La app abre con las pantallas vacías y la primera venta que se registre va a ser la **#1**.
- **Por qué ahora**: los datos eran ficticios desde el 2026-07-21 y servían para revisar la app con las pantallas llenas. Esa etapa terminó: de acá en adelante lo que entre es plata real, y no puede venir mezclada con $130.605 que nunca existieron.
- **El respaldo**: `backups/ANTES-DE-BORRAR_2026-07-26_13-16-53_demo.db`, con todo adentro. El prefijo lo deja fuera de la rotación automática de 30 copias, así que no se va a perder solo con el tiempo.
- **Se verificó después de borrar**: las 9 tablas en cero, `sqlite_sequence` vacía (los contadores de id realmente reiniciados, no solo las filas borradas), y `init_db()` corriendo limpio sobre la base vacía con las claves foráneas encendidas — o sea, la app abre igual que siempre. Las 36 pruebas de `test_dinero.py` siguen pasando.
- **Qué falta para vender**: cargar los productos reales (Productos → + Agregar producto, con su costo si se quiere ver el margen), los insumos con sus mínimos (Inventario → + Agregar insumo) y **las reglas de descuento por antigüedad en Ajustes** — esas también se borraron, así que hasta que se carguen ninguna tanda vieja baja de precio sola.

### 2026-07-24 — Claves foráneas encendidas (la base se defiende sola)
- **Qué cambia para el usuario**: nada visible. Es una red de contención: a partir de ahora la base rechaza por sí sola una línea de venta que apunte a un producto que no existe, o el detalle de un corte ya borrado — aunque el código que lo genere tenga un error. Antes las declaraciones `REFERENCES` de las tablas estaban ahí pero no se aplicaban.
- **Por qué no era una línea**: SQLite trae las claves foráneas apagadas y el ajuste es **por conexión**, no del archivo. Pero encenderlas a secas dejaba la app **peor** que antes: `eliminar_lote()` borra la tanda físicamente, así que pasaría a fallar en cualquier tanda que tuviera una venta encima — o sea, casi siempre. Hacía falta primero cambiar esa clave a `ON DELETE SET NULL`, y SQLite no sabe modificar una clave foránea ya creada: la única vía es rehacer la tabla entera y copiar las filas.
- **Qué significa el cambio**: al borrar una tanda, sus líneas de venta quedan en NULL. Eso es exactamente lo que `anular_venta()` ya sabía interpretar desde antes: "no hay tanda a la que devolverle el stock", el mismo caso que las ventas anteriores al sistema de lotes. No se pierde información: la tanda borrada ya no existía de todos modos, y nada en la app cruzaba ese campo con la tabla de tandas.
- **Se limpiaron 612 referencias colgadas** que arrastraba la base, apuntando a tandas borradas hace rato.
- **Si la migración fallara, la app queda como antes y abre igual.** Es la decisión más importante del cambio: las claves foráneas se encienden solamente si la migración confirmó que la estructura las soporta. Un fallo deja todo funcionando como hoy y anota el error en el log, en vez de dejar la app a medio migrar o directamente sin abrir. Mismo criterio que el backup automático y el log: una mejora que no se pudo aplicar no puede impedir vender.
- **Verificado contra una copia de la base real**: las 707 líneas de venta sobreviven con las sumas de plata idénticas al centavo (subtotales, costos y precios de lista), los ids sin renumerar, el orden de las columnas igual, cero referencias colgadas y `PRAGMA integrity_check` en `ok`. Los números de Análisis no se movieron. Correr `init_db()` tres veces seguidas no rehace la tabla de nuevo. **La base de Alan no se tocó**: todo se probó sobre copias.
- **5 pruebas nuevas de comportamiento y 4 de la migración** (36 en total). Validadas por mutación con 9 formas de romper el código nuevo; las 9 fueron detectadas. Dos huecos aparecieron ahí: la prueba de la migración comparaba solo la suma de subtotales (una migración que pusiera los costos en cero pasaba), y la de idempotencia no distinguía "no se hizo nada" de "se rehizo al pedo". Un tercer caso hizo aparecer una mejora en el código: el interruptor de las claves foráneas ahora se apaga explícitamente al fallar, en vez de confiar en que ya estuviera apagado.

### 2026-07-24 — `empezar_de_cero.py`: borrar la demo para arrancar en serio
- **Por qué**: la base tiene datos ficticios desde el 2026-07-21 y no había una forma prolija de sacarlos. Hacerlo a mano (borrar el archivo, o tirar `DELETE` sueltos) deja los contadores de id donde estaban, así que la primera venta real quedaría numerada #302 — y si mañana se agrega una tabla, una lista escrita a mano de qué borrar la dejaría afuera en silencio.
- **Qué hace**: muestra qué hay adentro y cuánto se facturó, pide escribir `BORRAR`, guarda un respaldo fuera de la rotación automática, vacía todas las tablas (leídas de la base misma, no de una lista fija), reinicia los contadores de id, compacta el archivo y **verifica que no haya quedado ni una fila** antes de decir que salió bien.
- **No se puede saltear la confirmación**: no hay flag para correrlo sin preguntar. Se usa una vez en la vida y el error no se deshace desde la app.
- **No vive en Ajustes a propósito**: un botón de "borrar todo el historial" permanente en la pantalla de una panadería es un peligro sin ninguna ventaja. Es una operación de una sola vez, va en un script aparte.
- **Vacía también el catálogo** (decisión de Alan): los 10 productos, 8 insumos y 4 reglas de la demo son plausibles pero no son sus precios reales, así que arranca de cero y carga los suyos.
- **Probado sobre copias, nunca sobre la base real**: cancelar deja las 301 ventas intactas; confirmar deja las 9 tablas vacías con la estructura completa (12 columnas en `detalle_venta`) y el archivo compactado de 100 KB a 48 KB; el respaldo pasa `PRAGMA integrity_check` con sus 301 ventas y no lo agarra la rotación; sobre la base ya vaciada, un alta de producto + venta + corte numeran 1, 1 y 1. También se probó correrlo dos veces y contra una ruta inexistente. **La base de Alan quedó sin tocar** (mismo hash antes y después).

### 2026-07-24 — Pruebas automáticas de las cuentas (`test_dinero.py`)
- **El problema**: el resto de la app se prueba usándola — si un botón no anda, se ve. Pero un error de un peso en un corte no se ve mirando la pantalla: se descubre meses después, cuando ya no hay con qué reconstruir qué pasó. Justo las cuentas donde un error es caro son las que menos se notan.
- **Qué hay ahora**: 26 pruebas que corren en 2 segundos con `python -m unittest test_dinero`. Sin instalar nada (`unittest` viene con Python; se prefirió a pytest por lo mismo que se descartó `tkcalendar` — no sumar dependencias por algo que la biblioteca estándar ya resuelve).
- **Nunca tocan la base real**: cada prueba arranca con una base temporal y vacía que se borra al terminar. Es lo primero que hace `_BaseDinero` y lo más importante del archivo — sin eso, las pruebas escribirían ventas y cortes inventados en `panaderia.db`.
- **Qué se verifica**: el total de una venta = la suma de sus líneas; que vender de más no deje nada a medias (la primera línea entra, la segunda no alcanza, y no puede quedar una venta cobrada con stock descontado); que anular devuelva exactamente lo vendido, **a la tanda correcta**, y que anular dos veces no lo devuelva dos veces; que no se pueda anular una venta ya cortada ni que ese rechazo deje efectos parciales; que un corte sume exactamente lo pendiente, ignore anuladas, y que un segundo corte no vuelva a contar lo del primero; que el desglose por producto sume el total del corte; que deshacer reabra las ventas sin devolver stock; que cambiar precio o costo no mueva nada ya vendido (ni antes ni después de cortar); que lo rematado salga de la resta del par y no del total (**el error que ya pasó una vez con la base real y dio $-5.452**); y los escalones del descuento por antigüedad, incluido que las reglas propias de un producto reemplacen a las generales en vez de mezclarse.
- **Se verificó que las pruebas realmente muerdan**: una prueba que pasa a la primera no demuestra nada. Se rompió `database.py` a propósito de 17 maneras distintas, una por vez (sacar la guarda de venta ya anulada, devolver el stock al lote equivocado, que el corte deje de filtrar por pendientes, sacar la protección de stock del UPDATE, quitar el rollback, leer el costo al cortar en vez de usar el congelado, calcular lo rematado con la resta vieja…) y **las 17 fueron detectadas**. Las tres que en la primera vuelta se escaparon dieron lugar a tres pruebas nuevas.
- **Lo que NO cubren**: la interfaz. No se abre ninguna ventana. Las pantallas se siguen probando usándolas.

### 2026-07-22 — Registro de errores a archivo
- **El problema**: el `.exe` se genera con `--windowed`, o sea **sin consola**. Cualquier error que se escapara de un `try` desaparecía sin dejar rastro: Python y Tkinter escriben el traceback en stderr y ahí no lo ve nadie. Desde el mostrador el síntoma era "apreté el botón y no hizo nada" o "se cerró sola", sin nada con qué diagnosticar después.
- **Qué hay ahora**: un archivo `panaderia_error.log` al lado de la base de datos, con fecha, hora y el traceback completo de cada error. Rota al llegar a 1 MB y conserva 3 archivos viejos, así no crece sin techo en años de uso pero tampoco se borra entero justo cuando hacía falta lo de ayer.
- **Tres enganches distintos**, porque un error se puede escapar por tres lados y ninguno cubre a los otros: los callbacks de la interfaz (botones, atajos de teclado, temporizadores) que es por donde se escapa casi todo; el hilo principal, sobre todo si algo falla **armando** la ventana, antes de que exista un solo widget que pueda avisar; y otros hilos, como seguro barato.
- **Los errores de base de datos también quedan anotados**, en el único punto por donde pasan todos. El usuario sigue viendo el mismo mensaje corto y entendible de siempre, pero ahora además queda el detalle técnico que ese mensaje descarta.
- **Y ahora la app avisa**: cuando algo falla en la interfaz aparece un cartel que dice que la acción no se completó y en qué archivo quedó registrado. Antes el click simplemente no hacía nada y parecía que la app se había colgado.
- **No poder escribir el log nunca rompe la app**: si la carpeta es de solo lectura o el disco está lleno, la falla se ignora y todo sigue funcionando. Es preferible una app que anda sin log que una que no abre por culpa del log.
- **Dos módulos nuevos**: `registro.py` (el log) y `rutas.py` (la carpeta donde la app escribe, que antes vivía dentro de `database.py`). El segundo existe para que el log no pueda terminar en una carpeta distinta de la base de datos. No hace falta tocar nada del empaquetado: PyInstaller los detecta solo.
- **Verificado**: un error dentro de un botón, un error de SQLite y un error del hilo principal quedan los tres en el archivo con su traceback; llamar varias veces al arranque no duplica líneas; con una ruta de log imposible ni el arranque ni el registro revientan y no se crea ningún archivo; las seis secciones siguen cargando sin excepciones.

### 2026-07-22 — Inventario: barra visual con el consumo del día
- **Qué se ve**: cada insumo tiene ahora una barra en su fila, bajo la columna **«Hoy»**. La parte llena es el stock actual, el tramo tenue que sigue es con cuánto arrancó el día (el "rastro" de lo que se consumió horneando), y la línea roja es el mínimo configurado. Con una leyenda arriba del listado que lo explica.
- **Una barra por fila y no un gráfico único**, a propósito: los insumos no son comparables entre sí (145 kg de harina contra 3,2 kg de levadura, más litros de leche). En un eje compartido la levadura sería una raya de dos píxeles, justo el insumo que suele estar bajo el mínimo. Cada barra se escala contra su propio máximo, así todas se leen igual de bien y los kg no se mezclan con los litros.
- **De dónde sale la sombra**: hasta ahora la base guardaba solo el stock actual y cada ajuste lo pisaba, así que no había ningún rastro del valor anterior. Se agregaron dos datos al insumo: con cuánto arrancó el día y de qué día es esa marca. **La marca se renueva en el primer ajuste de cada día**: si a las 6 se baja de 20 a 15 y a las 9 de 15 a 12, la sombra dice 20 las dos veces, no 15. Se eligió esto por sobre guardar simplemente "el valor anterior", que solo recuerda un paso atrás y perdería el punto de partida real de la jornada.
- **Sin movimiento de hoy, sin sombra**: la marca se renueva al tocar el insumo, no por reloj a medianoche. Si la harina no se movió en tres días, su marca es de aquel día y mostrarla sería hacerla pasar por la de hoy; en ese caso la barra va sólida y listo. La sombra aparece solo los días en que ese insumo efectivamente se usó.
- **Reposición**: si el stock SUBE, la sombra queda tapada por el relleno, así que se marca el arranque del día con una línea gris -- "se repuso" no se puede ver igual que "no se movió".
- **La línea del mínimo no costó nada**: `stock_minimo` ya existía (es la que alimenta el aviso amarillo de stock bajo desde antes).
- **Limitación conocida**: "el día" corta a las 00:00. Horneando de madrugada no molesta, pero una jornada que cruce la medianoche parte la sombra en dos. Si llega a pasar, se arregla definiendo que el día arranca a una hora fija.
- **Se descartó por ahora una tabla de movimientos** (registrar cada ajuste): para este gráfico da exactamente lo mismo y es bastante más trabajo. Sigue siendo lo que va a necesitar el descuento automático de insumos por receta; si eso se encara, conviene rehacer la sombra sobre esa tabla.
- **Verificado**: tres ajustes en la misma jornada mantienen la marca en el valor de arranque; el primer ajuste de un día nuevo la reemplaza; un insumo sin movimientos de hoy no dibuja sombra; la reposición dibuja la línea de marca; un insumo en 0 y sin mínimo no dibuja nada en vez de una barra vacía; geometría de la barra revisada caso por caso (levadura bajo mínimo termina antes de la línea roja, harina sana la pasa holgada); las seis secciones cargan sin excepciones.

### 2026-07-21 — Elegir fechas sin teclado: calendario y atajos
- **Calendario en el filtro de fechas**: cada campo (Desde y Hasta) tiene ahora un botón **"▾"** que abre un calendario del mes -- `‹ Julio 2026 ›` con la grilla de días arrancando el lunes, más un botón "Hoy". Sirve en **Historial y en Análisis**, porque la barra de filtro es un widget compartido. Se puede seguir tipeando a mano; el calendario es una opción más, no un reemplazo.
- **El calendario escribe la fecha en el campo, pero no filtra**. El filtro se aplica con "Filtrar", igual que cuando se tipea. Es a propósito: si al elegir "Desde" ya filtrara, el "Hasta" se elegiría sobre una lista a medio filtrar.
- **Detalles visuales**: el día que ya estaba cargado en el campo se resalta en dorado lleno; el día de hoy va solo con el número en dorado, para ubicarse sin competir con el elegido. El calendario abre en el mes de la fecha que el campo ya tuviera (o el actual si está vacío) y se posiciona debajo del botón, no centrado en la pantalla.
- **Por qué no `tkcalendar`** (la librería típica para esto): suma una dependencia que hay que empaquetar en el `.exe`, y su estilo es el de ttk (fondo claro), que desentonaría con el modo oscuro de Fermento. El calendario está hecho con customtkinter, así que respeta el tema. Los meses y días están en castellano fijos, sin depender del idioma de la PC.
- **Atajos de rango en Historial → Ventas**: botones **Hoy / Esta semana / Este mes**, como los que Análisis ya tenía. Cubren las preguntas que uno se hace de verdad al abrir el historial sin tocar fechas. "Esta semana" arranca el lunes; "Esta semana" y "Este mes" dejan el "Hasta" abierto (el rango es "desde tal día hasta ahora"). El atajo aplicado queda en dorado y se apaga solo si después se filtra o limpia a mano.
- **Sin duplicar**: los atajos salieron a un widget compartido (`widgets.BotonesPreset`) que ahora usan Historial y Análisis. Los atajos son distintos en cada pantalla (Análisis filtra por corte, Historial por día); lo compartido es el mecanismo y el resaltado, no la lista. Un atajo que no puede calcular su rango (falla la BD, no hay cortes todavía) avisa y **no** queda seleccionado, porque no estaría representando nada.
- **Verificado**: aritmética de meses cruzando años (−7 → Diciembre 2025, +18 → Julio 2027); grilla de julio 2026 con sus 31 días; elegir un día escribe `10-07-2026` en el campo sin mover la lista, y recién "Filtrar" aplica; los tres atajos de Historial dan los rangos correctos (Hoy = 22-07-2026 a 22-07-2026, Semana = lunes 20-07-2026); solo un atajo queda dorado por vez; filtrar o limpiar a mano lo apaga; Análisis mantiene exactamente el comportamiento que tenía; las seis secciones cargan sin excepciones.

### 2026-07-21 — Paginación de listas largas (Ventas de a 50, Cortes de a 30)
- **Síntoma**: entrar a Historial tardaba un momento perceptible. No es la base de datos -- SQLite devuelve las 301 ventas de la demo en 0.35 ms. El costo estaba en dibujar todas las filas de una: cada fila son ~5 widgets de customtkinter y CTk es lento creándolos.
- **Medido (headless, en máquina real es menos)**: dibujar las 301 tardaba ~6,3 s; dibujar solo 50 lo bajó a ~1,4 s. Y el problema crecía sin techo -- 301 ventas en un mes de demo son ~3.600 al año.
- **Qué cambió**: las listas largas se paginan, con una barra al fondo "‹ Anterior · Página X de Y · Siguiente ›". Nunca se dibujan más filas que el tamaño de página, así que entrar a la pantalla cuesta lo mismo tenga la base 300 filas o 30.000.
  - **Historial → Ventas: de a 50**, con y sin filtro. (Primero se probó como "solo las últimas 50 sin filtro", pero un tope no deja llegar a las ventas viejas -- la paginación sí, y de paso acota también los rangos filtrados grandes.)
  - **Historial → Cortes: de a 30**. El tamaño sale de que un corte es aproximadamente diario, así que ~30 cortes ≈ un mes: cada página es "el mes".
- **Sin duplicar código**: la barra es un widget compartido, `widgets.Paginador`, no una copia en cada pantalla. La pantalla le pasa la lista completa y recibe el tramo de la página; el widget solo guarda el número de página, no los datos.
- **Detalles de comportamiento**: las páginas van de lo más reciente a lo más antiguo; la página se reencaja sola si queda fuera de rango (p. ej. filtrar estando en la página 4 de un resultado que ahora tiene 1); aplicar un filtro vuelve a la página 1 (Ventas); hacer un corte vuelve a la página 1, donde aparece el nuevo (Cortes); la barra no aparece con una sola página; al cambiar de página el scroll vuelve arriba; las flechas de los extremos quedan deshabilitadas. En Cortes, el botón "Deshacer" (solo en el último corte) se decide sobre la lista completa, no sobre la página, así que nunca aparece de más en una página que no sea la primera.
- **Cero cambios en la base**: es solo cuántas filas se pintan por vez.
- **Verificado**: Ventas 301 → 7 páginas (la 7 con 1 fila, 301 = 6×50 + 1); Cortes 31 → 2 páginas (Deshacer visible en la 1, ausente en la 2); flechas de los extremos deshabilitadas; página fuera de rango se reencaja; filtrar resetea a la 1; filtro de un día (13 ventas) sin barra; las seis secciones de la app cargan sin excepciones.

### 2026-07-21 — Segunda tanda de simplificación (parte interna: deduplicación)
- Tres pedazos de código escritos dos veces, en archivos distintos. **Nada cambia en pantalla**; lo que cambia es que un arreglo futuro se hace en un solo lugar en vez de dos (y no queda una copia con el bug).
- **`_a_iso()` → `formato.a_iso()`**: la conversión DD-MM-AAAA → ISO estaba idéntica en `graficos.py` (función de módulo) e `historial.py` (staticmethod). Ahora vive al lado de `formato.fecha()`, que hace exactamente la conversión inversa -- la ida y la vuelta estaban en archivos distintos.
- **`_DetalleDialog` y `_AnularDialog` usan `dialogos.centrar_sobre()`**, como el resto de los diálogos de la app. Centraban a mano con las mismas 4 líneas porque son anteriores a que se extrajera el helper. Se verificó que la geometría resultante es idéntica a la de la fórmula vieja (misma posición y tamaño, comparadas lado a lado).
- **Nuevo `views/widgets.py` con `FiltroFechas`**: el bloque "Desde/Hasta/Filtrar/Limpiar" estaba duplicado entre Análisis e Historial → Ventas -- los cuatro widgets, la validación y los dos mensajes de error, ~50 líneas cada uno. El módulo es nuevo y no se metió en `dialogos.py` a propósito: ese archivo es para ventanas `CTkToplevel` y esto es un control de pantalla.
- **Los dos callbacks de `FiltroFechas`** son el único punto con diseño de por medio: las dos pantallas no son simétricas. `on_cambio` corre siempre; `on_manual` solo si el usuario tocó Filtrar/Limpiar. Análisis lo necesita porque filtrar a mano tiene que apagar el preset resaltado en dorado -- pero si `set_rango()` (que usan los presets para aplicarse) disparara el mismo callback, **un preset se apagaría a sí mismo al aplicarse**. Historial no lo pasa: no tiene presets.
- **Verificado**: preset → queda en dorado y refleja la fecha en el campo; filtrar a mano tras un preset → lo apaga; Limpiar → borra rango, campos y preset; fecha inválida y "Desde > Hasta" → muestran su error y NO notifican el cambio; un solo extremo cargado sigue siendo válido. Más el recorrido de las seis secciones de la app sin excepciones.

### 2026-07-21 — Segunda tanda de simplificación (parte UX)
- Continuación de la tanda del 2026-07-20, con el mismo criterio: **mover funciones detrás de donde se necesitan, no quitarlas**. Se aplicaron los tres puntos de interfaz de la auditoría; los tres de deduplicación interna (`_a_iso()`, centrado de diálogos, bloque de filtro de fechas) quedan pendientes y no cambian nada visible.
- **Nueva Venta: los agotados van al fondo, agrupados bajo un rótulo tenue "AGOTADOS"**. Antes se dibujaba una tarjeta "Sin stock" en el orden del catálogo, así que a media tarde quedaban *entre* el vendedor y lo que sí podía vender. Se descartó ocultarlos del todo: saber qué se terminó sirve para avisarle al cliente. El "Sin stock" pasó de rojo (`DANGER`) a gris (`TEXT_DISABLED`) -- agotado al final del día es lo normal, no un error. `refresh()` parte la lista en `con_stock`/`agotados` y el dibujo de una tarjeta se extrajo a `_tarjeta_producto()`.
- **Nueva Venta tiene buscador**; era la pantalla que no lo tenía y la que más lo necesita (se vende decenas de veces por día; el catálogo se edita una vez por semana). Es el mismo patrón que Productos: `StringVar` + `trace_add` → `refresh()`, filtrando en memoria la lista ya traída, sin consultar la BD por cada letra.
- **Cortes: fuera los modales de éxito** de "hacer corte" y "deshacer corte". No informaban nada que la pantalla no muestre sola (el corte nuevo aparece primero en la lista y los pendientes vuelven a cero; al deshacer pasa lo inverso). Es el mismo modal que se sacó del flujo de venta el 2026-07-20 y había quedado acá. **La confirmación previa se mantiene en los dos**: ahí sí hay información que no está en pantalla (el desglose por producto) y las dos acciones son contables.

### 2026-07-21 — Margen en $ y en %, y aviso cuando el margen es parcial
- **El pedido** (del 2026-07-11) era hacer el margen "más práctico para ver cómo va el negocio". De las cinco ideas anotadas se implementaron las tres que entran en la franja y los gráficos que ya existen; las otras dos (tendencia de margen en el tiempo, costo desglosado en el ranking) siguen pendientes porque implican una serie o un panel nuevo, y la restricción del usuario es que Análisis siga simple.
- **Margen del período en $ y en %**: la tarjeta "Margen real" ahora dice `$72.627 (57%)`, mismo formato que "Rematado". Uno solo de los dos se malinterpreta: un mes con más margen en $ puede tener peor margen en % (vendió más, ganó peor por peso vendido). El % es sobre lo vendido en el rango (`margen / total`), no sobre el costo.
- **Margen % por producto en el ranking**, dentro de la etiqueta de cada barra (`$11.565 (64%)`) en vez de una quinta métrica del toggle. Dos razones: (1) el toggle ya está al límite de ancho -- con cuatro botones consume 614px de los 735px disponibles a la ventana mínima, y un quinto no entraba; (2) las dos cosas se quieren ver juntas, no una o la otra: la barra ordena por plata (que es lo que se compara entre productos) y el % dice si ese monto es eficiente o solo grande. El eje lleva la aclaración de qué mide el %. El pad del `xlim` sube de 0.18 a 0.28 solo en esta métrica porque la etiqueta trae dos valores y con el pad del resto se salía del área.
- **Aviso de margen optimista**: si en el rango hay ventas de productos sin costo cargado, la nota al pie de la franja dice cuánto es en plata, qué porcentaje del total representa y qué productos son (hasta 3, después "…"). El margen de arriba trata el costo faltante como $0, o sea que **queda alto**, y hasta ahora nada lo avisaba -- solo caía a "sin datos" en el caso extremo de que NINGÚN producto tuviera costo. Mismo espíritu que el aviso de stock bajo en Inventario: el dato que hace falta para saber si conviene confiar en el número antes de decidir algo del negocio.
- **`get_resumen_analisis()` devuelve `sin_costo_total` / `sin_costo_nombres`** desde una segunda consulta sobre `corte_detalle` (las líneas con `costo_total <= 0`). Se mide en plata y no en cantidad de productos: lo que ensucia el margen es cuánto facturaron esas líneas, no cuántas son. La condición de fecha se arma con un helper `_cond(col)` porque la segunda consulta hace JOIN y necesita `co.fecha` calificada.
- **Por qué el % agregado se calcula sobre TODO lo vendido y no solo sobre la porción con costo**: la alternativa (más honesta en aislamiento) dejaría el $ y el % medidos sobre bases distintas, ilegibles juntos en la misma tarjeta. Se prefirió mantenerlos coherentes y avisar el hueco por separado. En el ranking, en cambio, el % es `None` para los productos sin costo y no se dibuja -- ahí sí hay una fila entera sin dato, no una mezcla.

### 2026-07-21 — Ranking: métrica "% pleno" (qué producto se remata más)
- Cuarto botón del toggle del ranking. Responde el **"quién"**: el remate total decía cuánto se resignaba, pero no qué producto lo causaba. `pleno_pct = lista_cobrado / lista_total * 100` -- de cada $100 de precio de lista, cuánto entró. 100% = ese producto nunca se remató.
- **Se mide en plata, no en unidades**, aunque "% a precio pleno" suene a contar piezas: rematar dos facturas caras pesa más que rematar dos bolillos, y lo que interesa es cuánto cuesta el sobrante. Sale de `corte_detalle.lista_total`/`lista_cobrado`, que ya se guardaban desde el cambio anterior -- no hizo falta tocar el esquema.
- **Es la única métrica que ordena de MENOR a mayor, y no es un capricho**: con el orden descendente de las otras tres, un "top 10" mostraría los productos que nunca se rematan y **escondería justamente los que hay que dejar de hornear de más**. Con la métrica invertida, el problema queda arriba de todo.
- Línea de referencia vertical en 100% (verde, punteada): sin ella, un gráfico donde todos rondan el 90% se ve igual de dramático que uno donde rondan el 40%, porque el eje se autoescala a los datos.
- Los productos sin ninguna venta con precio de lista se **excluyen** en vez de dibujarles un 100% falso -- mismo criterio que los sin costo en "Margen ($)". Si no queda ninguno, un mensaje lo explica en vez de un gráfico vacío.
- **El título del ranking ahora cambia con la métrica** ("El más vendido" / "El que más facturó" / "El de más margen" / "Lo que más se remata"). Era fijo en "Producto más vendido" y ya mentía al elegir "Margen ($)".
- Las etiquetas del toggle se acortaron ("Monto ($)" → "Monto", "Margen ($)" → "Margen"): con cuatro botones, el toggle más el título necesitaban 781px contra 735px disponibles a la ventana mínima (820x560) y el cuarto botón quedaba cortado. Medido, no estimado; ahora el peor caso son 614px. El "$" no se pierde: está en el eje y en las etiquetas de cada barra.


### 2026-07-20 — Segunda línea en "Total vendido por corte": el hueco es el remate
- El gráfico de cortes ahora dibuja **dos series**: "Cobrado" (la de siempre, dorada, con marcadores) y "Si nada se remataba" (punteada, naranja, sin marcadores). El área naranja entre ambas es lo que se resignó por vender pan viejo, corte por corte. La franja de arriba ya daba el total del período; esto muestra **en qué cortes se concentra**.
- La serie de referencia se calcula como `total_ventas - lista_cobrado + lista_total`, **no** como `lista_total` a secas: ese campo solo cubre las líneas que tienen precio de lista guardado, así que usarlo tal cual dibujaría una línea muy por debajo de la real en cualquier corte parcialmente cubierto. La fórmula reemplaza la parte con dato por su valor de lista y deja el resto como está.
- **Un corte sin el dato queda en `NaN` y matplotlib corta la línea ahí.** Se eligió el hueco por encima de dibujar las dos series pegadas, que se leería como "ese día no se remató nada" -- que es justamente lo que no se sabe. Los cortes anteriores a esta versión aparecen así.
- La leyenda solo aparece cuando hay dos series (con una sola sería ruido) y usa `loc="best"`: con `"upper left"` fijo se montaba encima de la curva cuando el pico cae temprano en el rango. Va estilada a mano para el modo oscuro, como el resto de los gráficos.
- La línea punteada va en `zorder` menor que la real y sin marcadores a propósito: es una referencia, no una serie que se mire por su propio valor. El naranja es el mismo del número "Rematado" de la franja, para que se lean como lo mismo.


### 2026-07-20 — Análisis: cuánto se resigna rematando pan viejo
- **El problema**: el ranking de Análisis se arma sobre `corte_detalle`, que guardaba solo nombre / cantidad / total / costo_total. Con precios que bajan solos por antigüedad, eso significaba que "$800 de pan francés" podía ser pan fresco a precio pleno o pan de tres días liquidado, **y era exactamente la misma barra**. El "Margen ($)" que ya existía nunca estuvo mal (usa el precio efectivamente cobrado), pero no respondía cuánto se dejó de ganar ni qué productos se rematan siempre.
- **No se podía calcular hacia atrás**, y por eso hizo falta tocar la BD: `productos.precio` cambia con el tiempo y `eliminar_lote()` borra la fila físicamente, así que ni el precio de lista ni la antigüedad de una venta pasada son reconstruibles. `registrar_venta()` ahora congela `precio_lista`, `lista_subtotal` y `dias_antiguedad` en `detalle_venta`, mismo criterio que ya se usaba con `costo_unitario`. **Los números existen desde esta versión en adelante**; lo anterior queda como "sin datos", nunca como "descuento cero".
- **Franja de tres números arriba de los gráficos** (`GraficosPanel._actualizar_kpis`): Vendido · Rematado por antigüedad · Margen real. Se eligió texto y no un cuarto gráfico a propósito: son números que se leen de un vistazo, no series. Cada uno cae a "sin datos" en gris si le falta el insumo, y una nota al pie aclara sobre cuántos cortes se calculó el remate; si no hay nada que aclarar, la nota no ocupa lugar (`_mostrar_nota()` hace `pack_forget`).
- **`lista_total` y `lista_cobrado` van siempre de a pares**, y esto es lo importante de la decisión: ambos suman EXACTAMENTE las mismas líneas (las que tienen precio de lista guardado), y el remate es su resta. La primera versión guardaba solo `lista_total` y le restaba `total_ventas` del corte -- una prueba con la BD real lo dejó en evidencia enseguida: el corte de la transición mezcla ventas con y sin el dato, y el resultado salía **negativo ($-5.452, -605%)**. Cualquier corte mezclado (o una venta sin lote asociado) reproduce el bug, así que no era solo un problema de la migración.
- El desglose por producto de `corte_detalle` guarda los mismos dos campos aunque todavía no se muestren: es el insumo de la métrica "% a precio pleno" por producto, que quedó planteada y sin hacer (ver Pendiente en `CLAUDE.md`).

### 2026-07-20 — "Tanda de hoy" / "Tanda anterior" en vez de "hace 0 día(s)"
- `formato.edad_tanda()` traduce la antigüedad de una tanda a las palabras del mostrador: día 0 → "Tanda de hoy", día 1 → "Tanda anterior", de ahí en adelante → "hace N días". Los dos primeros escalones son los que se distinguen de un vistazo al vender; del día 2 en adelante lo que importa es el número.
- "hace 0 día(s)" era técnicamente cierto y se leía mal justo en el caso más frecuente (el pan del día). Se aplica en los cuatro lugares donde aparecía: las tandas de Nueva Venta, las de la fila de Productos, el aviso de descuentos activos y el diálogo de tandas.
- Con `dias=None` (tanda sin fecha de horneado) devuelve `None` en vez de inventar una antigüedad; el llamador muestra "sin fecha".


### 2026-07-20 — Vocabulario: "Lotes" → "Tandas" en pantalla
- "Lote" es la palabra del modelo de datos, no la del mostrador. En pantalla ahora se dice **siempre "tanda"**. Cambió el título y el encabezado del diálogo (`Tandas — Pan francés`), el botón de la fila de Productos ("+ Tanda"), el aviso de descuentos activos ("⚠ Tandas con descuento por antigüedad activo hoy"), la confirmación de baja ("¿Dar de baja esta tanda entera?"), el formulario de alta ("Tanda nueva -- unidades:" / "Registrar tanda nueva") y los dos avisos de stock insuficiente de Nueva Venta ("...en esta tanda").
- **La palabra la eligió el usuario, en dos pasos**: primero se aplicó "hornada" (la palabra técnica del oficio) y Alan, al verla en pantalla, propuso **"tanda"** -- más corta, más natural en su habla ("tanda nueva", "tanda anterior") y sin la connotación de que necesariamente salió de un horno. El renombre completo se rehizo en una sola pasada. Que el primer intento haya costado 10 minutos deshacerlo es consecuencia directa de haberlo mantenido acotado a cadenas visibles.
- **La base de datos no se tocó**: la tabla sigue siendo `lotes`, la columna `detalle_venta.lote_id`, y las funciones `agregar_lote()` / `corregir_stock_lote()` / `eliminar_lote()` / `get_lotes_todos()` conservan su nombre. Renombrar el modelo obligaría a una migración de esquema por un cambio puramente cosmético, con riesgo real (datos en producción) a cambio de cero beneficio para el usuario. La frontera quedó anotada en el docstring de `_DialogoLotes`: **texto visible en tandas, identificadores en lotes**.
- El alcance fueron **cadenas visibles en 3 archivos** (`views/productos.py`, `views/nueva_venta.py`, `views/ajustes.py`); `database.py` no necesitó ni un cambio porque ninguno de sus mensajes de error nombra al lote. El único identificador que se tocó fue el método `_DialogoLotes._agregar_hornada()` → `_agregar_lote()`, justamente para respetar la frontera.
- Se reescribió también el texto de ayuda del diálogo, que decía "Cada hornada es un lote aparte" -- una frase que solo tenía sentido explicando el modelo interno. Ahora dice "Cada tanda se lleva su propia antigüedad y su propio precio", que es lo que al usuario le importa.

### 2026-07-20 — Barra lateral agrupada en dos bloques
- La barra lateral era una lista plana de cinco botones idénticos, sin jerarquía: nada indicaba que "Nueva venta" e "Historial" son cosas de momentos distintos de la jornada. Ahora van en dos bloques con rótulo: **DÍA A DÍA** (Nueva venta, Productos, Inventario -- lo que se toca con el local abierto) y **REVISAR** (Historial, Análisis -- lo que se consulta después, cerrando caja o viendo cómo viene el mes). "⚙ Ajustes" sigue anclado abajo, como tercer bloque implícito.
- Los rótulos son deliberadamente tenues (`theme.TEXT_DISABLED`, 10px, bold): están para agrupar, no para competir con los botones. **Sin línea divisoria** -- el espacio en blanco más el rótulo ya separan los bloques, y una línea sobre la marca de agua del emblema agregaría ruido justo donde se buscó textura sutil.
- Ninguna función se movió de lugar ni cambió de nombre: es solo jerarquía visual. El espacio bajo el logo bajó de 28 a 16px para compensar la altura de los rótulos; verificado que el sidebar completo entra en la ventana mínima (435px de contenido contra 560px de alto mínimo).

### 2026-07-20 — Sección Ajustes (configuración separada del uso diario)
- Nueva pantalla **Ajustes** (`views/ajustes.py`), con su botón "⚙ Ajustes" anclado **abajo del todo** en la barra lateral (`side="bottom"`), separado de las cinco secciones operativas: es configuración que se toca una vez cada varios meses y no debe sumarse a la lista que el ojo recorre buscando una pantalla de uso diario.
- **"Reglas de descuento" se fue del header de Productos** a esa pantalla. Estaba al lado de "+ Agregar producto", que se usa muchísimo más seguido -- dos cosas de frecuencia muy distinta compitiendo por la misma atención. El diálogo `_DialogoReglas` se movió tal cual de `views/productos.py` a `views/ajustes.py` (sin cambios de comportamiento).
- Ajustes no es solo un contenedor de botones: muestra un **resumen en vivo** de cómo están las reglas hoy (los escalones generales día→%, y qué productos tienen reglas propias que reemplazan a las generales). La mayoría de las veces que uno entra a Ajustes es a verificar cómo quedó algo, no a cambiarlo -- así se resuelve sin abrir ningún diálogo.
- `_centrar_sobre()` estaba duplicada literal en `views/productos.py` y `views/inventario.py`; al necesitarla una tercera pantalla se movió a **`views/dialogos.py`** (`centrar_sobre`) y los tres archivos la importan de ahí, en vez de hacer una copia más.

### 2026-07-20 — Productos: una acción por fila
- Cada fila de producto activo mostraba **Editar / Lotes / Eliminar**. Con 15 productos eso son 45 botones en pantalla para cubrir un uso que el 90% de las veces es el mismo: registrar la hornada del día. Ahora la fila muestra **un solo botón visible, "+ Hornada"**, más un **"⋯"** que despliega las acciones esporádicas (Editar producto…, Eliminar producto). De 3 botones por fila a 2, y con jerarquía clara entre lo diario y lo ocasional.
- El botón dice **"+ Tanda"** y no "Lotes": nombra la acción concreta en vez del concepto del modelo de datos, con la palabra que ya usa el panadero (y que de hecho ya aparecía en los textos del propio diálogo). El renombre completo de "Lotes" → "Hornadas" en el resto de la UI sigue pendiente.
- El menú "⋯" usa `tk.Menu` nativo (CustomTkinter no trae menú contextual) estilado a mano con `bg`/`fg`/`activebackground`/`activeforeground`/`bd=0`, para que no aparezca el bloque gris claro de Windows encima del modo oscuro. Se despliega pegado al borde inferior izquierdo del botón, no bajo el mouse.
- El ancho de la columna "Acciones" del encabezado bajó de 230 a 150 para acompañar. Las filas de productos inactivos siguen con su único botón "Reactivar" (ya eran de una sola acción).

### 2026-07-20 — Simplificación del flujo de venta (menos clicks, sin modales)
- Diagnóstico: la app había crecido por acumulación (cada función nueva se agregó *al lado* de las anteriores, nunca *detrás*). Una venta típica de 3 productos costaba **8 clicks y 2 diálogos modales**. Esta tanda ataca solo el flujo de venta, que es el 90% del uso diario; el resto de las simplificaciones quedó anotado en Pendiente.
- **La app arranca en Nueva Venta**, no en Productos (`main.py`): vender se hace decenas de veces al día y el catálogo se toca una vez por semana. Abrir en Productos costaba un click en cada venta. El botón "Nueva venta" se movió también al tope de la barra lateral, para que el orden del menú refleje la frecuencia de uso real y no el orden en que se fueron creando las pantallas.
- **Se quitó la confirmación "¿Registrar venta por $X?"**: el carrito completo y el total están a la vista justo al lado del botón "Confirmar venta", así que el diálogo no aportaba información nueva -- solo un click más en la acción más repetida del día. La red de seguridad sigue existiendo: una venta mal registrada se anula desde Historial y devuelve el stock al lote correcto.
- **El diálogo "Venta registrada / ¿generar ticket?" pasó a ser un aviso dentro de la pantalla** (franja verde arriba del pie del carrito: "✓ Venta #N registrada — $X" + botón "Ticket" + "✕"). Un modal por venta obliga a soltar el mouse y confirmar mientras hay gente esperando; el aviso no bloquea nada y permite empezar a cargar la venta siguiente de inmediato. Se oculta solo a los 12s (alcanza para decidir si el cliente quiere ticket, y evita que quede un aviso viejo colgado sobre la venta siguiente) o al generar el ticket (para que no invite a generarlo dos veces). El ticket sigue sin generarse automáticamente: no todos los clientes lo quieren.
- Resultado: la misma venta de 3 productos pasa de 8 clicks y 2 modales a **4 clicks y ningún modal**.

### 2026-07-12 — Ticket de venta en PDF (impresora convencional)
- Nuevo `views/ticket.py`: genera el ticket de una venta como **PDF en hoja A4** (blanco y negro, columna centrada estilo recibo: encabezado FERMENTO, N° de ticket, fecha, tabla de productos, total, "Comprobante sin valor fiscal") y lo abre con el visor de PDF predeterminado de Windows -- desde ahí se imprime en cualquier impresora convencional, o no se imprime si el cliente no quería papel. Se eligió PDF + vista previa (y no impresión directa silenciosa vía pywin32) por confiabilidad en cualquier impresora, porque da vista previa/elección de impresora, y porque el PDF queda como respaldo digital.
- Los PDF quedan guardados en `tickets/` junto al `.exe` (misma lógica de rutas que `panaderia.db` y `backups/`), nombrados `ticket_<id>_<fecha ISO>.pdf` para que ordenen cronológicamente en el explorador. Reimprimir la misma venta sobreescribe el mismo archivo. No hay límite de archivos (a diferencia de `backups/`): son chicos y son el respaldo digital del ticket.
- **Nueva Venta**: al confirmar, el diálogo pregunta "¿Generar el ticket para imprimirlo?" (Sí/No) -- se preguntó a propósito en vez de generarlo siempre (no todos los clientes quieren ticket) o de esconderlo en un botón aparte.
- **Historial > Ventas > Detalle**: botón "Ticket" para (re)generar el de una venta pasada. No se ofrece para ventas anuladas.
- El emblema del logo aparece arriba a la izquierda del ticket, reinterpretado para papel: el JPEG original (líneas doradas sobre fondo negro) se imprimiría como un bloque sólido de tinta, así que `_logo_emblema()` convierte el brillo de las líneas en opacidad de tinta negra y deja el fondo transparente -- en la hoja blanca solo se imprimen las líneas del emblema, en negro. Si falta `FermentoLogo.jpeg`, el ticket sale sin emblema (solo el texto "FERMENTO"), sin romperse.
- Nueva función `get_venta(venta_id)` en `database.py` y nueva dependencia `reportlab` (agregada a `requirements.txt`; si falta, solo falla la generación del ticket con mensaje claro, no el arranque de la app).
- Sigue pendiente (hardware/contacto): impresora térmica y envío del ticket al cliente.

### 2026-07-10 — Margen congelado en la venta, visible en Ventas/Cortes/Análisis
- El costo se congela en el momento de la venta (`detalle_venta.costo_unitario`/`costo_subtotal`, poblados en `registrar_venta()`), mismo criterio que `precio_unitario`/`subtotal` -- se descartó congelarlo recién en el corte porque mezclaría "precio de cuando se vendió" con "costo de cuando se cortó", dos momentos distintos que podrían ni siquiera ser el mismo día.
- `corte_detalle.costo_total` y `cortes.costo_total` (migración automática) suman lo ya congelado -- `hacer_corte()` nunca vuelve a consultar `productos.costo`. Cambiar el costo de un producto hoy no altera ninguna venta o corte ya hecho.
- **Historial > Ventas** (detalle de una venta): nueva columna "Margen" por línea ("—" si esa línea no tenía costo cargado) y un total al pie, con nota "(algunos productos sin costo cargado)" si el total mezcla líneas con y sin datos.
- **Historial > Cortes** (detalle + export CSV): mismo criterio -- columna "Margen" por producto, margen total del corte, y la misma nota de datos parciales cuando corresponde. El CSV agrega columnas "Costo" y "Margen de ganancia" (en blanco, no "0", cuando no hay costo cargado para ese producto).
- **Análisis**: tercera opción "Margen ($)" en el toggle del ranking de productos (antes "Cantidad" / "Monto ($)"). A diferencia de los totales agregados de Ventas/Cortes, acá los productos sin costo cargado se EXCLUYEN del todo (no hay "número parcial" razonable para un solo producto en un ranking). Las barras ahora soportan valores negativos (margen negativo, un producto vendido a pérdida): crecen hacia la izquierda de 0, con el degradé de color invertido y una línea de referencia vertical en cero.
- El export "Exportar todas las ventas" (Cortes) también suma columnas "Costo unitario" y "Margen de ganancia" por línea.
- **2026-07-10 (ajuste posterior)**: a pedido del usuario, en ambos CSV (el de un corte y el de "Exportar todas las ventas") la columna se renombró de "Margen" a **"Margen de ganancia"**. Solo en los CSV -- los diálogos en pantalla (detalle de venta, detalle de corte) siguen diciendo "Margen".
- **Verificado con datos reales**: el usuario probó el ranking de Análisis con productos propios y confirmó el comportamiento esperado -- un producto con costo cargado en algunas ventas pero no en todas muestra un margen más alto de lo real (el costo faltante de esas ventas cuenta como $0, no se excluye), justo el caso ya documentado como "número optimista" en `CLAUDE.md`. No hizo falta ningún cambio de código.

### 2026-07-10 — Costo interno y margen por producto
- Nuevo campo "Costo interno ($, opcional -- para calcular margen)" en el alta/edición de productos (`productos.costo`, migración automática, default 0 = todavía no cargado).
- Nueva columna "Margen" en la lista de Productos: `$(precio-costo) (pct%)`, verde si es positivo, rojo si es negativo o cero; muestra "—" gris (no un margen falso de 100%) cuando el costo no se cargó todavía.
- La columna es sortable (clic para ordenar, igual que Nombre/Precio/Stock); los productos sin costo cargado ordenan siempre como el valor más bajo, para no aparecer mezclados con los que sí tienen margen real calculado.
- Alcance de esta mejora: solo la pantalla Productos. No hay (todavía) ninguna vista agregada de margen a nivel de corte o período -- quedó anotado como pendiente.

### 2026-07-10 — Aviso de stock bajo en Inventario
- Nuevo campo "Stock mínimo (alerta, opcional)" en el alta/edición de insumos (`insumos.stock_minimo`, migración automática, default 0 = sin umbral configurado -- ese insumo nunca dispara alerta).
- Al pie de la pantalla Inventario aparece un aviso listando los insumos activos cuyo stock cayó a su mínimo o por debajo; si ninguno está bajo, no se muestra nada (ni una franja vacía) -- se pide explícitamente así.
- El número de stock de la fila también se pinta en el color de advertencia cuando ese insumo está bajo, como refuerzo visual además del aviso general.
- No aplica a insumos desactivados.

### 2026-07-10 — Sección Inventario (control de insumos)
- Nueva tabla `insumos(id, nombre, unidad, stock, activo)` -- `stock` es REAL (no INTEGER como `productos`), porque las cantidades de insumos se miden en kilos/litros, no en unidades enteras.
- CRUD completo en `database.py` (`get_insumos`, `add_insumo`, `update_insumo`, `ajustar_stock_insumo`, `desactivar_insumo`, `reactivar_insumo`), calcado del de Productos.
- Nueva pantalla "Inventario" (`views/inventario.py`), sección propia del sidebar (entre Productos y Nueva venta): alta/edición de insumos, ajuste de stock, desactivar/reactivar, búsqueda por nombre y orden por columna (Nombre/Stock) -- mismo patrón de UI que Productos.
- Es un **control manual**, sin ningún vínculo con las ventas: no hay descuento automático de insumos al vender. Se decidió así a propósito -- vincularlo por receta (cuánto insumo consume cada producto vendido) es mucho más complejo y queda anotado como pendiente para otra sesión.
- Se anotó además como pendiente "costo interno por producto" (para poder calcular márgenes), a pedido del usuario -- no implementado todavía, solo documentado.

### 2026-07-10 — Gráficos comparativos entre cortes
- Nueva sub-pestaña "Gráficos" en Historial (`views/graficos.py`), con dos gráficos de barra embebidos con matplotlib (`FigureCanvasTkAgg`), coloreados con la paleta oscura de la marca (fondo `theme.BG_CARD`, barras `theme.ACCENT`, grilla sutil sin bordes duros):
  - **Total vendido por corte**, en orden cronológico. Solo se etiqueta con su valor el corte de mayor total (el "pico"), para no saturar el gráfico si el rango incluye muchos cortes — el valor exacto de cada uno ya está en la tabla de la sub-pestaña Cortes.
  - **Producto más vendido**, top 10 por cantidad, ordenado de mayor a menor. Al ser una lista acotada a 10, sí se etiqueta cada barra con su cantidad.
- Ambos gráficos comparten un filtro de rango de fechas (Desde/Hasta, formato DD-MM-AAAA) arriba de los dos, igual que el resto de la app — un solo filtro que aplica a todo lo que muestra la pantalla.
- El filtro es por la **fecha del corte** (cuándo se cerró caja), no la de cada venta individual — mismo criterio que el resto de la sub-pestaña Cortes. El ranking de productos nueva función `get_ranking_productos()` en `database.py`, que solo cuenta ventas ya incluidas en algún corte (no las pendientes de cortar).
- Nueva dependencia: `matplotlib` (agregada a `requirements.txt`). Aumenta el tamaño del `.exe` empaquetado con PyInstaller.
- Ajuste de estilo a pedido del usuario: fondo de ambos gráficos negro puro (`#000000`, no el gris oscuro `theme.BG_CARD` que usa el resto de la app) y cada barra con un color distinto, tomados de la paleta `tab20` de matplotlib (20 colores, se repiten si hay más de 20 barras).
- Reubicación a pedido del usuario: `GraficosPanel` pasó de ser una tercera sub-pestaña de Historial a ser su propia sección de la barra lateral, llamada **"Análisis"** — la idea es que sea "la sección que permite analizar cómo va el negocio", separada del historial de registros crudos (Ventas/Cortes). `views/historial.py` volvió a tener solo dos sub-pestañas (Ventas, Cortes).
- Presets de rango de fechas: botones "Últimos 7 cortes", "Últimos 30 cortes" y "Este mes" arriba de los gráficos, para no tener que tipear el rango a mano cada vez. Calculan el "Desde" correspondiente y lo cargan en el campo (visible y editable desde ahí); "Últimos N cortes" cuenta cortes, no días corridos -- si hay menos de N cortes en total, trae todos.
- Toggle de métrica en el ranking de productos: botones "Cantidad" (por defecto) / "Monto ($)" arriba del gráfico. Cambia qué se ordena y qué valor se etiqueta en cada barra -- lo más vendido en unidades no siempre es lo que más factura.
- "Total vendido por corte" pasó de barras a **línea de tiempo** (con marcadores y relleno sutil bajo la curva), a pedido del usuario -- el eje es tiempo, una línea lee mejor la tendencia que columnas sueltas. Ahora etiqueta TODOS los puntos si hay 15 o menos (antes solo se etiquetaba el pico, lo que generó la duda de si era un bug); con más de 15 puntos sigue etiquetando solo el pico y el más reciente para no saturar.

### 2026-07-10 — Ranking con degradé, límite configurable, y presets resaltados
- Las barras del ranking de productos ya no son de un color plano: cada una tiene un **degradé** (de una versión oscurecida del mismo color a su tono pleno), a pedido del usuario que no le gustaba el look "plano". Técnicamente ya no se usa `ax.barh()` sino `imshow()` recortado a la forma de cada barra (`_barra_gradiente()` en `views/graficos.py`); los valores se etiquetan a mano con `ax.annotate()` en vez de `bar_label()`.
- El "top 10" fijo del ranking pasó a ser configurable: campo "Mostrar top" + botón "Aplicar" (vacío = mostrar todos los productos). El alto del gráfico crece según cuántas barras haya, para que no se aprieten con un top grande.
- Los botones de preset de fecha ("Últimos 7 cortes", "Últimos 30 cortes", "Este mes") ahora se resaltan en dorado cuando están aplicados, igual que las pestañas activas en el resto de la app -- antes quedaban siempre del mismo color gris, lo cual no era consistente con el resto de la interfaz. Se desmarcan si el usuario edita el rango a mano o lo limpia.
- Se agregó el título "Análisis" arriba de los filtros (mismo estilo que "Historial" o "Productos": tamaño 22, negrita, con separación del borde superior de la ventana) -- antes los filtros quedaban pegados al borde, sin encabezado de sección.

### 2026-07-10 — Formato de fecha DD-MM-AAAA en toda la app
- Nuevo `views/formato.py::fecha()`: convierte una fecha ISO (como se guarda en la BD, `AAAA-MM-DD` o `AAAA-MM-DD HH:MM:SS`) a `DD-MM-AAAA` (o con hora) para mostrar. No cambia cómo se guarda en la base de datos ni cómo se comparan fechas internamente -- ISO sigue siendo el formato de almacenamiento porque ordena bien como texto.
- Aplicado en: listado de Ventas, listado de Cortes, diálogo de detalle de venta (incluida la fecha de anulación), diálogo "Anular venta", diálogo de detalle de corte, confirmación de "Deshacer corte", y los dos CSV exportados (el de un corte individual y el de ventas detalladas).
- El filtro de fechas de Ventas ahora pide y valida `DD-MM-AAAA` (antes `AAAA-MM-DD`); internamente lo sigue convirtiendo a ISO para comparar contra `ventas.fecha`.
- Excepción a propósito: el nombre de archivo sugerido al exportar un corte a CSV (`corte_5_2026-07-10.csv`) sigue usando la fecha en ISO, no DD-MM-AAAA -- así los archivos quedan ordenados cronológicamente por nombre en una carpeta de Windows.

### 2026-07-10 — Filtro por fecha en Historial (sub-pestaña Ventas)
- Campos "Desde" y "Hasta" (formato AAAA-MM-DD) arriba del listado de ventas, con botones "Filtrar" y "Limpiar".
- El filtro se aplica recién al apretar "Filtrar" (o Enter en cualquiera de los dos campos), no en vivo mientras se escribe -- filtrar en vivo rompería la comparación con una fecha a medio escribir (ej. "202"). Valida el formato y que "Desde" no sea posterior a "Hasta" antes de aplicar; si algo no es válido, muestra el error y no toca la lista.
- Compara directamente los primeros 10 caracteres de `ventas.fecha` (string ISO `AAAA-MM-DD HH:MM:SS`, comparable como texto) contra los límites -- no hace falta una consulta nueva a la BD, se filtra en memoria sobre `db.get_ventas()`.
- Mensaje distinto para "sin ventas en el rango" vs. "no hay ventas registradas".
- Alcance: solo la sub-pestaña Ventas (el listado crudo de tickets, el que más crece con el tiempo). La sub-pestaña Cortes no tiene este filtro todavía.

### 2026-07-10 — Búsqueda/filtro y orden en la lista de productos
- Campo de búsqueda arriba de la lista en la pantalla Productos: filtra en vivo por nombre (sin distinguir mayúsculas/minúsculas) a medida que se escribe.
- Filtra en memoria sobre la lista ya cargada (`db.get_productos()`), sin ir a la BD por cada letra tipeada — el catálogo de una panadería es chico, no hace falta una consulta nueva.
- Mensaje distinto según el caso: "No hay productos registrados" (catálogo vacío) vs. "No hay productos que coincidan con la búsqueda" (hay productos pero ninguno matchea el filtro).
- Orden por columna clickeable: los encabezados "Nombre", "Precio" y "Stock" son botones. Un clic en una columna nueva ordena ascendente y muestra flecha "▼" al lado del nombre de esa columna; un clic de nuevo sobre la misma columna invierte el orden (flecha "▲"). Solo la columna activa muestra flecha. Se aplica en memoria, sobre la lista ya filtrada — no cambia la consulta a la BD. (Reemplaza al selector desplegable de la primera versión de esta mejora, descartado por preferencia del usuario.)

### 2026-07-10 — Backup automático de la base de datos
- `respaldar_db()` en `database.py`: copia `panaderia.db` a `backups/` con timestamp en el nombre, llamada en `main.py` antes de `init_db()` (respalda el estado con el que se cerró la sesión anterior, antes de que corra cualquier migración).
- No usa `@_safe` ni levanta `DBError` a propósito: un fallo al hacer backup (disco lleno, permisos) no debe impedir que la app arranque.
- Guarda como máximo 30 copias, borrando las más viejas -- pensado para no llenar el disco con meses de uso diario.
- No existía ningún mecanismo de respaldo antes de esto (dependía de que la persona copiara `panaderia.db` a mano).

### 2026-07-10 — Exportación de ventas detalladas a CSV
- `get_ventas_detalle_export()`: una fila por línea de venta (producto vendido dentro de una venta), con la fecha/hora EXACTA de esa venta (`ventas.fecha`) — a diferencia del export de Cortes, que agrupa cantidades por producto dentro de cada corte y usa la fecha del corte. Pensado para analizar qué se vende más y a qué hora del día, no para cuadrar caja.
- Incluye ventas ya cortadas y pendientes por igual (el estado del corte no importa para este análisis); excluye ventas anuladas.
- Botón "Exportar todas las ventas" agregado en la sub-pestaña Cortes. Reemplaza al botón "Exportar todo a CSV" (agregado por producto por corte): se sacó por preferencia del usuario, que prefirió quedarse solo con el detalle a nivel de venta. Se borró también `get_todos_los_cortes_detalle()` en `database.py`, que quedó sin uso. El export individual por corte ("CSV" en cada fila, `get_corte_detalle()`) no se tocó.

### 2026-07-10 — Deshacer último corte de caja
- `deshacer_ultimo_corte()`: borra físicamente el corte de mayor `id` (a diferencia de ventas/productos, acá no hay borrado lógico — no hay nada que preservar), reabre sus ventas (`corte_id` vuelve a NULL, quedan pendientes de cortar de nuevo) y borra su detalle (`corte_detalle`). No toca el stock: eso es responsabilidad de anular una venta, no de deshacer un corte.
- Solo se permite deshacer el corte más reciente: si se pudiera deshacer uno intermedio, quedaría un corte "salteado" en la cronología entre dos que sí persisten.
- UI en la sub-pestaña Cortes: botón "Deshacer" (rojo, mismo estilo que "Anular" en Ventas) que solo aparece en la fila del corte con el `id` más alto de la lista, con confirmación explícita antes de ejecutar.

### 2026-07-09 — Anulación de ventas
- Nuevas columnas en `ventas`: `anulada`, `motivo_anulacion`, `fecha_anulacion` (migración automática, igual que `corte_id`).
- `anular_venta(venta_id, motivo)`: devuelve el stock vendido y marca la venta como anulada, sin borrar el registro (queda en el historial con motivo y fecha). Solo permite anular mientras `corte_id IS NULL` — si la venta ya está en un corte cerrado, se bloquea con `DBError` para no dejar el total de ese corte sin ventas reales que lo sostengan.
- `_resumen_pendiente()` y `hacer_corte()` excluyen ventas anuladas al calcular pendientes y al asignar `corte_id`.
- UI en la sub-pestaña Ventas: botón "Anular" (solo visible si la venta está pendiente y no anulada) que abre un diálogo pidiendo motivo obligatorio; las ventas anuladas se muestran con etiqueta "ANULADA" y el motivo/fecha en el detalle.
- Se decidió anulación lógica en vez de borrado físico para conservar trazabilidad completa (mismo criterio que `desactivar_producto`).

### 2026-07-07 — v1.0, versión inicial
- Módulo Productos: alta, edición, ajuste de stock, desactivar/reactivar.
- Módulo Nueva Venta: carrito con control de cantidades y validación de stock.
- Módulo Historial: listado de ventas con detalle por pedido.
- Base de datos SQLite con tres tablas: productos, ventas, detalle_venta.
- Descuento automático de stock al confirmar venta.
- Guardado de `precio_unitario` en detalle para preservar historial correcto.

### 2026-07-08 — Fix: botón "Guardar" invisible en "Agregar producto"
`_DialogoProducto` fijaba una altura de ventana constante, pero "Agregar" tiene un campo más ("Stock inicial") que "Editar", y el botón quedaba fuera del área visible. Ahora el alto se calcula según el contenido real (`winfo_reqheight()`).

### 2026-07-08 — Robustez y UX de diálogos
- Fuga de conexiones SQLite corregida con `contextlib.closing()`.
- Manejo de errores de BD: excepción `DBError` + decorador `@_safe`, mensajes amigables en vez de crashes.
- Enter/Escape en diálogos; botón de sección activa resaltado en la barra lateral.
- El precio acepta coma decimal.

### 2026-07-08 — Segunda ronda: foco, centrado, condición de carrera
- Foco automático en el primer campo de los diálogos.
- Diálogos centrados sobre la ventana principal.
- Formato de precio consistente al editar (`10.50` en vez de `10.5`).
- `registrar_venta()` exige `stock >= cantidad` en el propio UPDATE con rollback si falla — blindaje real contra condición de carrera (ej. abrir la app dos veces sin querer).

### 2026-07-08 — Modo oscuro + identidad de marca "Fermento"
- Paleta centralizada en `views/theme.py`, tomada del logo (negro + dorado `#c9a227` + blanco cálido).
- `views/branding.py` genera el logo del sidebar, el ícono de ventana/barra de tareas, y una marca de agua del emblema (nítida a baja opacidad, no difuminada — un blur fuerte sobre el dibujo de líneas finas se veía como una mancha).
- La marca de agua se re-genera automáticamente al cambiar el tamaño de la ventana (maximizar, restaurar).
- Si `FermentoLogo.jpeg` no está presente, la app cae a texto plano sin romperse.

### 2026-07-08 — Cortes de caja + exportación a CSV
- Nuevas tablas `cortes` y `corte_detalle`; columna `ventas.corte_id` (NULL = pendiente de cortar), con migración automática.
- `hacer_corte()` cierra todas las ventas pendientes en un corte nuevo (permite varios cortes por día); no crea cortes vacíos.
- Nueva sub-pestaña "Cortes" dentro de Historial: resumen de pendientes, confirmación con desglose antes de cerrar, listado de cortes, detalle por producto, y exportación a CSV (UTF-8 con BOM para que Excel muestre bien los acentos).
- Fix: "Exportar todo a CSV" exportaba solo el resumen por corte (id/fecha/cantidad/total), sin desglose por producto — insuficiente para análisis. `get_todos_los_cortes_detalle()` ahora arma el CSV en formato "largo" (una fila por producto por corte, con la fecha del corte), pensado para tablas dinámicas en Excel.
