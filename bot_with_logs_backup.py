import asyncio
import logging
import os
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand
from google import genai
from google.genai import types as g_types
from aiogram.exceptions import TelegramBadRequest
import httpx

# Отслеживание последнего использования каждого ключа
last_key_usage = {}
KEY_COOLDOWN = 4  # Секунды между запросами к одному ключу (15 req/min = 1 req/4 sec)

def clean_latex(text):
    """Удаляет LaTeX форматирование из текста"""
    # Удаляем $ и $$
    text = text.replace('$$', '')
    text = text.replace('$', '')
    # Заменяем \frac{a}{b} на (a/b)
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1/\2)', text)
    # Удаляем другие LaTeX команды
    text = text.replace('\\cdot', '·')
    text = text.replace('\\sin', 'sin')
    text = text.replace('\\cos', 'cos')
    text = text.replace('\\tan', 'tan')
    text = text.replace('\\sqrt', '√')
    text = text.replace('\\circ', '°')
    text = text.replace('^\\circ', '°')
    text = text.replace('\\\\', '')
    text = text.replace('\\', '')
    return text

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = '8360715271:AAETGMaf74WPhzkocrWlZvL4gpNz5SkaR-I'

# Несколько API ключей для балансировки нагрузки
GEMINI_API_KEYS = [
    'AIzaSyA9_1w5qp_S4A7AHqx0DQXMHKp_VVeB3w4',  # Ключ 2 (КВОТА ИСЧЕРПАНА до 03:00 МСК)
    # Добавь сюда новые ключи:
    # 'AIzaSyC2lMotTBWc-TFmoC1TKN9HMbiq-0irQ4Q',
    # 'НОВЫЙ_КЛЮЧ_2',
    # 'НОВЫЙ_КЛЮЧ_3',
]

# Groq API ключ (запасной провайдер, 14,400 запросов/день бесплатно)
GROQ_API_KEY = "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"  # Получи на https://console.groq.com/keys

current_key_index = 0  # Индекс текущего ключа

def get_next_api_key():
    """Получить следующий API ключ по кругу с учетом cooldown"""
    global current_key_index
    
    # Пробуем найти ключ, который не использовался недавно
    attempts = 0
    while attempts < len(GEMINI_API_KEYS):
        key = GEMINI_API_KEYS[current_key_index]
        current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
        
        # Проверяем когда ключ использовался последний раз
        last_used = last_key_usage.get(key, 0)
        time_since_use = time.time() - last_used
        
        if time_since_use >= KEY_COOLDOWN:
            # Ключ готов к использованию
            last_key_usage[key] = time.time()
            return key
        
        attempts += 1
    
    # Если все ключи использовались недавно - берем следующий и ждем
    key = GEMINI_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
    
    last_used = last_key_usage.get(key, 0)
    time_since_use = time.time() - last_used
    
    if time_since_use < KEY_COOLDOWN:
        wait_time = KEY_COOLDOWN - time_since_use
        logging.info(f"⏳ Ожидание {wait_time:.1f}с перед использованием ключа (RPM лимит)")
        time.sleep(wait_time)
    
    last_key_usage[key] = time.time()
    return key

# Прокси для обхода блокировок
PROXY_URL = "http://127.0.0.1:10809"  # Твой Xray

# Настройка прокси для Gemini
os.environ['https_proxy'] = PROXY_URL
os.environ['http_proxy'] = PROXY_URL

# Создаем бота с прокси для Telegram
from aiogram.client.session.aiohttp import AiohttpSession

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=TELEGRAM_TOKEN, session=session)
dp = Dispatcher()

CURRENT_MODEL = "gemini-2.0-flash"

