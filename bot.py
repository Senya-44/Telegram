import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

# Глобальные переменные
application = None
bot = Bot(token=BOT_TOKEN)
reminders = {}
user_states = {}

app = FastAPI()

# 🔥 ХЕНДЛЕРЫ БОТА
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} ({user.id}) в {chat.id}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу **ВСЕМ участникам чата**!",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    
    print(f"🔘 {query.data} от {user_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text("📝 Напиши задачу для чата (все увидят)")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            if chat_id in reminders and len(reminders[chat_id]) > index:
                reminders[chat_id].pop(index)
                await query.edit_message_text("✅ Напоминание остановлено!")
        except:
            await query.edit_message_text("❌ Ошибка!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    chat_id = update.message.chat.id
    user_name = update.message.from_user.first_name
    
    print(f"💬 {user_name} ({user_id}): {text}")
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text(
            f"✅ Задача '{text}' принята, {user_name}!\n\n⏰ Когда напомнить?\nФормат: `дд.мм чч:мм`",
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
                'author': user_name,
                'datetime': remind_date,
                'chat_id': chat_id,
                'resends': 0,
                'max_resends': 10
            }
            
            if chat_id not in reminders:
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(
                f"✅ {user_name} создал напоминание!\n\n📋 **{reminder['text']}**\n⏰ {remind_date.strftime('%d.%m %H:%M')}\n🔄 10 повторений",
                parse_mode='Markdown'
            )
            del user_states[user_id]
            print(f"✅ Напоминание создано: {reminder['text']}")
            
        except Exception as e:
            print(f"❌ Парсинг времени: {e}")
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')

async def check_reminders():
    """Фоновая проверка напоминаний"""
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
                        await bot.send_message(
                            chat_id,
                            f"🔔 **#{reminder['resends']+1}/{reminder['max_resends']}**\n\n📋 {reminder['text']}\n👤 {reminder['author']}",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                        reminder['resends'] += 1
                        print(f"🔔 #{reminder['resends']} в {chat_id}")
                    elif reminder['resends'] >= reminder['max_resends']:
                        del reminders_list[i]
                        continue
                    i += 1
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Check error: {e}")
            await asyncio.sleep(20)

# ✅ ИСПРАВЛЕННЫЙ WEBHOOK
@app.post("/webhook")
async def webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot)
        if update:
            await application.process_update(update)
        return {"ok": True}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "bot": "running"}

# ✅ ИНИЦИАЛИЗАЦИЯ
async def main():
    global application
    print("🚀 Инициализация бота...")
    
    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Устанавливаем webhook
    webhook_url = "https://telegram-c3es.onrender.com/webhook"
    await bot.set_webhook(url=webhook_url)
    webhook_info = await bot.get_webhook_info()
    print(f"✅ Webhook: {webhook_info.url}")
    
    # Запускаем фоновую проверку
    asyncio.create_task(check_reminders())
    
    # Запуск сервера
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())






