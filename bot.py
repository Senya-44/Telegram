import os
import re
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Flask app
flask_app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные хранилища
reminders = {}
user_states = {}

async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

# ВСЕ ВАШИ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
# (start, button_handler, handle_message, check_reminders)

async def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    
    print(f"🚀 /start от {user.first_name} (@{user.username or 'no_username'})")
    print(f"   👤 ID: {user.id}")
    print(f"   📱 Чат: {chat.id} ({chat.type})")
    
    if chat.type in ['private', 'group', 'supergroup']:
        keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"Привет, {user.first_name}! 🔔\n\n"
            "Я напомню задачу **ВСЕМ участникам чата**!\n\n"
            f"👥 Чат: {'Группа' if chat.type in ['group', 'supergroup'] else 'ЛС'}"
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        print(f"✅ ОТВЕТИЛ {user.id} в чате {chat.id}")

# ... ВСТАВЬТЕ ЗДЕСЬ ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ ИЗ ВАШЕГО КОДА ...
# button_handler, handle_message, check_reminders

def create_application():
    """Создает Telegram Application"""
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        raise ValueError("❌ BOT_TOKEN не найден!")
    
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    return application

@flask_app.route('/', methods=['GET'])
def index():
    return "🚀 Reminder Bot работает!"

@flask_app.route('/<token>', methods=['POST'])
def webhook(token):
    """Webhook endpoint"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.create_task(application.process_update(update))
        return 'OK'
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return 'Error', 500

def run_reminders():
    """Фоновая задача напоминаний"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_reminders(application))

if __name__ == '__main__':
    global application
    application = create_application()
    
    # Запуск фоновой задачи
    reminder_thread = threading.Thread(target=run_reminders, daemon=True)
    reminder_thread.start()
    
    port = int(os.getenv('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)





