import asyncio
import logging
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand
import httpx
import pytesseract
from PIL import Image
import io

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = '8360715271:AAETGMaf74WPhzkocrWlZvL4gpNz5SkaR-I'
GROQ_API_KEY = "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"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

DEFAULT_PROMPT = """Ты — школьный помощник. Отвечай кратко и по делу, без лишних слов.

ОБЩИЕ ПРАВИЛА:
1. БЕЗ приветствий и воды. Сразу к ответу.
2. ЗАПРЕЩЕНО использовать LaTeX ($, $$, \\frac, \\cdot и т.д.)
3. ЗАПРЕЩЕНО использовать Markdown (**, __, *, _, ~~, `)
4. Только обычный текст!

ВАЖНО: Определи предмет по содержанию вопроса!

МАТЕМАТИКА И ФИЗИКА (только если есть числа, формулы, уравнения, расчёты):
Используй структуру:
Дано: (если есть)
Найти: (если есть)
Решение: (пошагово)
Ответ: (кратко)

Степени: ⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ (не используй ^)
Пример: x² + 5x - 3 = 0

ХИМИЯ (только если есть химические формулы и реакции):
Индексы маленькими: H₂O, CO₂, H₂SO₄
Коэффициенты обычными: 2H₂ + O₂ → 2H₂O

ВСЕ ОСТАЛЬНЫЕ ПРЕДМЕТЫ (русский, литература, история, обществознание, биология, география и т.д.):
НЕ используй структуру "Дано/Найти/Решение/Ответ"!
Отвечай естественным языком, как обычный человек.
Каждая мысль с новой строки для читабельности.
Просто отвечай на вопросы по порядку, кратко и понятно."""

DB_NAME = "bot_data.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, total_requests INTEGER DEFAULT 0, last_request_time INTEGER)")

def save_history(user_id, role, content):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.execute("DELETE FROM chat_history WHERE id IN (SELECT id FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT -1 OFFSET 20)", (user_id,))

