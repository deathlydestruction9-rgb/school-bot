import os
from google import genai

# Твои API ключи
api_keys = [
    'AIzaSyC2lMotTBWc-TFmoC1TKN9HMbiq-0irQ4Q',
    'AIzaSyA9_1w5qp_S4A7AHqx0DQXMHKp_VVeB3w4',
]

print("Проверка доступных моделей Gemini...\n")

for i, key in enumerate(api_keys, 1):
    print(f"=== API Ключ #{i} (последние 8 символов: ...{key[-8:]}) ===")
    try:
        client = genai.Client(api_key=key)
        models = client.models.list()
        
        flash_models = [m.name for m in models if 'flash' in m.name.lower() and 'generateContent' in str(m.supported_generation_methods)]
        
        if flash_models:
            print(f"✅ Найдено {len(flash_models)} Flash моделей:")
            for model in flash_models[:10]:  # Показываем первые 10
                print(f"   - {model}")
        else:
            print("❌ Flash модели не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print()
