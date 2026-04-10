# 🎓 Школьный помощник - Telegram бот

Telegram бот для решения школьных заданий с поддержкой нескольких AI провайдеров.

## 🚀 Возможности

- ✅ Решение задач по всем школьным предметам
- 📷 Распознавание текста с фотографий (Gemini)
- 🔄 История диалога (последние 20 сообщений)
- 📊 Статистика использования
- 🤖 Выбор между разными AI моделями

## 🆓 Бесплатные API провайдеры

### С поддержкой фото 📷 (важно для школьников!)

#### 1. Google Gemini 2.0 Flash ⚡⚡⚡
- **Лимит:** 1500 запросов/день
- **Фото:** ✅ Да
- **Скорость:** Очень быстрый
- **Получить ключ:** https://aistudio.google.com/apikey
- **Лучший выбор** для фото заданий!

#### 2. Groq Llama Vision 90B ⚡⚡⚡
- **Лимит:** 14,400 запросов/день
- **Фото:** ✅ Да
- **Скорость:** Самый быстрый
- **Получить ключ:** https://console.groq.com
- **Модель:** llama-3.2-90b-vision-preview

#### 3. OpenRouter Free 🆓
- **Лимит:** Бесплатно (с ограничениями)
- **Фото:** ✅ Да
- **Скорость:** Средняя
- **Получить ключ:** https://openrouter.ai/keys (опционально)
- **Модель:** google/gemini-2.0-flash-exp:free

### Только текст 📝

#### 4. Groq Llama 3.3 70B ⚡⚡⚡
- **Лимит:** 14,400 запросов/день
- **Фото:** ❌ Нет
- **Скорость:** Очень быстрый
- **Для текстовых задач** - отличный выбор

### Другие варианты:

**Hugging Face Inference API**
- Бесплатно, много моделей
- Некоторые поддерживают изображения
- https://huggingface.co/settings/tokens

**Together AI**
- Быстрые модели
- Бесплатный tier
- https://api.together.xyz

**Cohere**
- 100 запросов/минуту бесплатно
- Только текст
- https://dashboard.cohere.com/api-keys

## 📦 Установка

### Вариант 1: Базовый бот (только Gemini)

```bash
cd ~/burmaldun_bot
source venv/bin/activate
pip install -r requirements.txt

# Запуск
python bot.py

# Или через pm2
pm2 start bot.py --name burmaldun --interpreter python3
```

### Вариант 2: Мульти-провайдер бот

```bash
cd ~/burmaldun_bot
source venv/bin/activate
pip install -r requirements.txt

# Добавь Groq API ключ в bot_multi_provider.py
nano bot_multi_provider.py
# Найди строку: GROQ_API_KEY = ''
# Вставь свой ключ: GROQ_API_KEY = 'gsk_...'

# Запуск
python bot_multi_provider.py

# Или через pm2
pm2 start bot_multi_provider.py --name burmaldun --interpreter python3
```

## 🎯 Команды бота

- `/start` - Запуск бота
- `/help` - Помощь
- `/provider` - Выбор AI провайдера (только мульти-версия)
- `/clear` - Очистить историю диалога
- `/stats` - Статистика использования
- `/reset` - Полный сброс настроек

## ⚙️ Конфигурация

### Прокси
Бот использует прокси для обхода блокировок:
```python
os.environ['https_proxy'] = "http://127.0.0.1:10809"
os.environ['http_proxy'] = "http://127.0.0.1:10809"
```

### Системный промпт
Промпт настроен для школьных заданий:
- Без LaTeX форматирования
- Степени через Unicode (² ³ ⁴)
- Готовые решения для тетради
- Без лишней воды

## 📊 База данных

SQLite база `bot_data.db` хранит:
- `user_settings` - настройки пользователей
- `chat_history` - история диалогов (последние 20 сообщений)
- `user_stats` - статистика использования

## 🔧 Управление через pm2

```bash
# Статус
pm2 status

# Логи
pm2 logs burmaldun

# Рестарт
pm2 restart burmaldun

# Остановка
pm2 stop burmaldun

# Удаление
pm2 delete burmaldun
```

## 💡 Советы

1. **Для фото заданий:**
   - Gemini 2.0 Flash - самый быстрый и точный
   - Groq Vision - очень быстрый, большой лимит
   - OpenRouter Free - запасной вариант

2. **Для текстовых задач:**
   - Groq Llama 3.3 - самый быстрый
   - Gemini - универсальный

3. **Стратегия использования:**
   - Начни с Gemini (1500 запросов)
   - Когда лимит кончится - переключись на Groq Vision (14400 запросов)
   - OpenRouter как запасной вариант

4. **На VPS за границей** убери прокси - будет быстрее!

## 🛠 Расширение функционала

### Добавить новый провайдер

```python
PROVIDERS = {
    'новый_провайдер': {
        'name': '🆕 Название',
        'model': 'model-name',
        'supports_images': False
    }
}

async def call_новый_провайдер(messages, system_prompt):
    # Твоя реализация
    pass
```

## 📝 Структура проекта

```
~/burmaldun_bot/
├── bot.py                    # Базовая версия (только Gemini)
├── bot_multi_provider.py     # Версия с выбором провайдера
├── requirements.txt          # Зависимости
├── bot_data.db              # База данных (создается автоматически)
├── venv/                    # Виртуальное окружение
└── README.md                # Эта инструкция
```

## 🐛 Решение проблем

### Ошибка "Module not found"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Ошибка прокси
Проверь что Xray/VLESS запущен на порту 10809

### Ошибка API ключа
Проверь что ключи правильно вставлены в код

## 📞 Поддержка

Если нужна помощь - пиши в чат!
