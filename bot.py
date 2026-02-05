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

reminders = {}
user_states = {}

# FastAPI для Render (фейковый сервер)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск бота при старте
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация хендлеров
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск фоновой задачи напоминаний
    asyncio.create_task(check_reminders(application))
    
    yield
    # Остановка бота
    await application.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "bot": "running"}

# 🔥 ВСЕ ФУНКЦИИ БОТА (без изменений)
async def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.id}")
    
    if chat.type in ['private', 'group', 'supergroup']:
        keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
        await update.message.reply_text(
            f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу всем!",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'create_task':
        user_states[query.from_user.id] = 'waiting_task'
        await query.edit_message_text("📝 Напиши задачу для чата")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            chat_id = query.message.chat.id
            if chat_id in reminders and len(reminders[chat_id]) > index:
                reminders[chat_id].pop(index)
                await query.edit_message_text("✅ Напоминание остановлено!")
        except:
            await query.edit_message_text("❌ Ошибка")

async def handle_message(update, context):
    user_id = update.message.from_user.id
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    text = update.message.text
    
    if state == 'waiting_task':
        context.user_data['task_text'] = text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text("✅ Задача принята!\n⏰ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
    
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
                'chat_id': update.message.chat.id,
                'resends': 0,
                'max_resends': 10
            }
            
            if reminder['chat_id'] not in reminders:
                reminders[reminder['chat_id']] = []
            reminders[reminder['chat_id']].append(reminder)
            
            await update.message.reply_text(
                f"✅ Напоминание создано!\n📋 **{reminder['text']}**\n⏰ {remind_date.strftime('%d.%m %H:%M')}",
                parse_mode='Markdown'
            )
            del user_states[user_id]
            
        except:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')

async def check_reminders(application):
    print("🔄 Проверка напоминаний запущена")
    while True:
        try:
            now = datetime.now()
            for chat_id in list(reminders):
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
                            f"🔔 **#{reminder['resends']+1}/10**\n\n📋 {reminder['text']}",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                        reminder['resends'] += 1
                    elif reminder['resends'] >= reminder['max_resends']:
                        del reminders_list[i]
                        continue
                    i += 1
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    print("🚀 Запуск бота + HTTP сервера...")
    uvicorn.run(app, host="0.0.0.0", port=10000)