# Список моделей для автоматического переключения (в порядке приоритета)
FALLBACK_MODELS = [
    "gemini-flash-lite-latest",       # РАБОТАЕТ! Быстрая (2с)
    "gemini-3.1-flash-lite-preview",  # РАБОТАЕТ! (4.5с)
    "gemini-flash-latest",            # Последняя flash
    "gemini-3-flash-preview",         # Flash preview
    "gemini-3.1-flash-image-preview", # Image preview
    "gemini-2.0-flash",               # Полная 2.0
    "gemini-2.0-flash-001",           # Стабильная 2.0
    "gemini-pro-latest"               # Pro как последний вариант
]

DEFAULT_PROMPT = """Ты — универсальный школьный помощник. Твоя задача — выдавать готовые решения, которые можно сразу переписывать в тетрадь без исправлений.

ОБЩИЕ ПРАВИЛА:
1. НИКАКИХ приветствий ("Привет", "Вот решение") и лишней воды. Сразу к делу.
2. СТРОГО ЗАПРЕЩЕНО использовать LaTeX (НИКАКИХ $, $$, \\, frac, \\cdot, \\begin, \\end).
3. Используй жирный шрифт только для заголовков заданий и важных терминов.

АЛГЕБРА И МАТЕМАТИКА:
1. Деление пиши через : (двоеточие) или / (черта для дробей).
2. СТЕПЕНИ пиши ТОЛЬКО маленькими цифрами: ⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹. Для отрицательных: ⁻¹ ⁻² ⁻³ и т.д.
3. Умножение пиши через * или просто пропускай (например: 5a).
4. Структура: Номер. Пошаговое решение через знак = Ответ.
5. НИКОГДА не используй ^ для степеней - только Unicode символы!

ПРИМЕРЫ ПРАВИЛЬНОГО ОФОРМЛЕНИЯ:
✅ Правильно: x² + 2x³ - 5
✅ Правильно: 4¹¹ * 4⁻⁹ = 4² = 16
✅ Правильно: (x⁻³)⁴ * x¹⁴ = x²
❌ НЕПРАВИЛЬНО: $x^2 + 2x^3 - 5$
❌ НЕПРАВИЛЬНО: x^2 + 2x^3 - 5
❌ НЕПРАВИЛЬНО: \\frac{1}{2}

РУССКИЙ ЯЗЫК И ЛИТЕРАТУРА:
1. Перевод: Слово — перевод (без точек в конце).
2. Синтаксический анализ: расписывай по членам предложения (подлежащее, сказуемое и т.д.).
3. Сочинения: Пиши четко по теме, разделяй на абзацы (Вступление, Основная часть, Вывод). Используй грамотный, но доступный школьный язык, чтобы не выглядело слишком "нейросетевым".

ОФОРМЛЕНИЕ:
- Никаких знаков по типу звездочек или еще каких нибудь ЗНАКОВ мешаюших тексту решения и тд.
- Никаких таблиц (используй списки).
- Никаких лишних знаков типа *** или ---.
- Только чистый текст, готовый для тетради.
- ЗАПРЕЩЕНО использовать LaTeX форматирование!"""

DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        # Создаем таблицы если их нет
        conn.execute("CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, system_prompt TEXT, preferred_model TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, total_requests INTEGER DEFAULT 0, last_request_time INTEGER)")
        
        # Миграция: добавляем колонку preferred_model если её нет
        try:
            conn.execute("ALTER TABLE user_settings ADD COLUMN preferred_model TEXT")
            logging.info("✅ Добавлена колонка preferred_model")
        except sqlite3.OperationalError:
            # Колонка уже существует
            pass

def get_user_prompt(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT system_prompt FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        return res[0] if res else DEFAULT_PROMPT

def get_user_model(user_id):
    """Получить выбранную пользователем модель"""
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT preferred_model FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        # По умолчанию auto - сначала Gemini (для фото), потом Groq
        return res[0] if res else "auto"

def set_user_model(user_id, model_name):
    """Установить предпочитаемую модель для пользователя"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""INSERT INTO user_settings (user_id, preferred_model) 
                        VALUES (?, ?) 
                        ON CONFLICT(user_id) DO UPDATE SET preferred_model = ?""", 
                     (user_id, model_name, model_name))

