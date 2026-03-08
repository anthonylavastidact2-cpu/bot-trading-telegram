# bot.py - Versión compatible con python-telegram-bot 13.15

import logging
import asyncio
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import BOT_TOKEN, PASSWORD, ACTIVOS
from estrategias import get_activo_data, detectar_senales_apalancamiento, detectar_senales_binarias, backtest_estrategia

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Control de acceso
usuarios_autorizados = set()

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in usuarios_autorizados:
        update.message.reply_text("¡Bienvenido de nuevo! Ya tienes sesión iniciada.\nUsa /senales para ver las últimas oportunidades.")
    else:
        update.message.reply_text(
            "Bienvenido al Bot de Señales de Trading.\n"
            "Este es un bot privado. Por favor, introduce la contraseña para continuar."
        )
        context.user_data['esperando_password'] = True

def manejar_mensajes(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    texto = update.message.text

    if context.user_data.get('esperando_password'):
        if texto == PASSWORD:
            usuarios_autorizados.add(user_id)
            context.user_data['esperando_password'] = False
            # Guardar el chat_id del admin (el primero que se autentique)
            if 'admin_chat_id' not in context.bot_data:
                context.bot_data['admin_chat_id'] = user_id
            update.message.reply_text("✅ ¡Contraseña correcta! Acceso concedido.\nUsa /senales para empezar.")
        else:
            update.message.reply_text("❌ Contraseña incorrecta. Intenta de nuevo.")
        return

    if user_id in usuarios_autorizados:
        if texto.lower() == "senales" or texto.lower() == "/senales":
            enviar_todas_las_senales(update, context)
        else:
            update.message.reply_text("Comando no reconocido. Usa /senales.")
    else:
        update.message.reply_text("Por favor, primero inicia sesión con /start e introduce la contraseña.")

def senales_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in usuarios_autorizados:
        update.message.reply_text("No tienes acceso. Usa /start para iniciar sesión.")
        return
    enviar_todas_las_senales(update, context)

def enviar_todas_las_senales(update: Update, context: CallbackContext):
    update.message.reply_text("🔍 Analizando mercados con estrategias optimizadas...")
    
    for nombre_activo, simbolo in ACTIVOS.items():
        data = get_activo_data(simbolo)
        if not data:
            update.message.reply_text(f"❌ No se pudo obtener datos de {nombre_activo}.")
            continue
            
        senal_apalancamiento = detectar_senales_apalancamiento(data)
        senal_binarias = detectar_senales_binarias(data)
        
        mensaje = f"🔹 *{nombre_activo}*"
        
        if senal_apalancamiento:
            s = senal_apalancamiento
            mensaje += f"\n   📈 *Apalancamiento*: {s['tipo']} a ${s['precio']}"
            mensaje += f"\n       TP1: ${s['tp1']} | TP2: ${s['tp2']} (confianza {s['confianza']})"
        else:
            mensaje += f"\n   ⏸ Apalancamiento: Sin señal clara."
            
        if senal_binarias:
            s = senal_binarias
            mensaje += f"\n   ⏱ *Binarias*: {s['tipo']} a ${s['precio']} (Duración: {s['duracion']})"
        else:
            mensaje += f"\n   ⏸ Binarias: Sin señal clara."
            
        update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

def backtest_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in usuarios_autorizados:
        update.message.reply_text("No tienes acceso. Usa /start para iniciar sesión.")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Uso: /backtest <activo> <días>\nEjemplo: /backtest ORO 180")
            return
            
        activo_nombre = args[0].upper()
        dias = int(args[1])
        
        if activo_nombre not in ACTIVOS:
            update.message.reply_text(f"Activo no encontrado. Disponibles: {', '.join(ACTIVOS.keys())}")
            return
            
        simbolo = ACTIVOS[activo_nombre]
        update.message.reply_text(f"⏳ Ejecutando backtest para {activo_nombre} en los últimos {dias} días...")
        
        resultado = backtest_estrategia(simbolo, dias)
        
        if resultado is None:
            update.message.reply_text("❌ No se pudieron obtener datos para el backtest.")
            return
            
        if "mensaje" in resultado:
            update.message.reply_text(resultado["mensaje"])
            return
            
        mensaje = f"""
📊 *Backtest {activo_nombre} - Últimos {dias} días*
Total operaciones: {resultado['total_operaciones']}
Ganadoras: {resultado['operaciones_ganadoras']}
Perdedoras: {resultado['operaciones_perdedoras']}
Win Rate: {resultado['win_rate']}%
Ganancia total: ${resultado['ganancia_total']}
Ganancia promedio: ${resultado['ganancia_promedio']}
Pérdida promedio: ${resultado['perdida_promedio']}
        """
        update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        update.message.reply_text(f"Error en backtest: {str(e)}")

def main():
    print("🚀 Iniciando bot con versión 13.15...")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("senales", senales_command))
    dp.add_handler(CommandHandler("backtest", backtest_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, manejar_mensajes))

    # Iniciar bot
    updater.start_polling()
    print("✅ Bot iniciado correctamente. Presiona Ctrl+C para detener.")
    updater.idle()

if __name__ == '__main__':
    main()