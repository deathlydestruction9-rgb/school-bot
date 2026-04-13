import asyncio
import logging
import os
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from google.genai import types as g_types
from aiogram.exceptions import TelegramBadRequest
import httpx

# Отслеживание последнего использования каждого ключа
last_key_usage = {}
KEY_COOLDOWN = 2  # Секунды между запросами к одному ключу

def clean_latex(text):
    """Удаляет LaTeX и Markdown форматирование из текста"""
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
    
    # УДАЛЯЕМ MARKDOWN ФОРМАТИРОВАНИЕ
    # Удаляем жирный шрифт ** и __
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **текст** -> текст
    text = re.sub(r'__([^_]+)__', r'\1', text)      # __текст__ -> текст
    # Удаляем курсив * и _
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *текст* -> текст
    text = re.sub(r'_([^_]+)_', r'\1', text)        # _текст_ -> текст
    # Удаляем зачеркнутый ~~
    text = re.sub(r'~~([^~]+)~~', r'\1', text)      # ~~текст~~ -> текст
    # Удаляем код `
    text = re.sub(r'`([^`]+)`', r'\1', text)        # `текст` -> текст
    
    return text

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = '8360715271:AAETGMaf74WPhzkocrWlZvL4gpNz5SkaR-I'

# API ключ Gemini
GEMINI_API_KEYS = [
    'AIzaSyAlJ1id_gghgXK2CLeJg4QuzruXdtObJ8U',
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

# БЕЗ ПРОКСИ (VPS в Германии)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

CURRENT_MODEL = "gemini-2.0-flash-lite"

# Список моделей для автоматического переключения (ТОЛЬКО БЫСТРЫЕ!)
FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",          # Самая быстрая
    "gemini-2.0-flash-lite-001",      # Быстрая версия 001
    "gemini-2.0-flash",               # Стандартная быстрая
    "gemini-2.0-flash-001",           # Стандартная 001
    "gemini-2.5-flash",               # Новая быстрая
]

DEFAULT_PROMPT = """Ты — универсальный школьный помощник. Твоя задача — выдавать готовые решения, которые можно сразу переписывать в тетрадь без исправлений.

ОБЩИЕ ПРАВИЛА:
1. НИКАКИХ приветствий ("Привет", "Вот решение") и лишней воды. Сразу к делу.
2. СТРОГО ЗАПРЕЩЕНО использовать LaTeX (НИКАКИХ $, $$, \\, frac, \\cdot, \\begin, \\end).
3. СТРОГО ЗАПРЕЩЕНО использовать Markdown форматирование (НИКАКИХ **, __, *, _, ~~, `).
4. ТОЛЬКО ОБЫЧНЫЙ ТЕКСТ БЕЗ ВЫДЕЛЕНИЙ! Никаких жирных или курсивных шрифтов!

АЛГЕБРА, ГЕОМЕТРИЯ И МАТЕМАТИКА:
1. КРАТКОСТЬ: Минимум объяснений, максимум решения. Если нужно пояснение - 1-2 предложения в начале.
2. СТРУКТУРА:
   • Дано: (если есть)
   • Найти: (если есть)
   • Решение: (пошаговое, каждый шаг с новой строки)
   • Ответ: (четко и кратко)
3. НЕ РАСПИСЫВАЙ очевидные вещи ("сумма углов треугольника 180°" - просто используй это).
4. СТЕПЕНИ: ⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁻¹ ⁻² ⁻³ (НИКОГДА не используй ^)
5. Деление: через : или /
6. Умножение: через * или пропускай (5a)

ПРИМЕРЫ ПРАВИЛЬНОГО ОФОРМЛЕНИЯ:
✅ Правильно:
   Дано: AB || CD, угол VLD = 60°, угол KON = 87°
   Найти: угол OKN
   
   Решение:
   1. AB || CD → угол LKN = 60° (соответственные углы)
   2. В треугольнике OKN: 180° - 87° - 60° = 33°
   
   Ответ: 33°

✅ Правильно: 4¹¹ * 4⁻⁹ = 4² = 16
✅ Правильно: (x⁻³)⁴ * x¹⁴ = x⁻¹² * x¹⁴ = x²

❌ НЕПРАВИЛЬНО: Слишком много текста и объяснений каждого шага
❌ НЕПРАВИЛЬНО: $x^2$ или x^2 (используй x²)


ХИМИЯ:
1. Индексы пиши маленькими цифрами: H₂O, CO₂, H₂SO₄, Ca(OH)₂
2. КОЭФФИЦИЕНТЫ пиши ОБЫЧНЫМИ цифрами перед формулой БЕЗ ВЫДЕЛЕНИЯ!
3. Стрелку реакции пиши как →

ПРИМЕРЫ ХИМИЧЕСКИХ УРАВНЕНИЙ:
✅ Правильно: 2H₂ + O₂ → 2H₂O
✅ Правильно: 2Mg + O₂ → 2MgO
✅ Правильно: 2Na + 2H₂O → 2NaOH + H₂
✅ Правильно: 4P + 5O₂ → 2P₂O₅
❌ НЕПРАВИЛЬНО: **2**H₂ + O₂ → **2**H₂O
❌ НЕПРАВИЛЬНО: **2**Mg + O₂ → **2**MgO
❌ НЕПРАВИЛЬНО: 2H2 + O2 → 2H2O (индексы должны быть маленькими!)

РУССКИЙ ЯЗЫК И ЛИТЕРАТУРА:
1. ФОРМАТИРОВАНИЕ: Каждое предложение с новой строки, ответ с новой строки через отступ или пустую строку.
2. Грамматические основы: 
   Предложение.
   Грамматические основы: подлежащее + сказуемое.
3. Перевод: Слово — перевод (без точек в конце).
4. Синтаксический анализ: расписывай по членам предложения (подлежащее, сказуемое и т.д.).
5. Сочинения: четко по теме, абзацы (Вступление, Основная часть, Вывод). Грамотный школьный язык.
6. ЧИТАБЕЛЬНОСТЬ: Не слепляй текст в одну строку! Разделяй логические части.

ПРИМЕР ПРАВИЛЬНОГО ОФОРМЛЕНИЯ (русский язык):
✅ Правильно:
   1. Восходил месяц, и красным столбом отражался на другой стороне пруда.
   Грамматические основы: месяц восходил, отражался.
   
   2. Прошло ещё несколько дней, и каждая новая встреча вносила отчуждение.
   Грамматические основы: прошло дней, встреча вносила.

❌ НЕПРАВИЛЬНО:
   Восходил месяц, и красным столбом отражался на другой стороне пруда. Грамматические основы: месяц восходил, отражался. Прошло ещё несколько дней...
   (всё слеплено в одну строку - нечитабельно!)

ОФОРМЛЕНИЕ:
- НИКАКИХ звездочек ** или __ для выделения текста!
- НИКАКИХ знаков форматирования (* _ ~ ` и т.д.)!
- Никаких таблиц (используй списки).
- Никаких лишних знаков типа *** или ---.
- Только чистый текст, готовый для тетради.
- ЗАПРЕЩЕНО использовать LaTeX и Markdown форматирование!"""

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
/model — выбор модели (Gemini/Groq)
/reset — сброс всех настроек

