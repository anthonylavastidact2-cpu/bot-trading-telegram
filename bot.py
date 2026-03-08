# bot.py - Versión completa y robusta para Telegram
# Compatible con python-telegram-bot 13.15

import logging
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from config import BOT_TOKEN, PASSWORD, ACTIVOS
from estrategias import (
    get_activo_data,
    detectar_senales_apalancamiento,
    detectar_senales_binarias,
    backtest_estrategia
)

# ------------------- CONFIGURACIÓN DE LOGGING -------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- CONTROL DE ACCESO -------------------
usuarios_autorizados = set()

# ------------------- FUNCIONES DE LOS COMANDOS -------------------

def start(update: Update, context: CallbackContext):
    """Comando /start: da la bienvenida y pide contraseña si no está autenticado."""
    user_id = update.effective_user.id
    if user_id in usuarios_autorizados:
        update.message.reply_text(
            "¡Bienvenido de nuevo! Ya tienes sesión iniciada.\n"
            "Usa /senales para ver las últimas oportunidades."
        )
    else:
        update.message.reply_text(
            "Bienvenido al Bot de Señales de Trading.\n"
            "Este es un bot privado. Por favor, introduce la contraseña para continuar."
        )
        context.user_data['esperando_password'] = True

def manejar_mensajes(update: Update, context: CallbackContext):
    """Procesa mensajes de texto que no son comandos (para la autenticación)."""
    user_id = update.effective_user.id
    texto = update.message.text

    # Si el usuario está en proceso de autenticación
    if context.user_data.get('esperando_password'):
        if texto == PASSWORD:
            usuarios_autorizados.add(user_id)
            context.user_data['esperando_password'] = False
            # Guardar el chat_id del primer usuario como admin (para futuras notificaciones)
            if 'admin_chat_id' not in context.bot_data:
                context.bot_data['admin_chat_id'] = user_id
            update.message.reply_text(
                "✅ ¡Contraseña correcta! Acceso concedido.\n"
                "Usa /senales para empezar."
            )
        else:
            update.message.reply_text("❌ Contraseña incorrecta. Intenta de nuevo.")
        return

    # Si ya está autorizado, puede enviar "senales" como atajo
    if user_id in usuarios_autorizados:
        if texto.lower() in ["senales", "/senales"]:
            enviar_todas_las_senales(update, context)
        else:
            update.message.reply_text("Comando no reconocido. Usa /senales.")
    else:
        update.message.reply_text("Por favor, primero inicia sesión con /start e introduce la contraseña.")

def senales_command(update: Update, context: CallbackContext):
    """Comando /senales: ejecuta el análisis completo de todos los activos."""
    user_id = update.effective_user.id
    if user_id not in usuarios_autorizados:
        update.message.reply_text("No tienes acceso. Usa /start para iniciar sesión.")
        return
    enviar_todas_las_senales(update, context)

def enviar_todas_las_senales(update: Update, context: CallbackContext):
    """Analiza todos los activos y envía las señales detectadas."""
    update.message.reply_text("🔍 Analizando mercados con estrategias optimizadas...")

    for nombre_activo, simbolo in ACTIVOS.items():
        try:
            logger.info(f"Procesando {nombre_activo}...")
            data = get_activo_data(simbolo)
            if not data:
                update.message.reply_text(
                    f"❌ No se pudieron obtener datos de {nombre_activo} "
                    "(fallo de red o datos insuficientes)."
                )
                continue

            senal_apalancamiento = detectar_senales_apalancamiento(data)
            senal_binarias = detectar_senales_binarias(data)

            mensaje = f"🔹 *{nombre_activo}*"

            if senal_apalancamiento:
                s = senal_apalancamiento
                mensaje += (
                    f"\n   📈 *Apalancamiento*: {s['tipo']} a ${s['precio']}"
                    f"\n       TP1: ${s['tp1']} | TP2: ${s['tp2']} (confianza {s['confianza']})"
                )
            else:
                mensaje += f"\n   ⏸ Apalancamiento: Sin señal clara."

            if senal_binarias:
                s = senal_binarias
                mensaje += (
                    f"\n   ⏱ *Binarias*: {s['tipo']} a ${s['precio']} "
                    f"(Duración: {s['duracion']}, confianza {s['confianza']})"
                )
            else:
                mensaje += f"\n   ⏸ Binarias: Sin señal clara."

            update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.exception(f"Error procesando {nombre_activo}")
            update.message.reply_text(f"❌ Error inesperado procesando {nombre_activo}: {str(e)}")
            continue

def backtest_command(update: Update, context: CallbackContext):
    """Comando /backtest <activo> <días>: ejecuta backtest sobre un activo."""
    user_id = update.effective_user.id
    if user_id not in usuarios_autorizados:
        update.message.reply_text("No tienes acceso. Usa /start para iniciar sesión.")
        return

    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text(
                "Uso: /backtest <activo> <días>\n"
                "Ejemplo: /backtest ORO 180"
            )
            return

        activo_nombre = args[0].upper()
        dias = int(args[1])

        if activo_nombre not in ACTIVOS:
            update.message.reply_text(
                f"Activo no encontrado. Disponibles: {', '.join(ACTIVOS.keys())}"
            )
            return

        simbolo = ACTIVOS[activo_nombre]
        update.message.reply_text(
            f"⏳ Ejecutando backtest para {activo_nombre} en los últimos {dias} días..."
        )

        resultado = backtest_estrategia(simbolo, dias)

        if resultado is None:
            update.message.reply_text("❌ No se pudieron obtener datos para el backtest.")
            return

        if "mensaje" in resultado:
            update.message.reply_text(resultado["mensaje"])
            return

        mensaje = (
            f"📊 *Backtest {activo_nombre} - Últimos {dias} días*\n"
            f"Total operaciones: {resultado['total_operaciones']}\n"
            f"Ganadoras: {resultado['operaciones_ganadoras']}\n"
            f"Perdedoras: {resultado['operaciones_perdedoras']}\n"
            f"Win Rate: {resultado['win_rate']}%\n"
            f"Ganancia total: ${resultado['ganancia_total']}\n"
            f"Ganancia promedio: ${resultado['ganancia_promedio']}\n"
            f"Pérdida promedio: ${resultado['perdida_promedio']}"
        )
        update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.exception("Error en backtest_command")
        update.message.reply_text(f"Error en backtest: {str(e)}")

# ------------------- FUNCIÓN PRINCIPAL -------------------
def main():
    """Punto de entrada del bot."""
    print("🚀 Iniciando bot con versión 13.15...")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Registrar manejadores
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("senales", senales_command))
    dp.add_handler(CommandHandler("backtest", backtest_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, manejar_mensajes))

    # Iniciar el bot
    updater.start_polling()
    print("✅ Bot iniciado correctamente. Presiona Ctrl+C para detener.")
    updater.idle()

if __name__ == '__main__':
    main()
