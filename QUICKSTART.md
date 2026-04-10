# ⚡ Быстрый старт

## На локальном ПК (Windows)

```bash
# 1. Установи зависимости
pip install aiogram==3.15.0 google-genai==2.0.0 httpx==0.28.1

# 2. Запусти базовую версию (только Gemini)
python bot.py

# 3. Или мульти-провайдер версию
python bot_multi_provider.py
```

## На VPS (Ubuntu)

```bash
# 1. Подключись
ssh root@your_vps_ip

# 2. Быстрая установка
apt update && apt install -y python3 python3-pip python3-venv nodejs npm
npm install -g pm2

# 3. Создай проект
mkdir ~/burmaldun_bot && cd ~/burmaldun_bot
python3 -m venv venv
source venv/bin/activate
pip install aiogram==3.15.0 google-genai==2.0.0 httpx==0.28.1

# 4. Загрузи файл (с локального ПК)
# scp bot_multi_provider.py root@your_vps_ip:~/burmaldun_bot/

# 5. Настрой ключи
nano bot_multi_provider.py
# Вставь свои токены

# 6. Запусти
pm2 start bot_multi_provider.py --name burmaldun --interpreter python3
pm2 save
pm2 startup
```

## 🔑 Где взять API ключи

1. **Telegram Bot Token** (обязательно)
   - Открой @BotFather в Telegram
   - Отправь `/newbot`
   - Следуй инструкциям
   - Скопируй токен

2. **Google Gemini** (обязательно)
   - Открой https://aistudio.google.com/apikey
   - Войди через Google
   - Нажми "Create API Key"
   - Скопируй ключ

3. **Groq** (опционально, для большего лимита)
   - Открой https://console.groq.com
   - Зарегистрируйся
   - Settings → API Keys → Create API Key
   - Скопируй ключ

4. **OpenRouter** (опционально, запасной вариант)
   - Открой https://openrouter.ai/keys
   - Зарегистрируйся
   - Создай ключ
   - Или используй без ключа (ограниченный доступ)

## 📝 Что редактировать в коде

Открой `bot_multi_provider.py` и найди:

```python
# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = 'СЮДА_ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER'
GEMINI_API_KEY = 'СЮДА_ВСТАВЬ_КЛЮЧ_GEMINI'
GROQ_API_KEY = ''  # Опционально
OPENROUTER_API_KEY = ''  # Опционально
```

Если прокси НЕ нужен (VPS за границей):
```python
# Закомментируй эти строки:
# os.environ['https_proxy'] = "http://127.0.0.1:10809"
# os.environ['http_proxy'] = "http://127.0.0.1:10809"
```

## ✅ Проверка работы

1. Найди своего бота в Telegram
2. Отправь `/start`
3. Отправь любой вопрос или фото
4. Получи ответ!

## 🎯 Основные команды бота

- `/start` - Запуск
- `/provider` - Выбрать нейросеть
- `/clear` - Очистить историю
- `/stats` - Статистика
- `/help` - Помощь

## 🔧 Управление на VPS

```bash
pm2 status           # Статус
pm2 logs burmaldun   # Логи
pm2 restart burmaldun # Перезапуск
pm2 stop burmaldun   # Остановка
```

## 🚨 Если что-то не работает

### Бот не отвечает
```bash
# Проверь логи
pm2 logs burmaldun --lines 50

# Проверь что процесс запущен
pm2 status
```

### Ошибка "Invalid token"
- Проверь что токен правильно скопирован
- Не должно быть пробелов или кавычек

### Ошибка "API key not valid"
- Проверь что API ключ правильный
- Для Gemini: https://aistudio.google.com/apikey

### Ошибка с прокси
- Если VPS за границей - убери строки с прокси
- Если в России - настрой свой прокси

## 📊 Какую модель выбрать?

**Для школьников с фото:**
1. Gemini 2.0 Flash (по умолчанию) - быстрый, точный
2. Groq Vision - очень быстрый, большой лимит
3. OpenRouter Free - запасной вариант

**Только текст:**
1. Groq Llama 3.3 - самый быстрый

## 🎓 Примеры использования

**Математика:**
```
Реши уравнение: 2x + 5 = 15
```

**С фото:**
```
[Отправь фото задачи]
Реши задачу с фото
```

**Русский язык:**
```
Разбери предложение по членам: Мальчик читает книгу
```

**Английский:**
```
Переведи: The quick brown fox jumps over the lazy dog
```

Бот выдаст готовое решение без лишних слов!
