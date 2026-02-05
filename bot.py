import re
import logging
import os
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

reminders = {}
user_states = {}

async def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} (ID:{user.id}) в чате {chat.id}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔔 Создать напоминание для чата!", reply_markup=reply_markup)

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text("📝 Напишите задачу:")
    
    elif query.data.startswith('stop_'):
        index = int(query.data.split('_')[1])
        if chat_id in reminders and len(reminders[chat_id]) > index:
            removed = reminders[chat_id].pop(index)
            await query.edit_message_text(f"✅ '{removed['text']}' остановлено!")
            print(f"🛑 Остановлено: {removed['text']}")

async def handle_message(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        return
        
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task'] = update.message.text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text("✅ **Задача принята!**\n⏰ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
    
    elif state == 'waiting_time':
        time_text = update.message.text.strip()
        try:
            day, month, hour, minute = map(int, re.match(r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', time_text).groups())
            now = datetime.now()
            remind_time = now.replace(day=day, month=month, hour=hour, minute=minute)
            if remind_time <= now: remind_time += timedelta(days=1)
            
            reminder = {'text': context.user_data['task'], 'time': remind_time, 'sends': 0}
            
            if chat_id not in reminders: reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(f"✅ Напоминание: **{reminder['text']}** в {remind_time.strftime('%H:%M')}")
            del user_states[user_id]
            print(f"✅ Задача добавлена: {chat_id}")
            
        except:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`")

async def reminder_checker(application):
    """🔥 Render-safe проверка напоминаний"""
    while True:
        try:
            now = datetime.now()
            for chat_id, tasks in list(reminders.items()):
                for i, task in enumerate(tasks[:]):
                    if task['time'] <= now and task['sends'] < 3:  # 3 повтора
                        keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                        await application.bot.send_message(
                            chat_id, 
                            f"🔔 **#{task['sends']+1}/3** {task['text']}",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                        task['sends'] += 1
                        task['time'] += timedelta(seconds=30)  # Следующее через 30 сек
                    elif task['sends'] >= 3:
                        tasks.pop(i)
            await asyncio.sleep(10)  # Проверяем каждые 10 сек
        except Exception as e:
            print(f"❌ Checker error: {e}")
            await asyncio.sleep(10)

async def main():
    token = os.getenv('8598694238:AAHMaIHIXjGpIxHDTZIoGqgjMQalARlmhLs')
    if not token:
        print("❌ Нет TOKEN в Environment!")
        return
        
    print(f"🚀 Запуск с токеном...{token[:10]}")
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 🔥 Запуск фоновой проверки
    asyncio.create_task(reminder_checker(app))
    
    print("✅ Бот запущен! Ждем команды /start")
    await app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())



