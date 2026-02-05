import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# 🔥 Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавьте в .env файл")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# 🔥 МНОГОПОЛЬЗОВАТЕЛЬСКИЕ хранилища
reminders = {}
user_states = {}  # user_id → состояние


async def error_handler(update, context):
    """🔥 Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")


async def start(update, context):
    """🔥 /start ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ"""
    chat = update.message.chat
    user = update.message.from_user
    
    # 🔥 ДЕТАЛЬНЫЕ ЛОГИ ДЛЯ ОТЛАДКИ
    print(f"🚀 /start от {user.first_name} (@{user.username or 'no_username'})")
    print(f"   👤 ID: {user.id}")
    print(f"   📱 Чат: {chat.id} ({chat.type})")
    
    if chat.type in ['private', 'group', 'supergroup']:
        keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"Привет, {user.first_name}! 🔔\n\n"
            "Я напомню задачу **ВСЕМ участникам чата**!\n\n"
            f"👥 Чат: {'Группа' if chat.type in ['group', 'supergroup'] else 'ЛС'}"
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        print(f"✅ ОТВЕТИЛ {user.id} в чате {chat.id}")
    else:
        print(f"❌ Чат {chat.type} не поддерживается")


async def button_handler(update, context):
    """🔥 Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    
    print(f"🔘 {user_name} (ID:{user_id}) нажал '{query.data}' в чате {chat_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text(
            f"📝 {user_name}, напиши задачу для чата {chat_id}:\n"
            "(все участники увидят напоминание)"
        )
    
    elif query.data.startswith('stop_'):
        """🛑 ПОЛНАЯ ОСТАНОВКА"""
        try:
            index = int(query.data.split('_')[1])
            print(f"🛑 {user_name} останавливает #{index} в чате {chat_id}")
            
            if chat_id in reminders and len(reminders[chat_id]) > index:
                removed_reminder = reminders[chat_id].pop(index)
                await query.edit_message_text(
                    f"✅ {user_name} остановил напоминание!\n\n"
                    f"📋 **{removed_reminder['text']}**\n"
                    f"🛑 Было отправлено {removed_reminder['resends']} раз",
                    parse_mode='Markdown'
                )
                print(f"✅ 🛑 {user_name} УДАЛИЛ напоминание #{index}")
            else:
                await query.edit_message_text("❌ Напоминание уже удалено!")
        except (ValueError, IndexError) as e:
            await query.edit_message_text("❌ Ошибка остановки!")
            print(f"❌ Ошибка кнопки: {e}")


async def handle_message(update, context):
    """🔥 МНОГОПОЛЬЗОВАТЕЛЬСКАЯ обработка сообщений"""
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    print(f"💬 {user_name} (ID:{user_id}) в чате {chat_id}: '{update.message.text}'")
    
    # 🔥 ПРОВЕРЯЕМ состояние ТОЛЬКО этого пользователя
    if user_id not in user_states:
        print(f"⏳ {user_name} не в диалоге, игнорируем")
        return
    
    state = user_states[user_id]
    
    if state == 'waiting_task':
        context.user_data['task_text'] = update.message.text
        context.user_data['chat_id'] = chat_id
        user_states[user_id] = 'waiting_time'
        await update.message.reply_text(
            f"✅ **Задача '{update.message.text}' принята, {user_name}!**\n"
            f"⏰ Когда напомнить ВСЕМ в чат?\n"
            f"Формат: `дд.мм чч:мм`", 
            parse_mode='Markdown'
        )
        print(f"✅ Задача '{update.message.text}' принята от {user_id}")
    
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
            remind_date = now.replace(day=day, month=month, hour=hour, minute=minute, second=0)
            
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
            
            reminder_index = len(reminders[chat_id]) - 1
            
            await update.message.reply_text(
                f"✅ {user_name} запланировал напоминание!\n\n"
                f"📋 **{context.user_data['task_text']}**\n"
                f"⏰ {remind_date.strftime('%d.%m %H:%M')}\n"
                f"🔄 10 повторений по 20 сек\n"
                f"🛑 Любой участник может остановить",
                parse_mode='Markdown'
            )
            print(f"✅ Напоминание #{reminder_index} от {user_name} в {chat_id}")
            
            # 🔥 ОЧИЩАЕМ состояние ТОЛЬКО этого пользователя
            del user_states[user_id]
            
        except Exception as e:
            await update.message.reply_text("❌ Формат: `дд.мм чч:мм`", parse_mode='Markdown')
            print(f"❌ Ошибка парсинга времени: {e}")


async def check_reminders(application):
    """🔥 НАДЕЖНАЯ МНОГОПОЛЬЗОВАТЕЛЬСКАЯ проверка"""
    print("🔄 Запуск фоновой задачи напоминаний...")
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
                                
                                msg = (
                                    f"🔔 **#{reminder['resends'] + 1}/{reminder['max_resends']}**\n\n"
                                    f"📋 {reminder['text']}\n"
                                    f"👤 {reminder['author']}\n"
                                    f"⏰ {now.strftime('%H:%M')}"
                                )
                                
                                await application.bot.send_message(
                                    chat_id, msg, parse_mode='Markdown', reply_markup=reply_markup
                                )
                                reminder['resends'] += 1
                                print(f"🔔 Чат {chat_id}: #{reminder['resends']}/{reminder['max_resends']} от {reminder['author']}")
                            except Exception as e:
                                print(f"❌ Ошибка отправки {chat_id}: {e}")
                        else:
                            print(f"✅ Напоминание завершено в {chat_id}")
                            del reminders_list[i]
                            continue
                    i += 1
            
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            await asyncio.sleep(20)


def main():
    """🔥 ГЛАВНАЯ ФУНКЦИЯ"""
    print("🚀 Инициализация бота...")
    print(f"✅ Токен загружен: {'*' * len(BOT_TOKEN[:5]) + BOT_TOKEN[-3:]}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 🔥 РЕГИСТРАЦИЯ для ВСЕХ пользователей
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print("🚀 🔥 МНОГОПОЛЬЗОВАТЕЛЬСКИЙ бот запущен!")
    print("📢 /start@BotName в ЛС и ГРУППАХ!")
    print("👥 РАБОТАЕТ для ВСЕХ участников!")
    
    # 🔥 Запуск фоновой задачи
    loop = asyncio.get_event_loop()
    loop.create_task(check_reminders(application))
    
    # 🔥 Запуск polling
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()






