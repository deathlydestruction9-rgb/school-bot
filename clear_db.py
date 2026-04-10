#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скрипт для очистки базы данных бота"""

import sqlite3
import os

DB_NAME = "bot_data.db"

if os.path.exists(DB_NAME):
    print(f"🗑️  Удаляю старую базу данных {DB_NAME}...")
    os.remove(DB_NAME)
    print("✅ База данных удалена!")
    print("\n📝 Теперь запусти бота заново - он создаст новую базу с обновленным промптом")
else:
    print(f"⚠️  База данных {DB_NAME} не найдена")
    print("Возможно она уже удалена или бот еще не запускался")

print("\n💡 Команды для запуска бота:")
print("   python bot_with_logs.py")
print("   или")
print("   ./bot_with_logs.py")
