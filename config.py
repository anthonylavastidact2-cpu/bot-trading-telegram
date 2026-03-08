import os

# El token se leerá desde una variable de entorno en Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# La contraseña también la podemos leer desde el entorno, o dejar un valor por defecto
PASSWORD = os.environ.get("PASSWORD", "cuba2026")

# Activos a vigilar (los mismos de siempre)
ACTIVOS = {
    "ORO": "GC=F",
    "PETROLEO": "CL=F",
    "NASDAQ": "NQ=F"
}