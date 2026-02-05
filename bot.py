import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Загрузка токена
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в переменных окружения!")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные хранилища
reminders = {}
user_states = {}

async def start(update, context):
    """Команда /start"""
    chat = update.message.chat
    user = update.message.from_user
    
    print(f"🚀 /start от {user.first_name} ({user.id}) в чате {chat.id}")
    
    if chat.type in ['private', 'group', 'supergroup']:
        keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"Привет, {user.first_name}! 🔔\n\nЯ напомню задачу **ВСЕМ участникам чата**!"
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update, context):
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    user_name = query.from_user.first_name
    
    print(f"🔘 {user_name} нажал: {query.data}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text(
            f"📝 {user_name}, напиши задачу:\n"
            "(все участники чата увидят напоминание)"
        )
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            if chat_id in reminders and len(reminders[chat_id]) > index:
                removed = reminders[chat_id].pop(index)
                await query.edit_message_text(
                    f"✅ {user_name} остановил напоминание!\n\n"
                    f"📋 **{removed['text']}**\n"
                    f"Отправлено {removed['resends']} раз",
                    parse_mode='Markdown'
                )
                print(f"🛑 Напоминание #{index} удалено")
            else:
                await query.edit_message_text("❌ Напоминание уже удалено")
        except Exception as e:
            await query.edit_message_text("❌ Ошибка остановки")
            print(f"❌ Ошибка кнопки: {e}")

async def handle_message(update, context):
    """Обработка текстовых сообщений"""
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    text = update.message.text
    
    print(f"💬 {user_name} ({user_id}): {text}")
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = text
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text(
            f"✅ Задача '{text}' принята!\n\n"
            f"⏰ Когда напомнить всем?\n"
            f"Формат: `дд.мм чч:мм`", 
            parse_mode='Markdown'
        )
    
    elif state == 'waiting_time':
        time_text = text.strip()
        try:
            # Парсинг дд.мм чч:мм
            pattern = r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
            match = re.match(pattern, time_text)
            if not match:
                await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
                return
            
            day, month, hour, minute = map(int, match.groups())
            now = datetime.now()
            
            # Создаем дату
            remind_date = datetime(now.year, month, day, hour, minute)
            if remind_date <= now:
                remind_date += timedelta(days=1)
            
            # Создаем напоминание
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
                f"✅ {user_name} создал напоминание!\n\n"
                f"📋 **{reminder['text']}**\n"
                f"⏰ {remind_date.strftime('%d.%m %H:%M')}\n"
                f"🔄 10 повторений каждые 20 сек",
                parse_mode='Markdown'
            )
            
            # Очищаем состояние
            del user_states[user_id]
            print(f"✅ Напоминание создано: {reminder['text']}")
            
        except Exception as e:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
            print(f"❌ Ошибка времени: {e}")

async def check_reminders(application):
    """Фоновая проверка напоминаний"""
    print("🔄 Запущена проверка напоминаний...")
    
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
                    
                    if reminder['datetime'] <= now:
                        if reminder['resends'] < reminder['max_resends']:
                            try:
                                keyboard = [[InlineKeyboardButton("🛑 Стоп", callback_data=f'stop_{i}')]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                
                                message = (
                                    f"🔔 **#{reminder['resends'] + 1}/{reminder['max_resends']}**\n\n"
                                    f"📋 {reminder['text']}\n"
                                    f"👤 {reminder['author']}\n"
                                    f"⏰ {now.strftime('%H:%M')}"
                                )
                                
                                await application.bot.send_message(
                                    chat_id, message, 
                                    parse_mode='Markdown', 
                                    reply_markup=reply_markup
                                )
                                reminder['resends'] += 1
                                print(f"🔔 Отправлено в {chat_id}: #{reminder['resends']}")
                                
                            except Exception as e:
                                print(f"❌ Ошибка отправки в {chat_id}: {e}")
                        else:
                            print(f"✅ Напоминание завершено в {chat_id}")
                            del reminders_list[i]
                            continue
                    i += 1
            
            await asyncio.sleep(20)  # Проверка каждые 20 сек
            
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            await asyncio.sleep(20)

async def main():
    """Главная функция"""
    print("🚀 Запуск бота...")
    print(f"✅ Токен: {BOT_TOKEN[:5]}...{BOT_TOKEN[-3:]}")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем фоновую задачу
    asyncio.create_task(check_reminders(application))
    
    print("✅ Бот запущен! /start в ЛС или группах")
    
    # Запуск polling
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")






