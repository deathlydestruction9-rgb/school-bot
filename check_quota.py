import os
from google import genai
import time

# Прокси
os.environ['https_proxy'] = "http://127.0.0.1:10809"
os.environ['http_proxy'] = "http://127.0.0.1:10809"

# Твой API ключ
GEMINI_API_KEY = 'AIzaSyA9_1w5qp_S4A7AHqx0DQXMHKp_VVeB3w4'

client = genai.Client(api_key=GEMINI_API_KEY)

print("=" * 60)
print("🔍 Проверяю Gemini 3.1 Flash-Lite Preview...")
print("=" * 60)

# Тестируем новую модель
models_to_test = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
]

for model_name in models_to_test:
    try:
        print(f"\n📤 Тестирую модель: {model_name}")
        start = time.time()
        
        response = client.models.generate_content(
            model=model_name,
            contents='Скажи просто "ок"'
        )
        
        elapsed = time.time() - start
        print(f"✅ РАБОТАЕТ! Время: {elapsed:.2f}с")
        print(f"   Ответ: {response.text[:50]}")
        
    except Exception as e:
        error_str = str(e)
        print(f"❌ Ошибка: {error_str[:150]}")
        
        if "429" in error_str:
            print("   → Квота исчерпана")
        elif "404" in error_str:
            print("   → Модель не найдена")
        elif "400" in error_str:
            print("   → Ключ невалиден")
    
    time.sleep(1)

print("\n" + "=" * 60)
print("💡 Результат: используй первую рабочую модель")
print("=" * 60)