def save_history(user_id, role, content):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.execute("DELETE FROM chat_history WHERE id IN (SELECT id FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT -1 OFFSET 20)", (user_id,))

def get_history(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()
        logging.info(f"📚 Загружено {len(rows)} сообщений из истории для пользователя {user_id}")
        return [g_types.Content(role=r, parts=[g_types.Part(text=c)]) for r, c in rows]

def update_stats(user_id):
    import time
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""INSERT INTO user_stats (user_id, total_requests, last_request_time) 
                        VALUES (?, 1, ?) 
                        ON CONFLICT(user_id) DO UPDATE SET 
                        total_requests = total_requests + 1, 
                        last_request_time = ?""", (user_id, int(time.time()), int(time.time())))

def get_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT total_requests FROM user_stats WHERE user_id = ?", (user_id,)).fetchone()
        return res[0] if res else 0

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"👤 Пользователь {message.from_user.id} запустил бота")
    welcome_text = """🎓 **Школьный помощник готов к работе!**

Просто отправь мне:
📝 Текст задания
📷 Фото из учебника
🖼 Скриншот задачи

**Команды:**
/clear — очистить историю диалога
/reset — сброс всех настроек
/stats — твоя статистика
/help — помощь

Я решаю задачи по всем предметам быстро и без лишних слов! 🚀"""
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """📚 **Как пользоваться ботом:**

1️⃣ Отправь текст задания или фото
2️⃣ Получи готовое решение для тетради
3️⃣ Используй /clear если нужен новый контекст

**Что я умею:**
✅ Математика, алгебра, геометрия
✅ Физика, химия, биология
✅ Русский язык, литература
✅ Английский и другие языки
✅ История, обществознание

**Особенности:**
• Без LaTeX — только чистый текст
• Степени через ² ³ ⁴ для удобства
• Готово для переписывания в тетрадь"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = message.from_user.id
    total = get_stats(user_id)
    logging.info(f"📊 Пользователь {user_id} запросил статистику: {total} запросов")
    await message.answer(f"📊 **Твоя статистика:**\n\nВсего запросов: {total}", parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    logging.info(f"🧹 Пользователь {message.from_user.id} очистил историю")
    await message.answer("🧠 Память очищена! Готов к новым задачам.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (message.from_user.id,))
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    logging.info(f"🔄 Пользователь {message.from_user.id} сбросил настройки")
    await message.answer("🔄 Все настройки сброшены до стандартного решебника.")

@dp.message(Command("model"))
async def cmd_model(message: types.Message):
    """Выбор модели для работы"""
    user_id = message.from_user.id
    current_model = get_user_model(user_id)
    
    # Доступные модели
    models_info = {
        "gemini": "🤖 Gemini (Google) - умный, с фото",
        "groq": "⚡ Groq (Llama) - быстрый, только текст",
        "auto": "🔄 Авто - сначала Gemini, потом Groq"
    }
    
    current_text = f"Текущая: {current_model or 'auto'}"
    
    text = f"""🎯 **Выбор модели**

{current_text}

**Доступные модели:**
{chr(10).join(f"• {info}" for info in models_info.values())}

**Команды:**
/model gemini - использовать только Gemini
/model groq - использовать только Groq
/model auto - автоматический выбор (по умолчанию)

**Примеры:**
`/model gemini` - для работы с фото
`/model groq` - для быстрых текстовых ответов"""
    
    # Если есть аргумент команды
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        model_choice = args[1].lower().strip()
        
        if model_choice in ["gemini", "groq", "auto"]:
            set_user_model(user_id, model_choice)
            logging.info(f"🎯 Пользователь {user_id} выбрал модель: {model_choice}")
            
            emoji = {"gemini": "🤖", "groq": "⚡", "auto": "🔄"}
            await message.answer(f"{emoji[model_choice]} Модель изменена на: {model_choice}")
        else:
            await message.answer("❌ Неверная модель. Используй: gemini, groq или auto")
    else:
        await message.answer(text, parse_mode="Markdown")

async def try_groq(user_id, request_text, history_text):
    """Запасной вариант через Groq API"""
    if not GROQ_API_KEY:
        return None
    
    try:
        logging.info(f"� Пробую Groq API для пользователя {user_id}")
        
        # Формируем историю для Groq
        messages = [{"role": "system", "content": DEFAULT_PROMPT}]
        
        # Добавляем историю (только текст, без фото)
        if history_text:
            messages.append({"role": "user", "content": history_text})
        
        messages.append({"role": "user", "content": request_text})
        
        async with httpx.AsyncClient(proxy=PROXY_URL, timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",  # Быстрая и умная модель
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                logging.info(f"✅ Groq API успешно ответил пользователю {user_id}")
                return answer
            else:
                logging.warning(f"⚠️ Groq API вернул код {response.status_code}")
                return None
                
    except Exception as e:
        logging.error(f"❌ Ошибка Groq API для пользователя {user_id}: {e}")
        return None

@dp.message()
async def handle_msg(message: types.Message):
    user_id = message.from_user.id
    user_text = message.caption or message.text or ""
    
    logging.info(f"📨 Получено сообщение от пользователя {user_id} (@{message.from_user.username}): {user_text[:50] if user_text else '[фото]'}...")
    
    request_text = user_text if user_text.strip() else "Реши/разбери то, что на фото"
    
    sys_instruction = get_user_prompt(user_id)
    history = get_history(user_id)
    preferred_model = get_user_model(user_id)
    
    logging.info(f"👤 Пользователь {user_id} имеет {len(history)} сообщений в истории")
    logging.info(f"🎯 Предпочитаемая модель: {preferred_model or 'auto'}")
    
    current_parts = [g_types.Part(text=request_text)]
    has_photo = False
    
    if message.photo:
        has_photo = True
        logging.info(f"📷 Обработка фото от пользователя {user_id}")
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        current_parts.append(g_types.Part.from_bytes(data=file_bytes.read(), mime_type="image/jpeg"))
    
    # Если пользователь выбрал только Groq
    if preferred_model == "groq" and not has_photo:
        logging.info(f"⚡ Пользователь {user_id} выбрал Groq, пропускаю Gemini")
        
        history_text = ""
        for h in history[-6:]:
            if h.parts and h.parts[0].text:
                history_text += f"{h.role}: {h.parts[0].text}\n"
        
        groq_response = await try_groq(user_id, request_text, history_text)
        
        if groq_response:
            save_history(user_id, "user", request_text)
            save_history(user_id, "model", groq_response)
            update_stats(user_id)
            
            await message.answer(groq_response, parse_mode=None)
            logging.info(f"✅ Groq ответ отправлен пользователю {user_id}")
            return
        else:
            await message.answer("⚠️ Groq API недоступен. Попробуй /model auto")
            return
    
    # Если пользователь выбрал только Groq, но отправил фото
    if preferred_model == "groq" and has_photo:
        await message.answer("⚠️ Groq не поддерживает фото. Используй /model gemini или /model auto")
        return
    
    # Пробуем модели Gemini (если не выбран только Groq)
    if preferred_model != "groq":
        for model_name in FALLBACK_MODELS:
            try:
                await bot.send_chat_action(message.chat.id, "typing")
                
                api_key = get_next_api_key()
                logging.info(f"🔑 Использую API ключ: ...{api_key[-8:]} для пользователя {user_id}")
                logging.info(f"🤖 Пробую модель: {model_name} для пользователя {user_id}")
                
                current_client = genai.Client(api_key=api_key)
                
                chat = current_client.chats.create(
                    model=model_name,
                    config=g_types.GenerateContentConfig(system_instruction=sys_instruction),
                    history=history
                )
                
                logging.info(f"💬 Чат создан для пользователя {user_id}, отправляю сообщение...")
                response = chat.send_message(message=current_parts)
                
                logging.info(f"📥 Ответ получен от {model_name} для пользователя {user_id}")
                
                if response.text:
                    logging.info(f"✅ Успешно! Модель {model_name} ответила пользователю {user_id} ({len(response.text)} символов)")
                    
                    # Очищаем LaTeX форматирование
                    clean_text = clean_latex(response.text)
                    
                    save_history(user_id, "user", request_text)
                    save_history(user_id, "model", clean_text)
                    update_stats(user_id)
                    
                    logging.info(f"📤 Отправляю ответ пользователю {user_id}...")
                    
                    # Отправляем без Markdown чтобы избежать ошибок форматирования
                    await message.answer(clean_text, parse_mode=None)
                    logging.info(f"✅ Ответ успешно отправлен пользователю {user_id}")
                    
                    return
                else:
                    logging.warning(f"⚠️ Пустой ответ от {model_name} для пользователя {user_id}, пробую следующую модель...")
                    continue
                    
            except Exception as e:
                error_str = str(e)
                
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    logging.warning(f"⚠️ Модель {model_name} перегружена для пользователя {user_id}, пробую следующую...")
                    continue
                
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    logging.warning(f"⚠️ Модель {model_name} не найдена для пользователя {user_id}, пробую следующую...")
                    continue
                
                elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logging.warning(f"⚠️ Квота модели {model_name} исчерпана для пользователя {user_id}, пробую следующую...")
                    continue
                
                elif "400" in error_str or "API_KEY_INVALID" in error_str or "expired" in error_str.lower():
                    logging.warning(f"⚠️ API ключ истек для модели {model_name}, пробую следующую...")
                    continue
                
                else:
                    logging.error(f"❌ Ошибка с моделью {model_name} для пользователя {user_id}: {e}")
                    continue
    
    # Если все Gemini модели не сработали и нет фото - пробуем Groq (только для auto режима)
    if not has_photo and preferred_model != "gemini":
        logging.info(f"🔄 Все Gemini модели недоступны, пробую Groq для пользователя {user_id}")
        
        history_text = ""
        for h in history[-6:]:
            if h.parts and h.parts[0].text:
                history_text += f"{h.role}: {h.parts[0].text}\n"
        
        groq_response = await try_groq(user_id, request_text, history_text)
        
        if groq_response:
            save_history(user_id, "user", request_text)
            save_history(user_id, "model", groq_response)
            update_stats(user_id)
            
            await message.answer(groq_response, parse_mode=None)
            logging.info(f"✅ Groq ответ отправлен пользователю {user_id}")
            return
    
    # Если вообще ничего не сработало
    logging.error(f"❌ Все модели недоступны для пользователя {user_id}")
    
    if has_photo:
        await message.answer(
            "⚠️ Все модели с поддержкой фото сейчас перегружены.\n\n"
            "Попробуй:\n"
            "• Через 1-2 минуты\n"
            "• Отправить текстом вместо фото"
        )
    else:
        await message.answer(
            "⚠️ Все модели сейчас перегружены.\n\n"
            "Попробуй через 1-2 минуты или используй /help"
        )

async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Вывод в консоль
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
        
        await bot.set_my_commands([
            BotCommand(command='start', description='🚀 Запуск бота'),
            BotCommand(command='help', description='❓ Помощь'),
            BotCommand(command='model', description='🎯 Выбор модели'),
            BotCommand(command='clear', description='🧹 Очистить контекст'),
            BotCommand(command='stats', description='📊 Статистика'),
            BotCommand(command='reset', description='🔄 Полный сброс')
        ])
        logger.info("✅ Команды бота установлены")
        
        logger.info("=" * 50)
        logger.info("🚀 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        logger.info(f"📝 Модель: {CURRENT_MODEL}")
        logger.info("=" * 50)
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при запуске: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
