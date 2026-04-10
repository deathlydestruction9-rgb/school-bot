# 🚀 Перенос бота на VPS сервер

## Быстрая установка на Ubuntu VPS

### 1. Подключение к VPS
```bash
ssh root@your_vps_ip
```

### 2. Установка зависимостей
```bash
# Обновление системы
apt update && apt upgrade -y

# Python и pip
apt install python3 python3-pip python3-venv -y

# PM2 для управления процессом
apt install nodejs npm -y
npm install -g pm2

# Опционально: установка прокси (если нужен)
# bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)
```

### 3. Создание проекта
```bash
# Создаем директорию
mkdir -p ~/burmaldun_bot
cd ~/burmaldun_bot

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install aiogram==3.15.0 google-genai==2.0.0 httpx==0.28.1
```

### 4. Загрузка файлов

**Вариант А: Через SCP с локального ПК**
```bash
# На локальном ПК (Windows)
scp bot_multi_provider.py root@your_vps_ip:~/burmaldun_bot/
scp requirements.txt root@your_vps_ip:~/burmaldun_bot/
```

**Вариант Б: Создать файл на VPS**
```bash
# На VPS
cd ~/burmaldun_bot
nano bot.py
# Вставь код, Ctrl+X, Y, Enter
```

**Вариант В: Через Git**
```bash
# На VPS
cd ~
git clone your_repo_url burmaldun_bot
cd burmaldun_bot
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Настройка API ключей

```bash
cd ~/burmaldun_bot
nano bot_multi_provider.py

# Найди и заполни:
TELEGRAM_TOKEN = 'твой_токен'
GEMINI_API_KEY = 'твой_ключ'
GROQ_API_KEY = 'твой_ключ'  # Опционально
OPENROUTER_API_KEY = ''  # Опционально
```

### 6. Настройка прокси (если нужен)

Если VPS в России и нужен обход блокировок:

```bash
# Убери или закомментируй строки прокси если не нужен:
nano bot_multi_provider.py

# Найди и закомментируй:
# os.environ['https_proxy'] = "http://127.0.0.1:10809"
# os.environ['http_proxy'] = "http://127.0.0.1:10809"
```

Или настрой свой прокси на VPS.

### 7. Запуск бота

**Тестовый запуск:**
```bash
cd ~/burmaldun_bot
source venv/bin/activate
python3 bot_multi_provider.py
# Ctrl+C для остановки
```

**Запуск через PM2 (рекомендуется):**
```bash
cd ~/burmaldun_bot

# Запуск
pm2 start bot_multi_provider.py --name burmaldun --interpreter python3

# Автозапуск при перезагрузке VPS
pm2 startup
pm2 save

# Проверка статуса
pm2 status

# Логи
pm2 logs burmaldun

# Рестарт
pm2 restart burmaldun
```

## 🔧 Управление ботом на VPS

### Основные команды PM2
```bash
pm2 list              # Список процессов
pm2 status            # Статус
pm2 logs burmaldun    # Логи в реальном времени
pm2 logs burmaldun --lines 100  # Последние 100 строк
pm2 restart burmaldun # Перезапуск
pm2 stop burmaldun    # Остановка
pm2 delete burmaldun  # Удаление
pm2 monit             # Мониторинг ресурсов
```

### Обновление бота
```bash
cd ~/burmaldun_bot

# Останавливаем
pm2 stop burmaldun

# Обновляем код (через scp, git или nano)
nano bot_multi_provider.py

# Запускаем
pm2 restart burmaldun

# Или если удалили:
pm2 start bot_multi_provider.py --name burmaldun --interpreter python3
```

### Просмотр логов
```bash
# Логи PM2
pm2 logs burmaldun

# Логи Python
tail -f ~/.pm2/logs/burmaldun-out.log
tail -f ~/.pm2/logs/burmaldun-error.log
```

## 🛡️ Безопасность

### 1. Создай отдельного пользователя (рекомендуется)
```bash
# Создаем пользователя
adduser botuser
usermod -aG sudo botuser