Я решаю задачи по всем предметам быстро и без лишних слов! 🚀"""
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect(DB_NAME) as conn:
        # Удаляем только историю сообщений, НЕ настройки пользователя
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    logging.info(f"🧹 Пользователь {user_id} очистил историю диалога")
    await message.answer("🧠 История диалога очищена! Готов к новым задачам.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (message.from_user.id,))
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    logging.info(f"🔄 Пользователь {message.from_user.id} сбросил настройки")
    await message.answer("🔄 Все настройки сброшены до стандартного решебника.")

@dp.message(Command("model"))
async def cmd_model(message: types.Message):
    """Выбор модели для работы через кнопки"""
    user_id = message.from_user.id
    current_model = get_user_model(user_id) or "auto"
    
    # Создаем inline кнопки для выбора модели
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🤖 Gemini" + (" ✅" if current_model == "gemini" else ""),
                callback_data="model_gemini"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚡ Groq" + (" ✅" if current_model == "groq" else ""),
                callback_data="model_groq"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Авто" + (" ✅" if current_model == "auto" else ""),
                callback_data="model_auto"
            )
        ]
    ])
    
    text = f"""🎯 Выбор модели

Текущая модель: {current_model}

🤖 Gemini - умный, работает с фото
⚡ Groq - быстрый, только текст
🔄 Авто - сначала Gemini, потом Groq"""
    
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("model_"))
async def process_model_selection(callback: types.CallbackQuery):
    """Обработка выбора модели через кнопки"""
    user_id = callback.from_user.id
    model_choice = callback.data.replace("model_", "")
    
    # Сохраняем выбор
    set_user_model(user_id, model_choice)
    logging.info(f"🎯 Пользователь {user_id} выбрал модель: {model_choice}")
    
    # Обновляем сообщение с новыми кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🤖 Gemini" + (" ✅" if model_choice == "gemini" else ""),
                callback_data="model_gemini"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚡ Groq" + (" ✅" if model_choice == "groq" else ""),
                callback_data="model_groq"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Авто" + (" ✅" if model_choice == "auto" else ""),
                callback_data="model_auto"
            )
        ]
    ])
    
    emoji = {"gemini": "🤖", "groq": "⚡", "auto": "🔄"}
    text = f"""🎯 Выбор модели

Текущая модель: {model_choice}

🤖 Gemini - умный, работает с фото
⚡ Groq - быстрый, только текст
🔄 Авто - сначала Gemini, потом Groq"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(f"{emoji[model_choice]} Модель изменена на: {model_choice}")

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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            BotCommand(command='model', description='🎯 Выбор модели'),
            BotCommand(command='clear', description='🧹 Очистить историю'),
            BotCommand(command='reset', description='� Полный сброс')
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
