"""Arma el paquete que se instala (o se actualiza) en la panadería.

    python empaquetar.py

Deja en `dist/` un ZIP listo para mandar: `Fermento-v1.0.0.zip`, que adentro
tiene una sola carpeta, `Programa\\`.

Por qué el ZIP contiene una carpeta y no los archivos sueltos: así la
instalación y la actualización son EXACTAMENTE el mismo gesto —
descomprimir en la carpeta `Fermento` del usuario — y el resultado es siempre

    %USERPROFILE%\\Fermento\\
    ├─ Datos\\        <- la crea la app sola. El ZIP no la toca NUNCA.
    └─ Programa\\     <- esto es lo que viene en el ZIP.

Va en la carpeta personal del usuario y no en `C:\\Fermento` porque crear una
carpeta en la raíz del disco pide permisos de administrador, y tampoco en
Documentos ni en el Escritorio porque OneDrive los sincroniza y una base
SQLite sobre una carpeta sincronizada se puede corromper.

**El paquete no contiene ningún dato**: ni base, ni backups, ni tickets, ni
log. Eso no es un descuido sino la garantía principal del formato — mientras
el ZIP no tenga un `panaderia.db` adentro, ninguna actualización puede pisar
el historial de ventas, ni siquiera si quien actualiza se equivoca de
carpeta o descomprime encima sin borrar nada.

Decisiones del empaquetado (ver también DOCUMENTACION.md):

* **`--onedir`, no `--onefile`.** Un solo .exe es más lindo de mandar, pero
  descomprime ~200 MB (matplotlib, customtkinter, Pillow, reportlab) al
  %TEMP% en CADA arranque: en la máquina de la panadería (i5-6500T) son
  varios segundos cada vez que abren la app. En modo carpeta arranca
  directo. De paso da menos falsos positivos de antivirus, que es un
  problema real de los .exe autoextraíbles no firmados.
* **`--collect-data customtkinter`**: customtkinter carga sus temas y
  fuentes desde archivos .json que PyInstaller no detecta solo (no se
  importan, se abren en runtime). Sin esto el .exe compila bien y revienta
  al abrir, que es la peor forma de fallar: no se ve hasta la máquina
  destino.
* **El logo y el ícono se copian al lado del .exe**, no se empaquetan
  adentro: `views/branding.py` los busca en `rutas.APP_DIR`. Poder
  reemplazar el JPEG sin recompilar es deliberado.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from version import VERSION

RAIZ = Path(__file__).parent
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"
NOMBRE = "Fermento"
MANUAL = "Fermento - Manual de instalacion y uso.docx"


def _limpiar():
    """Build desde cero: un `dist/` con sobras de una compilación anterior es
    la forma más fácil de mandar un paquete con un archivo viejo adentro."""
    for carpeta in (DIST, BUILD):
        if carpeta.exists():
            shutil.rmtree(carpeta)


def _regenerar_icono():
    """El .ico que se le pega al .exe se rehace en cada build, a partir del
    JPEG actual del logo.

    PyInstaller incrusta el ícono en el ejecutable en tiempo de compilación:
    si acá quedara el archivo viejo, la única forma de notarlo sería mirando
    el ícono en la máquina de la panadería. Regenerarlo siempre cuesta
    milisegundos y saca el problema de raíz.
    """
    from views import branding
    ruta = branding.icono_ventana(regenerar=True)
    if ruta is None:
        print("AVISO: sin FermentoLogo.jpeg no hay ícono; el .exe sale con el de PyInstaller.")
    return ruta


def _compilar():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", NOMBRE,
        "--collect-data", "customtkinter",
    ]
    icono = RAIZ / "assets" / "fermento.ico"
    if icono.exists():
        cmd += ["--icon", str(icono)]
    cmd.append(str(RAIZ / "main.py"))

    print(">", " ".join(cmd), "\n")
    subprocess.run(cmd, check=True, cwd=RAIZ)


def _armar_carpeta_programa():
    """`dist/Fermento/` (lo que deja PyInstaller) → `dist/Programa/`."""
    programa = DIST / "Programa"
    (DIST / NOMBRE).rename(programa)

    # Van AFUERA del bundle a propósito: branding.py los busca en la carpeta
    # del .exe, así que se pueden reemplazar sin recompilar.
    logo = RAIZ / "FermentoLogo.jpeg"
    if logo.exists():
        shutil.copy2(logo, programa / logo.name)
    else:
        print("AVISO: no está FermentoLogo.jpeg. La app abre igual, pero sin logo.")

    icono = RAIZ / "assets" / "fermento.ico"
    if icono.exists():
        (programa / "assets").mkdir(exist_ok=True)
        shutil.copy2(icono, programa / "assets" / icono.name)

    # El manual viaja adentro del paquete y no aparte: mandado por separado se
    # pierde en el chat, y la persona que instala lo necesita justo cuando
    # todavía no tiene la app abierta para preguntar nada.
    manual = RAIZ / MANUAL
    if manual.exists():
        shutil.copy2(manual, programa / manual.name)
    else:
        print(f"AVISO: no está '{MANUAL}'. El paquete sale sin manual.")

    # utf-8-SIG (con BOM), no utf-8 a secas: este .txt lo va a abrir alguien en
    # la panadería con el Bloc de notas de Windows. El Notepad moderno detecta
    # UTF-8 sin BOM, pero las versiones anteriores a Windows 10 1903 lo leen
    # como ANSI y muestran "Versiòn" y "Imàgenes" -- justo en el archivo que
    # explica cómo instalar. El BOM lo resuelve en cualquier versión y no
    # molesta a ningún otro programa.
    (programa / "LEEME.txt").write_text(_LEEME.format(version=VERSION),
                                        encoding="utf-8-sig")
    return programa


def _comprimir(programa):
    destino = DIST / f"{NOMBRE}-v{VERSION}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in programa.rglob("*"):
            if archivo.is_file():
                # arcname arranca en "Programa/..." para que al descomprimir
                # en la carpeta Fermento del usuario quede en su lugar sola.
                z.write(archivo, Path("Programa") / archivo.relative_to(programa))
    return destino


_LEEME = """\
FERMENTO — Sistema de ventas
Versión {version}