# Переключаемся
su - botuser

# Повторяем установку от имени botuser
```

### 2. Настрой firewall
```bash
# Разрешаем только SSH
ufw allow 22/tcp
ufw enable
ufw status
```

### 3. Храни секреты в .env файле
```bash
cd ~/burmaldun_bot
nano .env

# Содержимое:
TELEGRAM_TOKEN=твой_токен
GEMINI_API_KEY=твой_ключ
GROQ_API_KEY=твой_ключ
```

Затем в коде:
```python
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
```

## 📊 Мониторинг

### Проверка работы бота
```bash
# Статус процесса
pm2 status

# Использование ресурсов
pm2 monit

# Системные ресурсы
htop

# Размер базы данных
ls -lh ~/burmaldun_bot/bot_data.db
```

### Автоматический рестарт при ошибках
PM2 автоматически перезапускает бота при падении.

Настройка лимитов:
```bash
pm2 start bot_multi_provider.py --name burmaldun --interpreter python3 \
  --max-memory-restart 500M \
  --restart-delay 3000
```

## 🔄 Бэкап

### Бэкап базы данных
```bash
# Создаем директорию для бэкапов
mkdir -p ~/backups

# Бэкап базы
cp ~/burmaldun_bot/bot_data.db ~/backups/bot_data_$(date +%Y%m%d).db

# Автоматический бэкап через cron
crontab -e

# Добавь строку (бэкап каждый день в 3:00):
0 3 * * * cp ~/burmaldun_bot/bot_data.db ~/backups/bot_data_$(date +\%Y\%m\%d).db
```

### Скачать бэкап на локальный ПК
```bash
# На локальном ПК
scp root@your_vps_ip:~/burmaldun_bot/bot_data.db ./backup_$(date +%Y%m%d).db
```

## 🚨 Решение проблем на VPS

### Бот не запускается
```bash
# Проверь логи
pm2 logs burmaldun --lines 50

# Проверь что виртуальное окружение активно
which python3
# Должно быть: /root/burmaldun_bot/venv/bin/python3

# Проверь зависимости
source ~/burmaldun_bot/venv/bin/activate
pip list
```

### Ошибки API
```bash
# Проверь что ключи правильные
grep "API_KEY" ~/burmaldun_bot/bot_multi_provider.py

# Проверь интернет
ping google.com
curl https://api.telegram.org
```

### Высокое использование памяти
```bash
# Ограничь память для PM2
pm2 restart burmaldun --max-memory-restart 300M

# Очисти старую историю в БД
sqlite3 ~/burmaldun_bot/bot_data.db "DELETE FROM chat_history WHERE id < (SELECT MAX(id) - 1000 FROM chat_history);"
```

## 📝 Чеклист переноса

- [ ] VPS подключен и обновлен
- [ ] Python 3.10+ установлен
- [ ] PM2 установлен
- [ ] Виртуальное окружение создано
- [ ] Зависимости установлены
- [ ] Файлы бота загружены
- [ ] API ключи настроены
- [ ] Прокси настроен (если нужен)
- [ ] Бот запущен через PM2
- [ ] Автозапуск настроен (pm2 save)
- [ ] Логи проверены
- [ ] Бот отвечает в Telegram
- [ ] Бэкап настроен

## 💡 Советы

1. **Используй screen/tmux** для долгих операций:
```bash
apt install screen
screen -S bot
# Работай в screen
# Ctrl+A, D для отключения
# screen -r bot для возврата
```

2. **Мониторь диск:**
```bash
df -h
du -sh ~/burmaldun_bot/*
```

3. **Регулярно обновляй систему:**
```bash
apt update && apt upgrade -y
```

4. **Используй разные модели** для балансировки нагрузки между API

5. **На VPS за границей** можно убрать прокси - будет быстрее!
