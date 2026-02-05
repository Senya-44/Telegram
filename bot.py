import re
import logging
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import threading
import time

# ТОКЕН В КОДЕ (НЕ Environment!)
TOKEN = '8598694238:AAHMaIHIXjGpIxHDTZIoGqgjMQalARlmhLs'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

reminders = {}
user_states = {}

def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

async def start(update, context):
    chat = update.message.chat
    user = update.message.from_user
    print(f"🚀 /start от {user.first_name} (ID:{user.id}) в {chat.id}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔔 Создать напоминание для чата!", reply_markup=reply_markup)

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    
    print(f"🔘 Пользователь {user_id} нажал '{query.data}'")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text("📝 Напишите задачу:")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            if chat_id in reminders and len(reminders[chat_id]) > index:
                removed = reminders[chat_id].pop(index)
                await query.edit_message_text(f"✅ '{removed['text']}' остановлено!")
                print(f"🛑 Удалено: {removed['text']}")
        except:
            await query.edit_message_text("❌ Ошибка!")

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
        try:
            day, month, hour, minute = map(int, re.match(r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', update.message.text.strip()).groups())
            now = datetime.now()
            remind_time = now.replace(day=day, month=month, hour=hour, minute=minute)
            if remind_time <= now: remind_time += timedelta(days=1)
            
            reminder = {'text': context.user_data['task'], 'time': remind_time, 'sends': 0}
            
            if chat_id not in reminders: reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(f"✅ Напоминание **{reminder['text']}** в {remind_time.strftime('%H:%M')}", parse_mode='Markdown')
            del user_states[user_id]
            print(f"✅ Создана задача для {chat_id}")
        except:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`")

def reminder_thread(app):
    """🔥 ОТДЕЛЬНЫЙ ТРЕД для напоминаний (НЕ блокирует бот!)"""
    print("🔄 Поток напоминаний запущен")
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
                            print(f"🔔 Напоминание #{task['sends']}")
                        except Exception as e:
                            print(f"❌ Ошибка отправки: {e}")
                    elif task['sends'] >= 3:
                        tasks.pop(i)
            time.sleep(10)  # Проверяем каждые 10 сек
        except Exception as e:
            print(f"❌ Поток ошибки: {e}")
            time.sleep(10)

def main():
    print("🚀 Telegram Reminder Bot v2.0")
    print(f"📱 Токен: {TOKEN[:20]}...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    # 🔥 Запуск потока напоминаний в ОТДЕЛЬНОМ ТРЕДЕ
    reminder_worker = threading.Thread(target=reminder_thread, args=(app,), daemon=True)
    reminder_worker.start()
    
    print("✅ Бот готов! Отправьте /start")
    print("🔄 Напоминания каждые 10 сек")
    
    # 🔥 ПРОСТОЙ run_polling БЕЗ asyncio.run()!
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()






