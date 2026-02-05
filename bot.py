import re
import logging
import time
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# ТОКЕН В КОДЕ!
TOKEN = '8598694238:AAHMaIHIXjGpIxHDTZIoGqgjMQalARlmhLs'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

reminders = {}
user_states = {}

def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} (ID:{user.id}) в {chat.id}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔔 Создать напоминание для чата!", reply_markup=reply_markup)

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    
    print(f"🔘 {user_id} нажал '{query.data}'")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        query.edit_message_text("📝 Напишите задачу:")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            if chat_id in reminders and len(reminders[chat_id]) > index:
                removed = reminders[chat_id].pop(index)
                query.edit_message_text(f"✅ '{removed['text']}' остановлено!")
                print(f"🛑 Удалено: {removed['text']}")
        except:
            query.edit_message_text("❌ Ошибка!")

def handle_message(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task'] = update.message.text
        user_states[user_id] = 'waiting_time'
        update.message.reply_text("✅ **Задача принята!**\n⏰ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
    
    elif state == 'waiting_time':
        try:
            day, month, hour, minute = map(int, re.match(r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', update.message.text.strip()).groups())
            now = datetime.now()
            remind_time = now.replace(day=day, month=month, hour=hour, minute=minute)
            if remind_time <= now: remind_time += timedelta(days=1)
            
            reminder = {'text': context.user_data['task'], 'time': remind_time, 'sends': 0}
            
            if chat_id not in reminders: 
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            update.message.reply_text(f"✅ Напоминание **{reminder['text']}** в {remind_time.strftime('%H:%M')}", parse_mode='Markdown')
            del user_states[user_id]
            print(f"✅ Задача для {chat_id}: {reminder['text']}")
        except:
            update.message.reply_text("❌ Формат: `дд.мм чч:мм`")

def check_reminders(app):
    """🔥 СИНХРОННАЯ проверка напоминаний в цикле"""
    print("🔄 Проверка напоминаний запущена")
    while True:
        try:
            now = datetime.now()
            for chat_id, tasks in list(reminders.items()):
                i = 0
                while i < len(tasks):
                    task = tasks[i]
                    if task['time'] <= now and task['sends'] < 3:
                        try:
                            keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                            app.bot.send_message(
                                chat_id, 
                                f"🔔 **#{task['sends']+1}/3** {task['text']}",
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode='Markdown'
                            )
                            task['sends'] += 1
                            task['time'] += timedelta(seconds=30)
                            print(f"🔔 #{task['sends']}/3: {task['text']}")
                        except TelegramError as e:
                            print(f"❌ Telegram ошибка: {e}")
                        i += 1
                    elif task['sends'] >= 3:
                        print(f"✅ Завершено: {task['text']}")
                        del tasks[i]
                    else:
                        i += 1
            time.sleep(10)
        except Exception as e:
            print(f"❌ Checker: {e}")
            time.sleep(10)

def main():
    print("🚀 Telegram Reminder Bot v3.0 (Render)")
    print(f"📱 Токен: {TOKEN[:20]}...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 🔥 Запуск проверки напоминаний в отдельном процессе
    import multiprocessing
    reminder_process = multiprocessing.Process(target=check_reminders, args=(app,), daemon=True)
    reminder_process.start()
    
    print("✅ Бот готов! /start")
    print("🔄 Напоминания каждые 10 сек")
    
    # 🔥 ПРОСТОЙ БЕЗОШИБНЫЙ polling
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()








