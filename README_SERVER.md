# TradeBot — запуск на сервере (Linux)

Ниже приведена минимальная, проверенная инструкция по установке и запуску бота в фоне на Linux-сервере.

## 1. Подготовка проекта

- Скопируйте проект на сервер, например в каталог:
```
~/TradeAiBot
```
- Убедитесь, что в каталоге есть файлы: `working_bot.py`, `requirements.txt`, `.env`, `active_chats.json` (может быть `{}`).

## 2. Установка Python и venv
```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```
Если при создании venv ранее была ошибка `ensurepip is not available`, установите пакет подходящей версии, например:
```
sudo apt install -y python3.10-venv
```

## 3. Виртуальное окружение и зависимости
```
cd ~/TradeAiBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

## 4. Настройка .env
Создайте файл `.env` в корне проекта (если его нет):
```
TELEGRAM_TOKEN=ВАШ_TELEGRAM_BОT_TOKEN
PROXYAPI_KEY=ВАШ_PROXYAPI_KEY
PROXYAPI_URL=https://api.proxyapi.ru/openai/v1/chat/completions
AI_MODEL=gpt-3.5-turbo
CRYPTO_API_URL=https://api.coingecko.com/api/v3/simple/price
CRYPTO_IDS=bitcoin,ethereum,cardano
```

## 5. Пробный запуск в терминале
```
cd ~/TradeAiBot
~/TradeAiBot/.venv/bin/python working_bot.py
```
Остановите `Ctrl+C` после проверки, что ошибок нет.

## 6. Запуск в фоне (nohup)
Запускайте из каталога проекта, чтобы `.env` подхватился:
```
cd ~/TradeAiBot
nohup ~/TradeAiBot/.venv/bin/python working_bot.py > bot.out 2> bot.err & echo $! > bot.pid
```
Проверка:
```
ps aux | grep working_bot.py | grep -v grep
tail -n 50 bot.out
tail -n 50 bot.err
```
Остановка:
```
kill "$(cat bot.pid)" && rm bot.pid
```

Альтернатива без venv (не рекомендуется):
```
pip3 install --user -r ~/TradeAiBot/requirements.txt
cd ~/TradeAiBot
nohup python3 working_bot.py > bot.out 2> bot.err & echo $! > bot.pid
```

## 7. Автозапуск через systemd (опционально)
Создайте сервис-файл:
```
sudo nano /etc/systemd/system/tradebot.service
```
Содержимое (замените ВАШ_ПОЛЬЗОВАТЕЛЬ на имя пользователя):
```
[Unit]
Description=TradeBot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/TradeAiBot
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/TradeAiBot/.venv/bin/python /home/ВАШ_ПОЛЬЗОВАТЕЛЬ/TradeAiBot/working_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Команды управления:
```
sudo systemctl daemon-reload
sudo systemctl enable tradebot
sudo systemctl start tradebot
sudo systemctl status tradebot --no-pager
journalctl -u tradebot -f
```
Остановка/перезапуск:
```
sudo systemctl stop tradebot
sudo systemctl restart tradebot
```

## 8. Частые проблемы
- "Exit 127" при nohup:
  - Используйте абсолютные пути к python и файлам (`~/TradeAiBot/.venv/bin/python`).
  - Убедитесь, что виртуальное окружение создано и зависимости установлены.
- `ModuleNotFoundError: No module named 'requests'`:
  - Установите зависимости в ту же среду, из которой запускаете (venv или системный python3).
- `.env` не подхватывается:
  - Запускайте из каталога проекта или задайте `WorkingDirectory` в systemd.
- Ошибка venv `ensurepip is not available`:
  - Установите `python3-venv`/`python3.10-venv` и пересоздайте venv. 