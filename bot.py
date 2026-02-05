import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден!")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
application = None
reminders = {}
user_states = {}

async def start(update, context):
    """🔥 /start команда"""
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} ({user.id}) в {chat.id}")
    
    if chat.type in ['private', 'group', 'supergroup']:
        keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
        await update.message.reply_text(
            f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу **ВСЕМ участникам чата**!",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    
    print(f"🔘 Кнопка {query.data} от {user_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text("📝 Напиши задачу для чата:\n(все увидят напоминание)")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            if chat_id in reminders and len(reminders[chat_id]) > index:
                reminders[chat_id].pop(index)
                await query.edit_message_text("✅ Напоминание остановлено!")
                print(f"🛑 Остановлено #{index}")
        except:
            await query.edit_message_text("❌ Ошибка!")

async def handle_message(update, context):
    user_id = update.message.from_user.id
    text = update.message.text
    chat_id = update.message.chat.id
    
    print(f"💬 {user_id}: {text}")
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text(
            f"✅ Задача '{text}' принята!\n\n⏰ Когда напомнить?\nФормат: `дд.мм чч:мм`",
            parse_mode='Markdown'
        )
    
    elif state == 'waiting_time':
        try:
            pattern = r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
            match = re.match(pattern, text.strip())
            if not match:
                await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
                return
            
            day, month, hour, minute = map(int, match.groups())
            now = datetime.now()
            remind_date = datetime(now.year, month, day, hour, minute)
            if remind_date <= now:
                remind_date += timedelta(days=1)
            
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
            
            await update.message.reply_text(
                f"✅ Напоминание создано!\n\n📋 **{reminder['text']}**\n⏰ {remind_date.strftime('%d.%m %H:%M')}",
                parse_mode='Markdown'
            )
            del user_states[user_id]
            print(f"✅ Создано напоминание: {reminder['text']}")
            
        except Exception as e:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
            print(f"❌ Парсинг времени: {e}")

async def check_reminders():
    """Фоновая проверка напоминаний"""
    global application
    print("🔄 Запуск проверки напоминаний...")
    
    while True:
        try:
            now = datetime.now()
            for chat_id in list(reminders.keys()):
                if chat_id not in reminders:
                    continue
                reminders_list = reminders[chat_id]
                i = 0
                while i < len(reminders_list):
                    reminder = reminders_list[i]
                    if reminder['datetime'] <= now and reminder['resends'] < reminder['max_resends']:
                        keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                        await application.bot.send_message(
                            chat_id,
                            f"🔔 **#{reminder['resends']+1}/{reminder['max_resends']}**\n\n📋 {reminder['text']}",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                        reminder['resends'] += 1
                        print(f"🔔 Напоминание #{reminder['resends']} в {chat_id}")
                    elif reminder['resends'] >= reminder['max_resends']:
                        del reminders_list[i]
                        continue
                    i += 1
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            await asyncio.sleep(20)

# FastAPI только для health-check (НЕ блокирует бот)
app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "bot": "polling"}

# 🔥 ОСНОВНОЙ ЗАПУСК БОТА (отдельно от FastAPI)
async def run_bot():
    global application
    print("🚀 Инициализация Telegram бота...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск фоновой проверки напоминаний
    asyncio.create_task(check_reminders())
    
    print("✅ Бот запущен! Тестируйте /start")
    
    # 🔥 ПОЛЛИНГ БОТА (основной цикл)
    await application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import threading
    
    # Запуск FastAPI в отдельном потоке (только для порта)
    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=10000, log_level="info")
    
    # FastAPI в фоне
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # Основной поток = Telegram бот
    asyncio.run(run_bot())





