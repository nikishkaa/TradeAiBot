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

# Словарь для хранения активных чатов
active_chats = {}
CHAT_ID_FILE = "active_chats.json"  # Файл для сохранения активных чатов

# Настройки бота
ANALYSIS_INTERVAL_SECONDS = 20
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
        self.load_active_chats()

    def load_active_chats(self):
        """Загружает активные чаты из файла"""
        global active_chats
        try:
            if os.path.exists(CHAT_ID_FILE):
                with open(CHAT_ID_FILE, 'r', encoding='utf-8') as f:
                    active_chats = json.load(f)
                    print(f"📱 Загружено {len(active_chats)} активных чатов")
        except Exception as e:
            logger.error(f"Ошибка загрузки активных чатов: {e}")
            print(f"Ошибка загрузки активных чатов: {e}")

    def save_active_chats(self):
        """Сохраняет активные чаты в файл"""
        try:
            with open(CHAT_ID_FILE, 'w', encoding='utf-8') as f:
                json.dump(active_chats, f, ensure_ascii=False, indent=2)
            print(f"💾 Сохранено {len(active_chats)} активных чатов")
        except Exception as e:
            logger.error(f"Ошибка сохранения активных чатов: {e}")
            print(f"Ошибка сохранения активных чатов: {e}")

    def add_chat(self, chat_id, username=None):
        """Добавляет чат в список активных"""
        global active_chats
        active_chats[str(chat_id)] = {
            'username': username,
            'added_at': datetime.now().isoformat()
        }
        self.save_active_chats()
        print(f"✅ Добавлен чат: {chat_id} (@{username})")

    def remove_chat(self, chat_id):
        """Удаляет чат из списка активных"""
        global active_chats
        if str(chat_id) in active_chats:
            del active_chats[str(chat_id)]
            self.save_active_chats()
            print(f"❌ Удален чат: {chat_id}")

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

    def send_message_sync(self, chat_id, text):
        """Отправляет сообщение в Telegram (синхронно)"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"📤 Сообщение отправлено в чат {chat_id}")
            else:
                print(f"❌ Ошибка отправки в чат {chat_id}: {response.status_code}")
                # Если чат заблокирован или удален, удаляем его из активных
                if response.status_code in [403, 400]:
                    self.remove_chat(chat_id)
        except Exception as e:
            print(f"❌ Ошибка отправки в чат {chat_id}: {e}")
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")

    def hourly_analysis_sync(self):
        """Выполняет анализ (синхронно) для всех активных чатов"""
        global active_chats
        if not active_chats:
            print("📭 Нет активных чатов для отправки анализа")
            return

        print(f"🔍 Выполняю анализ для {len(active_chats)} чатов...")

        # Получаем данные
        crypto_data = self.get_crypto_data()
        if isinstance(crypto_data, str):
            # Отправляем ошибку во все чаты
            for chat_id in active_chats.keys():
                self.send_message_sync(chat_id, f"❌ {crypto_data}")
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

        # Отправляем сообщение во все активные чаты
        for chat_id in active_chats.keys():
            self.send_message_sync(chat_id, message)

    def scheduler_thread(self):
        """Поток планировщика"""
        global scheduler_running, active_chats
        while scheduler_running:
            time.sleep(ANALYSIS_INTERVAL_SECONDS)
            if scheduler_running and active_chats:
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

    async def send_message(self, chat_id, text):
        """Отправляет сообщение в Telegram"""
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            print(f"📤 Сообщение отправлено в чат {chat_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки в чат {chat_id}: {e}")
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")

    async def hourly_analysis(self, chat_id):
        """Выполняет анализ для конкретного чата"""
        print("Выполняю анализ...")

        # Получаем данные
        crypto_data = self.get_crypto_data()
        if isinstance(crypto_data, str):
            await self.send_message(chat_id, f"❌ {crypto_data}")
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
        await self.send_message(chat_id, message)

    async def start_command(self, update: Update, context):
        """Обработчик команды /start"""
        chat_id = update.effective_chat.id
        username = update.effective_user.username

        self.add_chat(chat_id, username)
        interval_text = format_interval(ANALYSIS_INTERVAL_SECONDS)
        welcome_message = f"""
