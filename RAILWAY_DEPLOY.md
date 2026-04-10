# 🚀 Деплой бота на Railway.app

## Что уже сделано:

✅ Убран прокси (не нужен на Railway)
✅ Создан Procfile для запуска
✅ Создан railway.json конфиг
✅ Обновлен requirements.txt
✅ Создан .gitignore

## Пошаговая инструкция:

### 1. Инициализируй Git репозиторий (если еще не сделал)

```bash
git init
git add .
git commit -m "Подготовка к деплою на Railway"
```

### 2. Залей на GitHub

Создай новый репозиторий на https://github.com/new

```bash
git remote add origin https://github.com/ТВОЙ_USERNAME/ИМЯ_РЕПОЗИТОРИЯ.git
git branch -M main
git push -u origin main
```

### 3. Деплой на Railway

1. Зайди на https://railway.app
2. Нажми "New Project"
3. Выбери "Deploy from GitHub repo"
4. Выбери свой репозиторий
5. Railway автоматически начнет деплой

### 4. Настрой переменные окружения (НЕ ОБЯЗАТЕЛЬНО)

Если хочешь скрыть токены из кода:

В Railway → Settings → Variables добавь:
- `TELEGRAM_TOKEN` = твой токен
- `GEMINI_API_KEY_1` = первый ключ
- `GEMINI_API_KEY_2` = второй ключ
- `GROQ_API_KEY` = groq ключ

Потом в коде замени:
```python
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'твой_токен')
```

### 5. Проверь логи

Railway → Deployments → View Logs

Должно быть:
```
✅ База данных инициализирована
✅ Команды бота установлены
🚀 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!
```

### 6. Тестируй бота

Открой Telegram и напиши боту `/start`

## Что изменилось в коде:

**bot_with_logs.py:**
- Убран прокси (серверы Railway за границей)
- Добавлен таймаут 15 секунд на ответ модели
- Cooldown между ключами уменьшен до 2 секунд
- Список моделей заменен на ТОЛЬКО БЫСТРЫЕ

**Новые файлы:**
- `Procfile` - команда запуска для Railway
- `railway.json` - конфигурация деплоя
- `.gitignore` - что не заливать в Git

## Мониторинг

Railway показывает:
- CPU/RAM использование
- Логи в реальном времени
- Сколько кредитов осталось

## Если что-то не работает:

1. Проверь логи в Railway
2. Убедись что все токены правильные
3. Проверь что репозиторий обновлен на GitHub
4. Перезапусти деплой в Railway

## Обновление бота:

```bash
git add .
git commit -m "Обновление"
git push
```

Railway автоматически задеплоит новую версию!

## Локальный запуск (для тестов):

Если хочешь запустить локально в России - раскомментируй прокси в bot_with_logs.py:

```python
PROXY_URL = "http://127.0.0.1:10809"
os.environ['https_proxy'] = PROXY_URL
os.environ['http_proxy'] = PROXY_URL
from aiogram.client.session.aiohttp import AiohttpSession
session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=TELEGRAM_TOKEN, session=session)
```

Потом:
```bash
python bot_with_logs.py
```
