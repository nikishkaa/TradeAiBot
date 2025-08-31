# Простой Trading Bot для Telegram

Простой Telegram бот, который анализирует криптовалюты с помощью ProxyAPI (GPT-3.5) и отправляет результаты каждый час.

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` в корне проекта со следующим содержимым:
```env
# Telegram Bot
TELEGRAM_TOKEN=8220591320:AAGT7xl_ltX1EtuH8czTGe539kj4XTaIxRE

# ProxyAPI
PROXYAPI_KEY=sk-lMWaJW9HSgezZqT2oLD2X1s2NuZs75WJ
PROXYAPI_URL=https://api.proxyapi.ru/openai/v1/chat/completions

# Crypto API
CRYPTO_API_URL=https://api.coingecko.com/api/v3/simple/price
CRYPTO_IDS=bitcoin,ethereum,cardano
```

> ⚠️ **Важно**: Файл `.env` уже добавлен в `.gitignore` и не будет загружен в Git репозиторий для безопасности.

3. Настройте конфигурацию:
   - Chat ID будет получен автоматически при первом сообщении

## Настройка

1. Создайте бота в Telegram:
   - Напишите @BotFather в Telegram
   - Создайте нового бота командой `/newbot`
   - Получите токен бота

2. Активируйте бота:
   - Найдите бота в Telegram
   - Отправьте команду `/start` или любое сообщение
   - Бот автоматически активируется и начнет отправлять анализы

## Запуск

```bash
python working_bot.py
```

## Что делает бот

- Каждый час получает данные о Bitcoin, Ethereum и Cardano
- Анализирует данные с помощью ProxyAPI (GPT-3.5)
- Отправляет результаты в Telegram с анализом

## Команды бота

- `/start` - показать приветственное сообщение
- `/status` - проверить статус бота
- `/analyze` - выполнить анализ сейчас

## Настройка

В `.env` файле можно изменить:
- `CRYPTO_IDS` - список криптовалют для анализа
- `PROXYAPI_KEY` - ключ API (уже настроен) 