Este archivo es el resumen. En esta misma carpeta está el manual completo,
con todo explicado paso a paso y sin tecnicismos:

   Fermento - Manual de instalacion y uso.docx

INSTALAR POR PRIMERA VEZ
------------------------
1. Abrir el Explorador de archivos, escribir  %USERPROFILE%  en la barra de
   direcciones de arriba y presionar Enter. Es la carpeta personal del
   usuario (la que tiene adentro Descargas, Documentos, Imágenes).
2. Crear ahí una carpeta llamada  Fermento
3. Descomprimir este ZIP dentro de esa carpeta. Tiene que quedar así:

       Fermento\\Programa\\Fermento.exe

4. Abrir Fermento.exe. La primera vez Windows puede mostrar un aviso azul
   de SmartScreen (el programa no está firmado): "Más información" ->
   "Ejecutar de todas formas".
5. La app crea sola la carpeta  Fermento\\Datos  con la base de datos.
6. Para tenerlo a mano: botón derecho sobre Fermento.exe -> "Mostrar más
   opciones" -> "Enviar a" -> "Escritorio (crear acceso directo)".

NO instalar en Documentos ni en el Escritorio: si la máquina usa OneDrive,
esas carpetas se sincronizan solas y eso puede dañar la base de datos.
Tampoco en C:\\ directamente, porque Windows pide permisos de administrador.

ACTUALIZAR A UNA VERSIÓN NUEVA
------------------------------
1. Cerrar la app.
2. Borrar la carpeta  Fermento\\Programa  entera.
3. Descomprimir el ZIP nuevo dentro de la carpeta  Fermento
4. Abrir Fermento.exe (el acceso directo del escritorio sigue sirviendo).

NO se toca la carpeta Datos. Las ventas, los productos y el historial siguen
donde estaban: este ZIP no trae ninguna base de datos adentro, así que no hay
forma de que una actualización los pise.

DÓNDE ESTÁN LAS VENTAS
----------------------
En  Fermento\\Datos  (la app muestra la ruta exacta en Ajustes, con un botón
para abrir la carpeta). Ahí adentro:

   panaderia.db          <- TODO el historial está en este archivo
   backups\\              <- copias automáticas, una por arranque (30 últimas)
   tickets\\              <- los PDF de los tickets
   panaderia_error.log   <- si algo falla, esto es lo que hay que mandar

Conviene copiar la carpeta Datos a un USB o a la nube cada tanto. El respaldo
automático protege contra un archivo dañado, no contra que se rompa la
computadora.
"""


def main():
    if not (RAIZ / "main.py").exists():
        print("No encuentro main.py. Correr este script desde la carpeta del proyecto.")
        return 1

    _limpiar()
    _regenerar_icono()
    _compilar()
    programa = _armar_carpeta_programa()
    zip_final = _comprimir(programa)

    exe = programa / f"{NOMBRE}.exe"
    peso = sum(f.stat().st_size for f in programa.rglob("*") if f.is_file())
    print(f"\nListo.")
    print(f"   Carpeta:  {programa}   ({peso / 1024 / 1024:.0f} MB)")
    print(f"   Para mandar:  {zip_final}   ({zip_final.stat().st_size / 1024 / 1024:.0f} MB)")
    print(f"   Ejecutable:  {exe.name}")
    print("\nProbalo desde la carpeta antes de mandarlo: tiene que abrir y crear")
    print("una carpeta 'Datos' al lado de 'Programa'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
