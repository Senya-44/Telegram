import os
from flask import Flask, request
import threading
from telegram import Update
from telegram.ext import Application

# ... ваш существующий код остается БЕЗ ИЗМЕНЕНИЙ до main() ...

def run_check_reminders(application):
    """Запуск фоновой задачи в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_reminders(application))

def create_app():
    """Создание Flask приложения"""
    app = Flask(__name__)
    
    # 🔥 Получаем токен из переменных окружения
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")
    
    application = Application.builder().token(TOKEN).build()
    
    # 🔥 Регистрируем все handlers (ваш код без изменений)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # 🔥 Webhook endpoint
    @app.route(f'/{TOKEN}', methods=['POST'])
    def webhook():
        try:
            update = Update.de_json(request.get_json(force=True), application.bot)
            application.process_update(update)
            return 'OK'
        except Exception as e:
            print(f"❌ Webhook error: {e}")
            return 'Error', 500
    
    # 🔥 Health check
    @app.route('/')
    def index():
        return "🚀 Reminder Bot работает!"
    
    # 🔥 Запуск фоновой проверки напоминаний
    reminder_thread = threading.Thread(target=run_check_reminders, args=(application,), daemon=True)
    reminder_thread.start()
    
    print("🚀 🔥 Webhook бот готов к запуску!")
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)




