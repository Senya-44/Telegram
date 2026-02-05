import re
import logging
import threading
import time
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = '8598694238:AAHMaIHIXjGpIxHDTZIoGqgjMQalARlmhLs'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

reminders = {}
user_states = {}

def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} (ID:{user.id})")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔔 Создать напоминание!", reply_markup=reply_markup)

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    
    print(f"🔘 {query.data} от {user_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        query.edit_message_text("📝 Напишите задачу:")
    
    elif query.data.startswith('stop_'):
        index = int(query.data.split('_')[1])
        if chat_id in reminders and len(reminders[chat_id]) > index:
            removed = reminders[chat_id].pop(index)
            query.edit_message_text(f"✅ '{removed['text']}' остановлено!")
            print(f"🛑 Удалено: {removed['text']}")

def handle_message(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task'] = update.message.text
        user_states[user_id] = 'waiting_time'
        update.message.reply_text("✅ **Задача принята!**\n⏰ `дд.мм чч:мм`", parse_mode='Markdown')
    
    elif state == 'waiting_time':
        try:
            # ✅ ПРАВИЛЬНЫЙ regex!
            day, month, hour, minute = map(int, re.match(r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', update.message.text.strip()).groups())
            now = datetime.now()
            remind_time = now.replace(day=day, month=month, hour=hour, minute=minute)
            if remind_time <= now: 
                remind_time += timedelta(days=1)
            
            reminder = {'text': context.user_data['task'], 'time': remind_time, 'sends': 0}
            
            if chat_id not in reminders: 
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            update.message.reply_text(f"✅ **{reminder['text']}** в {remind_time.strftime('%H:%M')}", parse_mode='Markdown')
            del user_states[user_id]
            print(f"✅ Задача: {reminder['text']} → {remind_time.strftime('%H:%M')}")
        except:
            update.message.reply_text("❌ Формат: `дд.мм чч:мм`")

def reminder_checker(app):
    """🔥 ОТДЕЛЬНЫЙ ТРЕД для напоминаний"""
    print("🔄 Напоминания запущены в фоне!")
    while True:
        try:
            now = datetime.now()
            for chat_id, tasks in list(reminders.items()):
                for i, task in enumerate(tasks[:]):
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
                            print(f"🔔 #{task['sends']}: {task['text']}")
                        except Exception as e:
                            print(f"❌ Send error: {e}")
                    elif task['sends'] >= 3:
                        tasks.pop(i)
            time.sleep(10)
        except Exception as e:
            print(f"❌ Checker: {e}")
            time.sleep(10)

def main():
    print("🚀 Telegram Reminder Bot v6.0 (Render)")
    print(f"📱 Токен: {TOKEN[:20]}...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 🔥 Запуск напоминаний в ОТДЕЛЬНОМ ТРЕДЕ
    reminder_thread = threading.Thread(target=reminder_checker, args=(app,), daemon=True)
    reminder_thread.start()
    
    print("✅ Бот + напоминания готовы!")
    print("🔄 Тред напоминаний запущен")
    
    # 🔥 ОСНОВНОЙ polling НЕ блокируется!
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