🤖 Добро пожаловать в Trading Bot!

Я анализирую криптовалюты и отправляю результаты {interval_text}.

📊 Сейчас анализирую: Bitcoin, Ethereum, Cardano
🤖 Анализ: через ProxyAPI ({AI_MODEL})
⏰ Отправка: {interval_text}

Команды:
/start - показать это сообщение
/status - текущий статус бота
/analyze - выполнить анализ сейчас
/stop - остановить получение уведомлений

Отправьте любое сообщение, чтобы начать получать уведомления!
        """
        await update.message.reply_text(welcome_message)
        print(f"✅ Бот активирован для чата: {chat_id} (@{username})")

    async def status_command(self, update: Update, context):
        """Обработчик команды /status"""
        global active_chats, scheduler_running
        chat_id = update.effective_chat.id

        if str(chat_id) not in active_chats:
            await update.message.reply_text("❌ Бот не активирован. Отправьте /start")
        else:
            status = "✅ Запущен" if scheduler_running else "❌ Остановлен"
            total_chats = len(active_chats)
            await update.message.reply_text(
                f"✅ Бот активен\n"
                f"Ваш Chat ID: {chat_id}\n"
                f"Всего активных чатов: {total_chats}\n"
                f"Планировщик: {status}"
            )

    async def analyze_command(self, update: Update, context):
        """Обработчик команды /analyze"""
        chat_id = update.effective_chat.id
        if str(chat_id) not in active_chats:
            await update.message.reply_text("❌ Бот не активирован. Отправьте /start")
            return

        await update.message.reply_text("🔍 Выполняю анализ...")
        await self.hourly_analysis(chat_id)

    async def stop_command(self, update: Update, context):
        """Обработчик команды /stop"""
        chat_id = update.effective_chat.id
        if str(chat_id) in active_chats:
            self.remove_chat(chat_id)
            await update.message.reply_text("❌ Вы отписались от уведомлений")
        else:
            await update.message.reply_text("❌ Вы не были подписаны на уведомления")

    async def handle_message(self, update: Update, context):
        """Обработчик всех сообщений"""
        chat_id = update.effective_chat.id
        username = update.effective_user.username

        if str(chat_id) not in active_chats:
            self.add_chat(chat_id, username)
            interval_text = format_interval(ANALYSIS_INTERVAL_SECONDS)
            await update.message.reply_text(f"✅ Бот активирован! Анализ будет отправляться {interval_text}.")
            print(f"✅ Бот активирован для чата: {chat_id} (@{username})")
        else:
            await update.message.reply_text("🤖 Бот уже активен. Используйте /analyze для анализа.")


def setup_bot_commands():
    """Устанавливает список команд для бота"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands"
        commands = [
            {"command": "start", "description": "🚀 Запустить бота и подписаться на уведомления"},
            {"command": "status", "description": "📊 Показать статус бота и количество пользователей"},
            {"command": "analyze", "description": "🔍 Выполнить анализ криптовалют сейчас"},
            {"command": "stop", "description": "❌ Отписаться от уведомлений"}
        ]
        data = {"commands": commands}
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ Команды бота установлены")
        else:
            print(f"❌ Ошибка установки команд: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка установки команд: {e}")

def main():
    # Устанавливаем команды бота
    setup_bot_commands()
    bot = TradingBot()

    # Регистрируем обработчики
    bot.app.add_handler(CommandHandler("start", bot.start_command))
    bot.app.add_handler(CommandHandler("status", bot.status_command))
    bot.app.add_handler(CommandHandler("analyze", bot.analyze_command))
    bot.app.add_handler(CommandHandler("stop", bot.stop_command))
    bot.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    print("🤖 Trading Bot запущен!")
    if active_chats:
        print(f"✅ Загружено {len(active_chats)} активных чатов")
        bot.start_scheduler()
    else:
        print("📱 Отправьте боту /start или любое сообщение для активации")

    bot.app.run_polling()


if __name__ == "__main__":
    main()