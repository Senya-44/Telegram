import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# Глобальные хранилища
reminders = {}
user_states = {}

app = FastAPI()

# Хендлеры бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} ({user.id})")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу ВСЕМ участникам чата!",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'create_task':
        user_states[query.from_user.id] = 'waiting_task'
        await query.edit_message_text("📝 Напиши задачу для чата")
    
    elif query.data.startswith('stop_'):
        index = int(query.data.split('_')[1])
        chat_id = query.message.chat.id
        if chat_id in reminders and len(reminders[chat_id]) > index:
            reminders[chat_id].pop(index)
            await query.edit_message_text("✅ Напоминание остановлено!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    chat_id = update.message.chat.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
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
                'chat_id': chat_id,
                'resends': 0,
                'max_resends': 10
            }
            
            if chat_id not in reminders:
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(
                f"✅ Напоминание создано!\n📋 **{reminder['text']}**\n⏰ {remind_date.strftime('%d.%m %H:%M')}",
                parse_mode='Markdown'
            )
            del user_states[user_id]
            
        except:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')

async def check_reminders(application):
    print("🔄 Фоновая проверка напоминаний...")
    while True:
        try:
            now = datetime.now()
            for chat_id in list(reminders.keys()):
                reminders_list = reminders[chat_id]
                i = 0
                while i < len(reminders_list):
                    reminder = reminders_list[i]
                    if reminder['datetime'] <= now and reminder['resends'] < reminder['max_resends']:
                        keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                        await application.bot.send_message(
                            chat_id,
                            f"🔔 **#{reminder['resends']+1}/10**\n📋 {reminder['text']}",
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
            print(f"❌ Check error: {e}")
            await asyncio.sleep(20)

# Webhook endpoint
@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), app.bot)
    await application.process_update(update)
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Главная функция
async def main():
    global application
    print("🚀 Инициализация...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация хендлеров
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Установка webhook
    await application.bot.set_webhook(url="https://telegram-c3es.onrender.com/webhook")
    print("✅ Webhook установлен!")
    
    # Запуск фоновой проверки
    asyncio.create_task(check_reminders(application))
    
    # Запуск FastAPI
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())





