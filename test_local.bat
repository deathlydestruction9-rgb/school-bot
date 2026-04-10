@echo off
echo ========================================
echo   Тест бота на локальном ПК
echo ========================================
echo.

echo Проверка Python...
python --version
if errorlevel 1 (
    echo ОШИБКА: Python не установлен!
    pause
    exit
)

echo.
echo Установка зависимостей...
pip install aiogram==3.15.0 google-genai==1.71.0 httpx==0.28.1

echo.
echo ========================================
echo   Запуск бота (Ctrl+C для остановки)
echo ========================================
echo.

python bot_multi_provider.py

pause
