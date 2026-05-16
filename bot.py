print("START BOT FILE")

import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PreCheckoutQueryHandler
)
from groq import Groq
import os
import nest_asyncio

nest_asyncio.apply()

# =====================
# 🔑 CONFIG
# =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

print("TOKEN:", TELEGRAM_BOT_TOKEN)
print("GROQ:", GROQ_API_KEY)
print("PAYMENT:", PROVIDER_TOKEN)

client = Groq(api_key=GROQ_API_KEY)

# =====================
# 🗄 DB
# =====================

conn = sqlite3.connect("career_v10.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    requests INTEGER DEFAULT 0,
    plan TEXT DEFAULT 'free'
)
""")
conn.commit()

# =====================
# 💰 SERVICES
# =====================

SERVICES = {
    "resume": {
        "name": "Разбор резюме",
        "price": 299,
        "desc": "Анализ резюме + ошибки + улучшения"
    },
    "rejection": {
        "name": "Почему не берут на работу",
        "price": 399,
        "desc": "Разбор причин отказов"
    },
    "full": {
        "name": "Полный карьерный разбор",
        "price": 599,
        "desc": "Резюме + стратегия + вакансии"
    }
}

# =====================
# 🧠 STATE
# =====================

user_state = {}

# =====================
# 🧠 SYSTEM PROMPT (НЕ ТРОГАЛ)
# =====================

SYSTEM_PROMPT = """
Ты карьерный AI-ассистент уровня senior HR.
Если тебе отправили вакансию, проси чтобы прислали еще профиль и наоборот!
Твоя задача:
делать честный, понятный и структурный разбор кандидата и вакансии.

---

📌 ГЛАВНЫЕ ПРАВИЛА:

- НЕ выдумывай навыки
- НЕ додумывай информацию
- НЕ используй “возможно”, “скорее всего”
- работай только с тем, что явно указано

---

📊 ЛОГИКА АНАЛИЗА:

1. Выпиши требования из вакансии
2. Выпиши навыки из профиля
3. Сравни их напрямую (есть / нет)
4. Определи главные причины несоответствия
5. Дай реалистичную оценку шансов

---

📊 ФОРМАТ ОТВЕТА:

📊 Шанс: X/100

📉 Почему не берут:
- 2–4 конкретные причины

🟢 Сильные стороны:
- только то, что явно совпадает с вакансией

🔴 Чего не хватает:
- конкретные навыки из вакансии

⚠️ Главный барьер:
- 1 ключевая причина отказа

🧭 Уровень:
- junior / junior+ / middle (с коротким объяснением)

⚡ Что улучшить:
- конкретные навыки / действия

🚀 План 7 дней:
- практические шаги

💬 Отклик:
- готовый текст для HR
"""

# =====================
# DB HELP
# =====================

def get_user(user_id):
    cursor.execute("SELECT requests, plan FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (user_id, requests, plan) VALUES (?, 0, 'free')", (user_id,))
        conn.commit()
        return 0, "free"

    return row

def add_request(user_id):
    cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id=?", (user_id,))
    conn.commit()

# =====================
# 🚀 START
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = {"mode": "idle", "vacancy": "", "profile": ""}

    keyboard = ReplyKeyboardMarkup(
        [["📌 Вакансия"], ["👤 Профиль"], ["💰 Услуги"], ["📊 О боте"], ["💳 PRO"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "💼 Career AI v10\n\nFREE: 3 анализа\nPRO: без ограничений",
        reply_markup=keyboard
    )

# =====================
# PAYMENT CALLBACK
# =====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    service = SERVICES.get(query.data)
    if not service:
        return

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=service["name"],
        description=service["desc"],
        payload=query.data,
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(service["name"], service["price"] * 100)]
    )

# =====================
# PRECHECKOUT
# =====================

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

# =====================
# SUCCESS PAYMENT
# =====================

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("""
    INSERT INTO users (user_id, requests, plan)
    VALUES (?, 0, 'pro')
    ON CONFLICT(user_id)
    DO UPDATE SET plan='pro'
    """, (user_id,))
    conn.commit()

    await update.message.reply_text("✅ PRO активирован")

# =====================
# HANDLER
# =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_state:
        user_state[user_id] = {"mode": "idle", "vacancy": "", "profile": ""}

    state = user_state[user_id]

    # =====================
    # SERVICES BUTTONS
    # =====================

    if text == "💰 Услуги":
        keyboard = [
            [InlineKeyboardButton("📄 Разбор резюме — 299₽", callback_data="resume")],
            [InlineKeyboardButton("❌ Почему не берут — 399₽", callback_data="rejection")],
            [InlineKeyboardButton("🚀 Полный разбор — 599₽", callback_data="full")]
        ]

        await update.message.reply_text(
            "💰 Услуги:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if text == "📊 О боте":
        await update.message.reply_text("""💼 Career AI — AI карьерный ассистент

Этот бот анализирует твоё резюме и вакансию так, как это делает реальный HR.

❌ Почему тебя могут не брать на работу:

— резюме не соответствует вакансии
— не хватает ключевых навыков
— опыт подан слишком слабо
— HR не видит ценности за 10–15 секунд
— ты откликаешься “как все”

🤖 Что делает бот:

— сравнивает резюме и вакансию 1 к 1
— находит реальные причины отказа
— показывает слабые места без воды
— не придумывает, а анализирует строго по фактам
— даёт конкретные правки, которые можно сразу использовать

📉 Что ты получаешь:

— честный разбор от “HR-логики”
— понимание, почему тебя игнорируют
— список конкретных ошибок
— что именно нужно исправить в резюме
— план улучшения на 7 дней

🚀 Результат:

Ты перестаёшь “просто откликаться” и начинаешь понимать,
как реально пройти отбор и получить оффер.""")
        return

    if text == "💳 PRO":
        await update.message.reply_text("PRO активируется после оплаты")
        return

    if text == "📌 Вакансия":
        state["mode"] = "vacancy"
        await update.message.reply_text("📌 отправь вакансию")
        return

    if text == "👤 Профиль":
        state["mode"] = "profile"
        await update.message.reply_text("👤 отправь профиль")
        return

    if state["mode"] == "vacancy" and text not in [
    "📌 Вакансия",
    "👤 Профиль",
    "💰 Услуги",
    "📊 О боте",
    "💳 PRO"
]:
        state["vacancy"] = text
        state["mode"] = "idle"
        await update.message.reply_text("✅ вакансия сохранена")
        return

    # =====================
    # 🔥 ANALYSIS + LIMIT LOGIC
    # =====================

    if state["mode"] == "profile" and text not in [
    "📌 Вакансия",
    "👤 Профиль",
    "💰 Услуги",
    "📊 О боте",
    "💳 PRO"
]:
        state["profile"] = text
        state["mode"] = "idle"

        requests, plan = get_user(user_id)

        if plan != "pro" and requests >= 3:
            await update.message.reply_text("🚫 Лимит 3/3 исчерпан\n💳 Купи PRO")
            return

        await update.message.reply_text("🧠 анализ...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"ВАКАНСИЯ:\n{state['vacancy']}\n\nПРОФИЛЬ:\n{state['profile']}"}
            ],
            temperature=0.2
        )

        await update.message.reply_text(response.choices[0].message.content)

        if plan != "pro":
            add_request(user_id)

# =====================
# RUN
# =====================

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_callback))

app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

print("🚀 bot running")

import asyncio

async def main():
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
