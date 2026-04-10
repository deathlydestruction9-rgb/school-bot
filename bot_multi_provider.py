import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
import httpx

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = 'ВСТАВЬ_СВОЙ_ТОКЕН_ОТ_BOTFATHER'
GEMINI_API_KEY = 'ВСТАВЬ_СВОЙ_КЛЮЧ_GEMINI'
GROQ_API_KEY = ''  # https://console.groq.com (опционально)

# Прокси для обхода блокировок Google
# Если Google блокирует - попробуй отключить прокси (закомментируй строки ниже)
os.environ['https_proxy'] = "http://127.0.0.1:10809"
os.environ['http_proxy'] = "http://127.0.0.1:10809"
os.environ['no_proxy'] = "api.telegram.org"  # Telegram без прокси

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Провайдеры (все БЕСПЛАТНЫЕ с хорошими лимитами!)
PROVIDERS = {
    'gemini': {
        'name': '🔷 Gemini 2.0 Flash',
        'model': 'gemini-2.0-flash-exp',
        'supports_images': True,
        'speed': '⚡⚡⚡',
        'free_limit': '1500/день'
    },
    'gemini-vision': {
        'name': '👁️ Gemini 1.5 Flash',
        'model': 'gemini-1.5-flash',
        'supports_images': True,
        'speed': '⚡⚡',
        'free_limit': '1500/день'
    },
    'groq-vision': {
        'name': '🖼️ Groq Llama Vision',
        'model': 'llama-3.2-90b-vision-preview',
        'supports_images': True,
        'speed': '⚡⚡⚡',
        'free_limit': '14400/день'
    },
    'groq': {
        'name': '⚡ Groq Llama 3.3',
        'model': 'llama-3.3-70b-versatile',
        'supports_images': False,
        'speed': '⚡⚡⚡',
        'free_limit': '14400/день'
    }
}

DEFAULT_PROMPT = """Ты — универсальный школьный помощник. Твоя задача — выдавать готовые решения, которые можно сразу переписывать в тетрадь без исправлений.

ОБЩИЕ ПРАВИЛА:
1. НИКАКИХ приветствий ("Привет", "Вот решение") и лишней воды. Сразу к делу.
2. НИКОГДА не используй LaTeX (никаких $, \\, frac, \\cdot).
3. Используй жирный шрифт только для заголовков заданий и важных терминов.

АЛГЕБРА И МАТЕМАТИКА:
1. Деление пиши через : (двоеточие) или / (черта для дробей).
2. СТЕПЕНИ пиши СТРОГО маленькими цифрами ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹. Если степень больше 9, используй ^.
3. Умножение пиши через * или просто пропускай (например: 5a).
4. Структура: Номер. Пошаговое решение через знак = Ответ.

РУССКИЙ ЯЗЫК И ЛИТЕРАТУРА:
1. Перевод: Слово — перевод (без точек в конце).
2. Синтаксический анализ: расписывай по членам предложения (подлежащее, сказуемое и т.д.).
3. Сочинения: Пиши четко по теме, разделяй на абзацы (Вступление, Основная часть, Вывод). Используй грамотный, но доступный школьный язык, чтобы не выглядело слишком "нейросетевым".

ОФОРМЛЕНИЕ:
- Никаких таблиц (используй списки).
- Никаких лишних знаков типа *** или ---.
- Только чистый текст, готовый для тетради."""

DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, system_prompt TEXT, provider TEXT DEFAULT 'gemini')")
        conn.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, total_requests INTEGER DEFAULT 0)")

def get_user_provider(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT provider FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        return res[0] if res else 'gemini'

def set_user_provider(user_id, provider):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO user_settings (user_id, provider) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET provider = ?", 
                     (user_id, provider, provider))

def get_user_prompt(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT system_prompt FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        return res[0] if res else DEFAULT_PROMPT

def save_history(user_id, role, content):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.execute("DELETE FROM chat_history WHERE id IN (SELECT id FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT -1 OFFSET 20)", (user_id,))

def get_history(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()
        return rows

def update_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO user_stats (user_id, total_requests) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET total_requests = total_requests + 1", (user_id,))

# --- API КЛИЕНТЫ ---
async def call_gemini(messages, system_prompt, model_key='gemini', image_data=None):
    from google import genai
    from google.genai import types as g_types
    
    # Используем прокси для Google
    import httpx
    http_client = httpx.Client(
        proxies={
            "http://": "http://127.0.0.1:10809",
            "https://": "http://127.0.0.1:10809"
        },
        timeout=30.0
    )
    
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={'client': http_client}
    )
    
    history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        history.append(g_types.Content(role=role, parts=[g_types.Part(text=msg["content"])]))
    
    chat = client.chats.create(
        model=PROVIDERS[model_key]['model'],
        config=g_types.GenerateContentConfig(system_instruction=system_prompt),
        history=history
    )
    
    parts = [g_types.Part(text=messages[-1]["content"])]
    if image_data:
        parts.append(g_types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))
    
    response = chat.send_message(message=parts)
    return response.text

