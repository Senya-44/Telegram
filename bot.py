import re
import logging
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден!")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилища
reminders = {}
user_states = {}

async def start(update, context):
    """🔥 /start"""
    user = update.message.from_user
    chat = update.message.chat
    
    print(f"🚀 /start от {user.first_name} ({user.id}) в {chat.id}")
    
    keyboard = [[InlineKeyboardButton("📝 Создать задачу", callback_data='create_task')]]
    await update.message.reply_text(
        f"✅ **Привет, {user.first_name}!** 🔔\n\n"
        f"**МНОГОПОЛЬЗОВАТЕЛЬСКИЙ НАПОМИНАТЕЛЬ**\n\n"
        f"👥 Работает в **ЛС** и **группах**\n"
        f"🔔 Напоминает **ВСЕМ участникам**",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def button_handler(update, context):
    """🔥 Кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    print(f"🔘 {query.data} от {user_id}")
    
    if query.data == 'create_task':
        user_states[user_id] = 'waiting_task'
        await query.edit_message_text(
            "📝 **Напиши задачу для чата:**\n\n"
            "❗ **ВСЕ участники** увидят напоминание!"
        )
    
    elif query.data.startswith('stop_'):
        try:
            index = int(query.data.split('_')[1])
            chat_id = query.message.chat.id
            if chat_id in reminders and len(reminders[chat_id]) > index:
                reminders[chat_id].pop(index)
                await query.edit_message_text("✅ **Напоминание остановлено!**")
                print(f"🛑 #{index} удалено")
        except:
            await query.edit_message_text("❌ Ошибка!")

async def handle_message(update, context):
    """🔥 Сообщения"""
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
            f"✅ **Задача '{text}' принята!**\n\n"
            f"⏰ **Когда напомнить ВСЕМ?**\n"
            f"`дд.мм чч:мм`",
            parse_mode='Markdown'
        )
    
    elif state == 'waiting_time':
        try:
            pattern = r'(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
            match = re.match(pattern, text.strip())
            if not match:
                await update.message.reply_text("❌ **Формат: `дд.мм чч:мм`**", parse_mode='Markdown')
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
                f"✅ **{user_name} запланировал!**\n\n"
                f"📋 **{reminder['text']}**\n"
                f"⏰ **{remind_date.strftime('%d.%m %H:%M')}**\n"
                f"🔄 **10 повторений** по 20 сек\n"
                f"🛑 **Любой может остановить**",
                parse_mode='Markdown'
            )
            del user_states[user_id]
            print(f"✅ Напоминание: {reminder['text']}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await update.message.reply_text("❌ **Формат: `дд.мм чч:мм`**", parse_mode='Markdown')

async def check_reminders(app):
    """🔥 Фоновая проверка"""
    print("🔄 **ПРОВЕРКА НАПОМИНАНИЙ запущена**")
    
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
                                await app.bot.send_message(
                                    chat_id,
                                    f"🔔 **#{reminder['resends'] + 1}/{reminder['max_resends']}**\n\n"
                                    f"📋 **{reminder['text']}**\n"
                                    f"👤 **{reminder['author']}**",
                                    reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode='Markdown'
                                )
                                reminder['resends'] += 1
                                print(f"🔔 #{reminder['resends']} в {chat_id}")
                            except Exception as e:
                                print(f"❌ Отправка: {e}")
                        else:
                            del reminders_list[i]
                            continue
                    i += 1
            
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Проверка: {e}")
            await asyncio.sleep(20)

async def main():
    print("🚀 **МНОГОПОЛЬЗОВАТЕЛЬСКИЙ БОТ ПОЛЛИНГ**")
    print(f"✅ Токен: {BOT_TOKEN[:5]}...{BOT_TOKEN[-3:]}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(check_reminders(app))
    
    print("✅ **ЗАПУЩЕН!** Тест: `/start`")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановлен")






