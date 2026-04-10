import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from google.genai import types as g_types
from aiogram.exceptions import TelegramBadRequest

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = '8360715271:AAETGMaf74WPhzkocrWlZvL4gpNz5SkaR-I'
GEMINI_API_KEY = 'AIzaSyCoTUp4ffJbj5CBWFaIt9zsmrMcJtH_BSQ'

# Прокси (раскомментируй если нужен обход блокировок)
# os.environ['https_proxy'] = "http://127.0.0.1:10809"
# os.environ['http_proxy'] = "http://127.0.0.1:10809"

client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

CURRENT_MODEL = "gemini-2.0-flash-exp"

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

# --- БАЗА ДАННЫХ ---
DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, system_prompt TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, total_requests INTEGER DEFAULT 0, last_request_time INTEGER)")

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

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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
    await message.answer(f"📊 **Твоя статистика:**\n\nВсего запросов: {total}", parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    await message.answer("🧠 Память очищена! Готов к новым задачам.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (message.from_user.id,))
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (message.from_user.id,))
    await message.answer("🔄 Все настройки сброшены до стандартного решебника.")

@dp.message()
async def handle_msg(message: types.Message):
    user_id = message.from_user.id
    user_text = message.caption or message.text or ""
    
    logging.info(f"📨 Получено сообщение от пользователя {user_id}: {user_text[:50]}...")
    
    if not user_text.strip() and not message.photo:
        await message.answer("Отправь текст или фото задания")
        return
    
    sys_instruction = get_user_prompt(user_id)
    history = get_history(user_id)
    
    current_parts = [g_types.Part(text=user_text if user_text.strip() else "Реши/разбери то, что на фото")]
    
    if message.photo:
        logging.info(f"📷 Обработка фото от пользователя {user_id}")
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        current_parts.append(g_types.Part.from_bytes(data=file_bytes.read(), mime_type="image/jpeg"))
    
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        logging.info(f"🤖 Отправка запроса в Gemini для пользователя {user_id}")
        
        chat = client.chats.create(
            model=CURRENT_MODEL,
            config=g_types.GenerateContentConfig(system_instruction=sys_instruction),
            history=history
        )
        
        response = chat.send_message(message=current_parts)
        
        if response.text:
            logging.info(f"✅ Получен ответ от Gemini для пользователя {user_id} ({len(response.text)} символов)")
            save_history(user_id, "user", user_text if user_text.strip() else "Фото задания")
            save_history(user_id, "model", response.text)
            update_stats(user_id)
            
            try:
                await message.answer(response.text, parse_mode="Markdown")
                logging.info(f"📤 Ответ отправлен пользователю {user_id}")
            except TelegramBadRequest:
                await message.answer(response.text, parse_mode=None)
                logging.info(f"📤 Ответ отправлен пользователю {user_id} (без Markdown)")
    except Exception as e:
        error_msg = f"⚠️ Ошибка: {str(e)[:150]}"
        logging.error(f"❌ Ошибка для пользователя {user_id}: {e}")
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
            BotCommand(command='start', description='🚀 Запуск бота'),
            BotCommand(command='help', description='❓ Помощь'),
            BotCommand(command='clear', description='🧹 Очистить контекст'),
            BotCommand(command='stats', description='📊 Статистика'),
            BotCommand(command='reset', description='🔄 Полный сброс')
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
