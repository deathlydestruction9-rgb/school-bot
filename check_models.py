import os
from google import genai

# Прокси
os.environ['https_proxy'] = "http://127.0.0.1:10809"
os.environ['http_proxy'] = "http://127.0.0.1:10809"

# Твой API ключ
GEMINI_API_KEY = 'AIzaSyA9_1w5qp_S4A7AHqx0DQXMHKp_VVeB3w4'

client = genai.Client(api_key=GEMINI_API_KEY)

print("=" * 60)
print("🔍 Получаю список доступных моделей Gemini...")
print("=" * 60)

try:
    models = client.models.list()
    
    print("\n✅ Доступные модели:\n")
    
    for model in models:
        print(f"✅ {model.name}")
        print(f"   Название: {model.display_name if hasattr(model, 'display_name') else 'N/A'}")
        print(f"   Атрибуты: {dir(model)[:5]}...")  # Покажем первые атрибуты
        print()
    
    print("=" * 60)
    print("💡 Попробуй эти модели в боте")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
