import requests
import json
import os
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Загружаем переменные из .env файла
load_dotenv()

# Получаем переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_URL = os.getenv("PROXYAPI_URL")
CRYPTO_API_URL = os.getenv("CRYPTO_API_URL")
CRYPTO_IDS = os.getenv("CRYPTO_IDS", "bitcoin,ethereum,cardano").split(",")

# Глобальная переменная для хранения Chat ID
chat_id = None

class TradingBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    def get_crypto_data(self):
        """Получает данные о криптовалютах"""
        try:
            params = {
                'ids': ','.join(CRYPTO_IDS),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            response = requests.get(CRYPTO_API_URL, params=params)
            return response.json()
        except Exception as e:
            return f"Ошибка получения данных: {e}"
    
    def analyze_with_proxyapi(self, data):
        """Анализирует данные с помощью ProxyAPI"""
        try:
            prompt = f"""
            Проанализируй следующие данные о криптовалютах и дай краткий анализ:
            {json.dumps(data, indent=2, ensure_ascii=False)}
            
            Дай краткий анализ (2-3 предложения) на русском языке о текущем состоянии рынка.
            """
            
            headers = {
                "Authorization": f"Bearer {PROXYAPI_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200
            }
            
            response = requests.post(PROXYAPI_URL, headers=headers, json=payload)
            result = response.json()
            return result.get('choices', [{}])[0].get('message', {}).get('content', 'Ошибка анализа')
        except Exception as e:
            return f"Ошибка анализа: {e}"
    
    async def send_message(self, text):
        """Отправляет сообщение в Telegram"""
        global chat_id
        if chat_id is None:
            print("Chat ID не установлен. Отправьте боту любое сообщение.")
            return
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            print(f"Сообщение отправлено: {text[:50]}...")
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    async def hourly_analysis(self):
        """Выполняет анализ"""
        print("Выполняю анализ...")
        
        # Получаем данные
        crypto_data = self.get_crypto_data()
        if isinstance(crypto_data, str):
            await self.send_message(f"❌ {crypto_data}")
            return
        
        # Анализируем с помощью ProxyAPI
        analysis = self.analyze_with_proxyapi(crypto_data)
        
        # Формируем сообщение
        message = "📊 Анализ криптовалют\n\n"
        for coin, data in crypto_data.items():
            price = data.get('usd', 'N/A')
            change_24h = data.get('usd_24h_change', 'N/A')
            message += f"💰 {coin.upper()}: ${price:,.2f} ({change_24h:+.2f}%)\n"
        
        message += f"\n🤖 Анализ ИИ:\n{analysis}"
        
        # Отправляем сообщение
        await self.send_message(message)
    
    async def start_command(self, update: Update, context):
        """Обработчик команды /start"""
        global chat_id
        chat_id = update.effective_chat.id
        welcome_message = """
🤖 Добро пожаловать в Trading Bot!

Я анализирую криптовалюты и отправляю результаты.

📊 Сейчас анализирую: Bitcoin, Ethereum, Cardano
🤖 Анализ: через ProxyAPI (GPT-3.5)

Команды:
/start - показать это сообщение
/status - текущий статус бота
/analyze - выполнить анализ сейчас

Отправьте любое сообщение, чтобы начать получать уведомления!
        """
        await update.message.reply_text(welcome_message)
        print(f"Бот активирован для Chat ID: {chat_id}")
    
    async def status_command(self, update: Update, context):
        """Обработчик команды /status"""
        global chat_id
        if chat_id is None:
            await update.message.reply_text("❌ Бот не активирован. Отправьте /start")
        else:
            await update.message.reply_text(f"✅ Бот активен\nChat ID: {chat_id}")
    
    async def analyze_command(self, update: Update, context):
        """Обработчик команды /analyze"""
        await update.message.reply_text("🔍 Выполняю анализ...")
        await self.hourly_analysis()
    
    async def handle_message(self, update: Update, context):
        """Обработчик всех сообщений"""
        global chat_id
        if chat_id is None:
            chat_id = update.effective_chat.id
            await update.message.reply_text("✅ Бот активирован! Используйте /analyze для анализа.")
            print(f"Бот активирован для Chat ID: {chat_id}")
        else:
            await update.message.reply_text("🤖 Бот уже активен. Используйте /analyze для анализа.")

def main():
    bot = TradingBot()
    
    # Регистрируем обработчики
    bot.app.add_handler(CommandHandler("start", bot.start_command))
    bot.app.add_handler(CommandHandler("status", bot.status_command))
    bot.app.add_handler(CommandHandler("analyze", bot.analyze_command))
    bot.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("🤖 Trading Bot запущен!")
    print(f"📱 Имя бота: tradeAiiiBot")
    print(f"🔗 Ссылка: https://t.me/tradeAiiiBot")
    print("📱 Отправьте боту /start или любое сообщение для активации")
    
    # Запускаем бота
    print("🔄 Запускаю polling...")
    bot.app.run_polling()

if __name__ == "__main__":
    main() 