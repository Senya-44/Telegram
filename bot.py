import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные хранилища
reminders = {}
user_states = {}

async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

async def start(update, context):
    """🔥 /start для всех пользователей"""
    chat = update.message.chat
    user = update.message.from_user
    
    print(f"🚀 /start от {user.first_name} (ID:{user.id}) в чате {chat.id} ({chat.type})")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🔔\n\n"
        "Я напомню задачу ВСЕМ в чате!\n"
        f"👥 {'Группа' if chat.type in ['group', 'supergroup'] else 'Личный чат'}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update, context):
    """🔥 Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    
    print(f"🔘 {user_name} (ID:{user_id}) нажал '{query.data}' в {chat_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text(f"📝 {user_name}, напишите задачу для чата:")
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            print(f"🛑 {user_name} останавливает задачу #{index}")
            
            if chat_id in reminders and len(reminders[chat_id]) > index:
                removed = reminders[chat_id].pop(index)
                await query.edit_message_text(
                    f"✅ {user_name} остановил напоминание!\n\n"
                    f"📋 **{removed['text']}**\n"
                    f"🛑 Было отправлено {removed['sends']} раз",
                    parse_mode='Markdown'
                )
                print(f"✅ Удалена задача: {removed['text']}")
            else:
                await query.edit_message_text("❌ Напоминание уже удалено!")
        except:
            await query.edit_message_text("❌ Ошибка остановки!")

async def handle_message(update, context):
    """🔥 Многопользовательская обработка"""
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    print(f"💬 {user_name} (ID:{user_id}): '{update.message.text}'")
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = update.message.text
        context.user_data['chat_id'] = chat_id
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text(
            f"✅ **Задача '{update.message.text}' принята, {user_name}!**\n"
            f"⏰ Когда напомнить ВСЕМ?\n"
            f"Формат: `дд.мм чч:мм`", 
            parse_mode='Markdown'
        )
    
    elif state == 'waiting_time':
        time_text = update.message.text.strip()
        try:
            pattern = r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
            match = re.match(pattern, time_text)
            if not match:
                await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
                return
            
            day, month, hour, minute = map(int, match.groups())
            now = datetime.now()
            remind_time = now.replace(day=day, month=month, hour=hour, minute=minute, second=0)
            
            if remind_time <= now:
                remind_time += timedelta(days=1)
            
            reminder = {
                'text': context.user_data['task_text'],
                'author': user_name,
                'datetime': remind_time,
                'chat_id': chat_id,
                'sends': 0,
                'max_sends': 5  # 5 повторений
            }
            
            if chat_id not in reminders:
                reminders[chat_id] = []
            reminders[chat_id].append(reminder)
            
            await update.message.reply_text(
                f"✅ {user_name} запланировал напоминание!\n\n"
                f"📋 **{context.user_data['task_text']}**\n"
                f"⏰ {remind_time.strftime('%d.%m %H:%M')}\n"
                f"🔄 5 повторений по 30 сек\n"
                f"🛑 Любой может остановить",
                parse_mode='Markdown'
            )
            print(f"✅ Напоминание создано для чата {chat_id}")
            
            del user_states[user_id]
            
        except Exception as e:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
            print(f"❌ Ошибка времени: {e}")

async def reminder_checker(application):
    """🔥 Render-safe фоновый чекер напоминаний"""
    print("🔄 Фоновая проверка напоминаний запущена")
    while True:
        try:
            now = datetime.now()
            
            for chat_id in list(reminders.keys()):
                if chat_id not in reminders:
                    continue
                    
                tasks = reminders[chat_id]
                i = 0
                while i < len(tasks):
                    task = tasks[i]
                    
                    if task['datetime'] <= now and task['sends'] < task['max_sends']:
                        try:
                            keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            msg = (
                                f"🔔 **#{task['sends'] + 1}/{task['max_sends']}**\n\n"
                                f"📋 {task['text']}\n"
                                f"👤 {task['author']}\n"
                                f"⏰ {now.strftime('%H:%M')}"
                            )
                            
                            await application.bot.send_message(
                                chat_id, msg, 
                                parse_mode='Markdown', 
                                reply_markup=reply_markup
                            )
                            task['sends'] += 1
                            task['datetime'] += timedelta(seconds=30)  # Следующее через 30 сек
                            print(f"🔔 Отправлено #{task['sends']}/{task['max_sends']} для {chat_id}")
                            
                        except Exception as e:
                            print(f"❌ Ошибка отправки в {chat_id}: {e}")
                    
                    elif task['sends'] >= task['max_sends']:
                        print(f"✅ Задача завершена: {task['text']}")
                        del tasks[i]
                        continue
                    
                    i += 1
            
            await asyncio.sleep(10)  # Чекаем каждые 10 сек
            
        except Exception as e:
            print(f"❌ Checker error: {e}")
            await asyncio.sleep(10)

async def main():
    """🔥 Главная функция для Render"""
    # Токен прямо в коде (для простоты деплоя)
    TOKEN = '8598694238:AAHMaIHIXjGpIxHDTZIoGqgjMQalARlmhLs'
    
    print(f"🚀 Запуск Telegram Reminder Bot...")
    print(f"📱 Токен: {TOKEN[:20]}...")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # 🔥 Запуск фонового чекера
    asyncio.create_task(reminder_checker(application))
    
    print("✅ Бот полностью готов! Отправьте /start")
    print("🔄 Напоминания проверяются каждые 10 сек")
    
    # Запуск polling
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())




