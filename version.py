"""Versión del programa, en un solo lugar.

Existe por la actualización a distancia: la app corre en la panadería y
quien la actualiza no está sentado ahí. Sin un número visible en pantalla,
"¿ya quedó instalada la versión nueva?" no se puede contestar por teléfono
más que mirando la fecha de un archivo -- y un `.exe` viejo funciona igual
de bien que uno nuevo, así que el síntoma de una actualización que no se
aplicó es que el problema reportado "sigue pasando" sin ninguna pista.

Se muestra en Ajustes, junto a la ruta de la carpeta de datos.

Al publicar una versión nueva: subir este número ANTES de empaquetar
(`empaquetar.py` lo lee para nombrar el ZIP, así que el nombre del archivo
y lo que la app dice en pantalla no pueden quedar desincronizados).
"""

VERSION = "1.3.0"
