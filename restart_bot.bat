@echo off
chcp 65001 >nul
echo ========================================
echo 🔄 ПЕРЕЗАПУСК БОТА С НОВЫМ ПРОМПТОМ
echo ========================================
echo.

echo 🗑️  Шаг 1: Очистка старой базы данных...
python clear_db.py
echo.

echo 🚀 Шаг 2: Запуск бота...
echo.
python bot_with_logs.py

pause