def get_history(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()
        return [(r, c) for r, c in rows]

def update_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""INSERT INTO user_stats (user_id, total_requests, last_request_time) 
                        VALUES (?, 1, ?) 
                        ON CONFLICT(user_id) DO UPDATE SET 
                        total_requests = total_requests + 1, 
                        last_request_time = ?""", (user_id, int(time.time()), int(time.time())))

# --- GEMINI VISION ---
async def extract_text_with_gemini(image_bytes):
    """Извлечение текста из изображения с помощью Gemini Vision"""
    # Список моделей для попытки (в порядке приоритета)
    models_to_try = [
        'gemini-1.5-flash-8b',        # Самая легкая и быстрая
        'gemini-1.5-flash',            # Стандартная быстрая
        'gemini-1.5-flash-latest',     # Последняя версия
        'gemini-pro-vision',           # Старая стабильная
    ]
    
    for model_name in models_to_try:
        try:
            api_key = get_gemini_key()
            logging.info(f"🔍 Пробую {model_name} для распознавания изображения")
            
            client = genai.Client(api_key=api_key)
            
            # Создаём запрос с изображением
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=model_name,
                        contents=[
                            g_types.Content(
                                role='user',
                                parts=[
                                    g_types.Part(text="Извлеки весь текст с этого изображения. Верни только текст, без комментариев."),
                                    g_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                                ]
                            )
                        ]
                    )
                ),
                timeout=10.0
            )
            
            if response.text:
                text = response.text.strip()
                logging.info(f"📝 {model_name} извлёк текст: {text[:100]}...")
                return text
            else:
                logging.warning(f"⚠️ {model_name} не вернул текст, пробую следующую модель")
                continue
                
        except asyncio.TimeoutError:
            logging.error(f"❌ {model_name} таймаут (>10 сек), пробую следующую модель")
            continue
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                logging.warning(f"⚠️ {model_name} квота исчерпана, пробую следующую модель")
                continue
            elif "404" in error_str or "NOT_FOUND" in error_str:
                logging.warning(f"⚠️ {model_name} не найдена, пробую следующую модель")
                continue
            else:
                logging.error(f"❌ Ошибка {model_name}: {e}")
                continue
    
    logging.error("❌ Все Gemini модели недоступны")
    return None

# --- TESSERACT OCR (FALLBACK) ---
async def extract_text_with_tesseract(image_bytes):
    """Извлечение текста из изображения с помощью Tesseract OCR (fallback)"""
    try:
        logging.info("🔍 Использую Tesseract OCR (fallback)")
        image = Image.open(io.BytesIO(image_bytes))
        
        # Уменьшаем размер изображения для ускорения
        max_size = 1600
        if image.width > max_size or image.height > max_size:
            ratio = min(max_size / image.width, max_size / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logging.info(f"📐 Изображение уменьшено до {new_size}")
        
        # Tesseract работает синхронно
        loop = asyncio.get_event_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: pytesseract.image_to_string(image, lang='rus+eng')),
            timeout=15.0
        )
        
        # Очищаем текст
        text = ' '.join(text.split())
        
        if text and len(text.strip()) > 5:
            logging.info(f"📝 Tesseract извлёк текст: {text[:100]}...")
            return text
        else:
            logging.warning("⚠️ Tesseract не нашёл текст")
            return None
            
    except asyncio.TimeoutError:
        logging.error("❌ Tesseract таймаут (>15 сек)")
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка Tesseract: {e}")
        return None

# --- GROQ API ---
async def ask_groq(user_id, request_text, history):
    """Запрос к Groq API"""
    try:
        logging.info(f"⚡ Отправляю запрос в Groq для пользователя {user_id}")
        
        # Формируем историю для Groq
        messages = [{"role": "system", "content": DEFAULT_PROMPT}]
        
        # Добавляем последние 6 сообщений из истории
        for role, content in history[-6:]:
            messages.append({"role": role, "content": content})
        
        messages.append({"role": "user", "content": request_text})
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
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

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"👤 Пользователь {message.from_user.id} запустил бота")
    welcome_text = """🎓 Школьный помощник готов к работе!

Просто отправь мне:
📝 Текст задания
📷 Фото из учебника
🖼 Скриншот задачи

Команды:
/clear — очистить историю диалога
/reset — сброс настроек

Я решаю задачи по всем предметам быстро и без лишних слов! 🚀"""
    await message.answer(welcome_text)

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    logging.info(f"🧹 Пользователь {user_id} очистил историю диалога")
    await message.answer("🧠 История диалога очищена! Готов к новым задачам.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    logging.info(f"🔄 Пользователь {user_id} сбросил настройки")
    await message.answer("🔄 Все настройки сброшены.")

# --- ОБРАБОТКА СООБЩЕНИЙ ---
@dp.message()
async def handle_msg(message: types.Message):
    user_id = message.from_user.id
    user_text = message.caption or message.text or ""
    
    logging.info(f"📨 Получено сообщение от пользователя {user_id}: {user_text[:50] if user_text else '[фото]'}...")
    
    request_text = user_text if user_text.strip() else "Реши/разбери то, что на фото"
    history = get_history(user_id)
    
    # Если есть фото - используем Tesseract OCR
    if message.photo:
        logging.info(f"📷 Обработка фото от пользователя {user_id}")
        
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_data = file_bytes.read()
        
        # Извлекаем текст с фото через Tesseract
        ocr_text = await extract_text_with_tesseract(image_data)
        
        if ocr_text and len(ocr_text.strip()) > 5:
            combined_text = f"{user_text}\n\nТекст с фото:\n{ocr_text}" if user_text.strip() else f"Реши задание:\n{ocr_text}"
            
            groq_response = await ask_groq(user_id, combined_text, history)
            
            if groq_response:
                save_history(user_id, "user", combined_text)
                save_history(user_id, "assistant", groq_response)
                update_stats(user_id)
                
                await message.answer(groq_response)
                logging.info(f"✅ Ответ (OCR+Groq) отправлен пользователю {user_id}")
                return
        
        await message.answer("⚠️ Не удалось распознать текст на фото. Попробуй отправить текстом.")
        return
    
    # Текстовый запрос
    groq_response = await ask_groq(user_id, request_text, history)
    
    if groq_response:
        save_history(user_id, "user", request_text)
        save_history(user_id, "assistant", groq_response)
        update_stats(user_id)
        
        await message.answer(groq_response)
        logging.info(f"✅ Ответ отправлен пользователю {user_id}")
        return
    
    # Если Groq недоступен
    await message.answer("⚠️ Сервис временно недоступен. Попробуй через минуту.")

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
        
        await bot.set_my_commands([
            BotCommand(command='start', description='🚀 Запуск бота'),
            BotCommand(command='clear', description='🧹 Очистить историю'),
            BotCommand(command='reset', description='🔄 Полный сброс')
        ])
        logger.info("✅ Команды бота установлены")
        
        logger.info("=" * 50)
        logger.info("🚀 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        logger.info("=" * 50)
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при запуске: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