async def call_groq(messages, system_prompt, model_key='groq', image_data=None):
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    formatted_messages = [{"role": "system", "content": system_prompt}]
    
    for msg in messages:
        if msg == messages[-1] and image_data and model_key == 'groq-vision':
            # Groq Vision поддерживает изображения
            import base64
            img_b64 = base64.b64encode(image_data).decode('utf-8')
            formatted_messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": msg["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            })
        else:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": PROVIDERS[model_key]['model'],
                "messages": formatted_messages,
                "temperature": 0.7,
                "max_tokens": 2048
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            raise Exception(f"Groq API error: {response.status_code}")


# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = """🎓 **Школьный помощник готов к работе!**

Просто отправь мне:
📝 Текст задания
📷 Фото из учебника (только Gemini)

**Команды:**
/provider — выбрать нейросеть
/clear — очистить историю
/stats — статистика
/help — помощь"""
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("provider"))
async def cmd_provider(message: types.Message):
    keyboard = []
    
    for key, info in PROVIDERS.items():
        emoji = "📷" if info['supports_images'] else "📝"
        text = f"{emoji} {info['name']} {info['speed']}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f'provider_{key}')])
    
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    current = get_user_provider(message.from_user.id)
    current_info = PROVIDERS[current]
    
    await message.answer(
        f"🤖 **Выбор нейросети**\n\n"
        f"Текущая: {current_info['name']}\n"
        f"Скорость: {current_info['speed']}\n"
        f"Фото: {'✅' if current_info['supports_images'] else '❌'}\n"
        f"Лимит: {current_info['free_limit']}\n\n"
        f"Выбери провайдера:",
        reply_markup=keyboard_markup,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith('provider_'))
async def process_provider(callback: types.CallbackQuery):
    provider = callback.data.split('_')[1]
    set_user_provider(callback.from_user.id, provider)
    
    await callback.message.edit_text(
        f"✅ Выбрана нейросеть: {PROVIDERS[provider]['name']}",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    await message.answer("🧠 Память очищена!")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        res = conn.execute("SELECT total_requests FROM user_stats WHERE user_id = ?", (message.from_user.id,)).fetchone()
        total = res[0] if res else 0
    
    provider = get_user_provider(message.from_user.id)
    await message.answer(
        f"📊 **Статистика:**\n\nЗапросов: {total}\nПровайдер: {PROVIDERS[provider]['name']}",
        parse_mode="Markdown"
    )

async def handle_msg(message: types.Message):
    user_id = message.from_user.id
    user_text = message.caption or message.text or ""

    logging.info(f"📨 Получено сообщение от пользователя {user_id}: {user_text[:50] if user_text else 'фото'}...")

    if not user_text.strip() and not message.photo:
        await message.answer("Отправь текст или фото задания")
        return

    provider = get_user_provider(user_id)
    logging.info(f"🤖 Используется провайдер: {provider}")

    if message.photo and not PROVIDERS[provider]['supports_images']:
        await message.answer(
            f"⚠️ {PROVIDERS[provider]['name']} не поддерживает фото.\n\n"
            f"Используй /provider чтобы выбрать модель с поддержкой изображений 📷"
        )
        return

    request_text = user_text if user_text.strip() else "Реши/разбери то, что на фото"
    sys_instruction = get_user_prompt(user_id)
    history = get_history(user_id)

    messages = []
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": request_text})

    image_data = None
    if message.photo:
        logging.info(f"📷 Обработка фото от пользователя {user_id}")
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_data = file_bytes.read()

    try:
        await bot.send_chat_action(message.chat.id, "typing")
        logging.info(f"🔄 Отправка запроса в {provider} для пользователя {user_id}")

        if provider in ['gemini', 'gemini-vision']:
            response_text = await call_gemini(messages, sys_instruction, provider, image_data)
        elif provider in ['groq', 'groq-vision']:
            response_text = await call_groq(messages, sys_instruction, provider, image_data)
        else:
            await message.answer("⚠️ Неизвестный провайдер")
            return

        logging.info(f"✅ Получен ответ от {provider} ({len(response_text)} символов)")

        save_history(user_id, "user", request_text)
        save_history(user_id, "assistant", response_text)
        update_stats(user_id)

        try:
            await message.answer(response_text, parse_mode="Markdown")
            logging.info(f"📤 Ответ отправлен пользователю {user_id}")
        except TelegramBadRequest:
            await message.answer(response_text, parse_mode=None)
            logging.info(f"📤 Ответ отправлен (без Markdown)")

    except Exception as e:
        logging.error(f"❌ ОШИБКА для пользователя {user_id}: {e}")

        error_msg = f"⚠️ Ошибка: {str(e)[:150]}\n\n"

        if "API key" in str(e) or "401" in str(e):
            error_msg += "💡 API ключ не настроен. Попробуй другую модель через /provider"
        elif "quota" in str(e).lower() or "limit" in str(e).lower():
            error_msg += "💡 Лимит исчерпан. Переключись на другую модель через /provider"
        else:
            error_msg += "💡 Попробуй другую модель через /provider"

        await message.answer(error_msg)



async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Вывод в консоль
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
        
        await bot.set_my_commands([
            BotCommand(command='start', description='� Запуск'),
            BotCommand(command='provider', description='🤖 Выбор нейросети'),
            BotCommand(command='clear', description='🧹 Очистить контекст'),
            BotCommand(command='stats', description='📊 Статистика')
        ])
        logger.info("✅ Команды бота установлены")
        
        logger.info("🚀 Бот запущен и готов к работе!")
        logger.info(f"📝 Доступные модели: {', '.join(PROVIDERS.keys())}")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
