
import asyncio
import os
import sqlite3
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "pulse_users.db"

bot = Bot(token=TOKEN) if TOKEN else None
dp = Dispatcher()

# Временное хранилище загружаемых графиков
sessions = {}

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                free_used INTEGER DEFAULT 0,
                daily_used INTEGER DEFAULT 0,
                daily_date TEXT,
                plan TEXT DEFAULT 'FREE'
            )
        """)

def get_user(user_id):
    today = str(date.today())

    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )

        user = conn.execute(
            "SELECT free_used, daily_used, daily_date, plan "
            "FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        free_used, daily_used, daily_date, plan = user

        if daily_date != today:
            daily_used = 0
            conn.execute(
                "UPDATE users SET daily_used = 0, daily_date = ? "
                "WHERE user_id = ?",
                (today, user_id)
            )

        return free_used, daily_used, plan

def use_analysis(user_id):
    today = str(date.today())

    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE users SET free_used = free_used + 1, "
            "daily_used = daily_used + 1, daily_date = ? "
            "WHERE user_id = ?",
            (today, user_id)
        )

@dp.message(CommandStart())
async def start(message: Message):
    sessions.pop(message.from_user.id, None)

    await message.answer(
        "⚡ PULSE AI\n\n"
        "Интеллектуальный анализ торговых графиков.\n\n"
        "Тебе нужно отправить 3 скриншота одного инструмента:\n"
        "1️⃣ M1 — минутный график\n"
        "2️⃣ M5 — пятиминутный график\n"
        "3️⃣ M15 — пятнадцатиминутный график\n\n"
        "🎁 Новым пользователям доступны 2 бесплатные попытки.\n\n"
        "Команды:\n"
        "/analyze — начать анализ\n"
        "/status — проверить лимит"
    )

@dp.message(Command("status"))
async def status(message: Message):
    free_used, daily_used, plan = get_user(message.from_user.id)

    if plan == "FREE":
        remaining = max(0, 2 - free_used)
        await message.answer(
            f"📊 Твой тариф: FREE\n"
            f"Бесплатных анализов осталось: {remaining} из 2"
        )
    else:
        limit = 10 if plan == "START" else 50
        await message.answer(
            f"📊 Твой тариф: {plan}\n"
            f"Анализов сегодня: {daily_used} из {limit}"
        )

@dp.message(Command("analyze"))
async def analyze(message: Message):
    user_id = message.from_user.id
    free_used, daily_used, plan = get_user(user_id)

    if plan == "FREE" and free_used >= 2:
        await message.answer(
            "🎁 Бесплатные попытки закончились.\n\n"
            "Подписки START и PRO скоро появятся."
        )
        return

    if plan == "START" and daily_used >= 10:
        await message.answer("Дневной лимит START исчерпан.")
        return

    if plan == "PRO" and daily_used >= 50:
        await message.answer("Дневной лимит PRO исчерпан.")
        return

    sessions[user_id] = {}

    await message.answer(
        "📈 Начинаем новый анализ!\n\n"
        "Отправь скриншот графика M1 с подписью M1.\n"
        "После него отправь M5 и M15.\n\n"
        "Важно: все три графика должны быть одного инструмента."
    )

@dp.message(F.photo)
async def receive_photo(message: Message):
    user_id = message.from_user.id

    if user_id not in sessions:
        await message.answer(
            "Сначала нажми /analyze, чтобы начать анализ."
        )
        return

    caption = (message.caption or "").strip().upper()

    if caption not in ("M1", "M5", "M15"):
        await message.answer(
            "❗ Добавь к изображению подпись M1, M5 или M15."
        )
        return

    if caption in sessions[user_id]:
        await message.answer(
            f"График {caption} уже получен. Отправь другой таймфрейм."
        )
        return

    sessions[user_id][caption] = message.photo[-1].file_id

    received = len(sessions[user_id])

    if received < 3:
        missing = [
            tf for tf in ("M1", "M5", "M15")
            if tf not in sessions[user_id]
        ]
        await message.answer(
            f"✅ {caption} получен!\n"
            f"Осталось графиков: {', '.join(missing)}"
        )
        return

    free_used, daily_used, plan = get_user(user_id)

    if plan == "FREE" and free_used >= 2:
        sessions.pop(user_id, None)
        await message.answer("Бесплатные попытки закончились.")
        return

    if plan == "START" and daily_used >= 10:
        sessions.pop(user_id, None)
        await message.answer("Дневной лимит START исчерпан.")
        return

    if plan == "PRO" and daily_used >= 50:
        sessions.pop(user_id, None)
        await message.answer("Дневной лимит PRO исчерпан.")
        return

    use_analysis(user_id)
    sessions.pop(user_id, None)

    await message.answer(
        "✅ Все три графика получены!\n\n"
        "M1, M5 и M15 приняты.\n\n"
        "⚙️ Приём изображений работает. "
        "Подключение искусственного интеллекта для анализа "
        "будет следующим этапом.\n\n"
        "Результат пока не формируется — AI ещё не подключён."
    )

@dp.message()
async def other_messages(message: Message):
    await message.answer(
        "Используй /analyze, чтобы начать анализ графиков."
    )

async def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN!")

    init_db()
    print("PULSE AI запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
