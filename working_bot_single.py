import requests
import json
import os
import threading
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Загружаем переменные из .env файла
load_dotenv()

# Получаем переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_URL = os.getenv("PROXYAPI_URL")
AI_MODEL = os.getenv("AI_MODEL", "gpt-3.5-turbo")
CRYPTO_API_URL = os.getenv("CRYPTO_API_URL")
CRYPTO_IDS = os.getenv("CRYPTO_IDS", "bitcoin,ethereum,cardano").split(",")

# Глобальная переменная для хранения Chat ID
chat_id = None
CHAT_ID_FILE = "chat_id.txt"  # Файл для сохранения Chat ID

# Настройки бота
ANALYSIS_INTERVAL_SECONDS = 3600
scheduler_running = False

# Настройка логирования
def setup_logging():
    """Настраивает логирование"""
    log_filename = f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)


# Инициализируем логгер
logger = setup_logging()


def format_interval(seconds):
    """Форматирует интервал в читаемый вид"""
    if seconds < 60:
        return f"каждые {seconds} сек"
    elif seconds < 3600:
        return f"каждые {seconds // 60} мин"
    elif seconds < 86400:
        return f"каждый {seconds // 3600} час"
    else:
        return f"каждый {seconds // 86400} день"


class TradingBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.load_chat_id()

    def load_chat_id(self):
        """Загружает Chat ID из файла"""
        global chat_id
        try:
            if os.path.exists(CHAT_ID_FILE):
                with open(CHAT_ID_FILE, 'r') as f:
                    chat_id = f.read().strip()
                    print(f"📱 Загружен Chat ID: {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка загрузки Chat ID: {e}")
            print(f"Ошибка загрузки Chat ID: {e}")

    def save_chat_id(self, chat_id_value):
        """Сохраняет Chat ID в файл"""
        try:
            with open(CHAT_ID_FILE, 'w') as f:
                f.write(str(chat_id_value))
            print(f"💾 Chat ID сохранен: {chat_id_value}")
        except Exception as e:
            logger.error(f"Ошибка сохранения Chat ID: {e}")
            print(f"Ошибка сохранения Chat ID: {e}")

    def get_crypto_data(self):
        """Получает данные о криптовалютах"""
        try:
            params = {
                'ids': ','.join(CRYPTO_IDS),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            response = requests.get(CRYPTO_API_URL, params=params)
            data = response.json()
            return data
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
                "model": AI_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200
            }

            response = requests.post(PROXYAPI_URL, headers=headers, json=payload)
            result = response.json()
            analysis = result.get('choices', [{}])[0].get('message', {}).get('content', 'Ошибка анализа')
            return analysis
        except Exception as e:
            return f"Ошибка анализа: {e}"

    def send_message_sync(self, text):
        """Отправляет сообщение в Telegram (синхронно)"""
        global chat_id
        if chat_id is None:
            print("Chat ID не установлен. Отправьте боту любое сообщение.")
            return
        try:
            # Используем requests для отправки сообщения напрямую
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"Сообщение отправлено: {text[:50]}...")
            else:
                print(f"Ошибка отправки: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    def hourly_analysis_sync(self):
        """Выполняет анализ (синхронно)"""
        print("Выполняю анализ...")

        # Получаем данные
        crypto_data = self.get_crypto_data()
        if isinstance(crypto_data, str):
            self.send_message_sync(f"❌ {crypto_data}")
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
        self.send_message_sync(message)

    def scheduler_thread(self):
        """Поток планировщика"""
        global scheduler_running
        while scheduler_running:
            time.sleep(ANALYSIS_INTERVAL_SECONDS)
            if scheduler_running and chat_id is not None:
                print("⏰ Выполняю плановый анализ...")
                self.hourly_analysis_sync()

    def start_scheduler(self):
        """Запускает планировщик в отдельном потоке"""
        global scheduler_running
        if not scheduler_running:
            scheduler_running = True
            scheduler_thread = threading.Thread(target=self.scheduler_thread, daemon=True)
            scheduler_thread.start()
            interval_text = format_interval(ANALYSIS_INTERVAL_SECONDS)
            print(f"⏰ Планировщик запущен ({interval_text})")

    def stop_scheduler(self):
        """Останавливает планировщик"""
        global scheduler_running
        scheduler_running = False
        print("⏰ Планировщик остановлен")

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
        self.save_chat_id(chat_id)
        interval_text = format_interval(ANALYSIS_INTERVAL_SECONDS)
        welcome_message = f"""
🤖 Добро пожаловать в Trading Bot!

Я анализирую криптовалюты и отправляю результаты {interval_text}.

📊 Сейчас анализирую: Bitcoin, Ethereum, Cardano
🤖 Анализ: через ProxyAPI (GPT-3.5)
⏰ Отправка: {interval_text}

Команды:
/start - показать это сообщение
/status - текущий статус бота
/analyze - выполнить анализ сейчас

Отправьте любое сообщение, чтобы начать получать уведомления!
        """
        await update.message.reply_text(welcome_message)
        print(f"Бот активирован для Chat ID: {chat_id}")
        # Запускаем планировщик
        self.start_scheduler()

    async def status_command(self, update: Update, context):
        """Обработчик команды /status"""
        global chat_id, scheduler_running
        if chat_id is None:
            await update.message.reply_text("❌ Бот не активирован. Отправьте /start")
        else:
            status = "✅ Запущен" if scheduler_running else "❌ Остановлен"
            await update.message.reply_text(f"✅ Бот активен\nChat ID: {chat_id}\nПланировщик: {status}")

    async def analyze_command(self, update: Update, context):
        """Обработчик команды /analyze"""
        await update.message.reply_text("🔍 Выполняю анализ...")
        await self.hourly_analysis()

    async def handle_message(self, update: Update, context):
        """Обработчик всех сообщений"""
        global chat_id
        if chat_id is None:
            chat_id = update.effective_chat.id
            self.save_chat_id(chat_id)
            interval_text = format_interval(ANALYSIS_INTERVAL_SECONDS)
            await update.message.reply_text(f"✅ Бот активирован! Анализ будет отправляться {interval_text}.")
            print(f"Бот активирован для Chat ID: {chat_id}")
            # Запускаем планировщик
            self.start_scheduler()
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
    print("📱 Отправьте боту /start или любое сообщение для активации")
    if chat_id is not None:
     bot.start_scheduler()
    bot.app.run_polling()


if __name__ == "__main__":
    main()
