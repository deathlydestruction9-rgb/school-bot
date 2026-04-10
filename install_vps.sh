#!/bin/bash
# Скрипт автоматической установки бота на VPS

echo "════════════════════════════════════════════════════════"
echo "  УСТАНОВКА TELEGRAM БОТА НА VPS"
echo "════════════════════════════════════════════════════════"
echo ""

# Обновляем систему
echo "📦 Обновление системы..."
apt update && apt upgrade -y

# Устанавливаем Python
echo "🐍 Установка Python..."
apt install python3 python3-pip python3-venv -y

# Проверяем версию
echo "✅ Версия Python:"
python3 --version

# Создаем папку
echo "📁 Создание папки для бота..."
mkdir -p /root/telegram-bot
cd /root/telegram-bot

# Создаем виртуальное окружение
echo "🔧 Создание виртуального окружения..."
python3 -m venv venv

# Активируем
source venv/bin/activate

echo ""
echo "════════════════════════════════════════════════════════"
echo "  СЛЕДУЮЩИЕ ШАГИ:"
echo "════════════════════════════════════════════════════════"
echo ""
echo "1. Загрузи файлы на сервер:"
echo "   • bot_with_logs.py"
echo "   • requirements.txt"
echo ""
echo "   Способ 1 (nano):"
echo "   nano bot_with_logs.py"
echo "   (скопируй код, вставь, Ctrl+O, Enter, Ctrl+X)"
echo ""
echo "   Способ 2 (scp с твоего ПК):"
echo "   scp bot_with_logs.py root@IP_VPS:/root/telegram-bot/"
echo "   scp requirements.txt root@IP_VPS:/root/telegram-bot/"
echo ""
echo "2. Установи зависимости:"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "3. Запусти бота:"
echo "   python3 bot_with_logs.py"
echo ""
echo "════════════════════════════════════════════════════════"
