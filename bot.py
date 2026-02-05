import os
import re
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

app = Flask(__name__)

# Глобальные переменные
reminders = {}
user_states = {}
application = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔥 ВАШИ ФУНКЦИИ (скопировать из старого кода)
async def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу **ВСЕМ**!"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'create_task':
        user_states[query.from_user.id] = 'waiting_task'
        await query.edit_message_text("📝 Напиши задачу:")

async def handle_message(update, context):
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        return
        
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = update.message.text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text("⏰ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
        
    elif state == 'waiting_time':
        time_text = update.message.text.strip()
        pattern = r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
        match = re.match(pattern, time_text)
        
        if match:
            day, month, hour, minute = map(int, match.groups())
            now = datetime.now()
            remind_date = now.replace(day=day, month=month, hour=hour, minute=minute)
            
            if remind_date <= now:
                remind_date += timedelta(days=1)
                
            chat_id = update.message.chat.id
            reminder = {
                'text': context.user_data['task_text'],
                'author': update.message.from_user.first_name,
                'datetime': remind_date,
                'chat_id': chat_id,
                'resends': 0,
                'max_resends': 10
            }
            
            if chat_id not in reminders:
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(f"✅ Запланировано на {remind_date.strftime('%d.%m %H:%M')}")
            del user_states[user_id]
        else:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`")

async def check_reminders(application):
    while True:
        try:
            now = datetime.now()
            for chat_id in list(reminders.keys()):
                if chat_id in reminders:
                    i = 0
                    while i < len(reminders[chat_id]):
                        reminder = reminders[chat_id][i]
                        if reminder['datetime'] <= now and reminder['resends'] < reminder['max_resends']:
                            keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                            await application.bot.send_message(
                                chat_id, 
                                f"🔔 {reminder['text']}\n👤 {reminder['author']}",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode='Markdown'
                            )
                            reminder['resends'] += 1
                            reminder['datetime'] += timedelta(seconds=20)
                        i += 1
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Check error: {e}")
            await asyncio.sleep(20)

@app.route('/')
def index():
    return "🚀 Bot OK!"

@app.route('/webhook', methods=['POST'])
def webhook():
    global application
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.create_task(application.process_update(update))
        return 'OK'
    except Exception as e:
        print(f"❌ Webhook: {e}")
        return 'Error', 500

def create_application():
    global application
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден!")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск фоновой задачи
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    threading.Thread(target=lambda: loop.run_until_complete(check_reminders(application)), daemon=True).start()
    
    return application

if __name__ == '__main__':
    create_application()
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)






