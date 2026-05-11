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

SYSTEM_PROMPT = """Ты карьерный AI-ассистент уровня senior HR.
Если тебе отправили вакансию, проси чтобы прислали еще профиль и наоборот!
Твоя задача:
делать честный, понятный и структурный разбор кандидата и вакансии.
"""

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
# 💳 PAYMENT FLOW
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
        prices=[
            LabeledPrice(service["name"], service["price"] * 100)
        ]
    )

# =====================
# ⚡ PRECHECKOUT
# =====================

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

# =====================
# ✅ SUCCESS PAYMENT (PRO FIX)
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
# 🎯 HANDLER (PRO LOGIC ADDED)
# =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        user_state[user_id] = {"mode": "idle", "vacancy": "", "profile": ""}

    state = user_state[user_id]

    # 🔥 GET USER PLAN
    cursor.execute("SELECT requests, plan FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        requests = 0
        plan = "free"
        cursor.execute("INSERT INTO users (user_id, requests, plan) VALUES (?, 0, 'free')", (user_id,))
        conn.commit()
    else:
        requests, plan = row

    # 💰 LIMIT LOGIC
    if plan != "pro" and requests >= 3:
        await update.message.reply_text("❌ Лимит 3/3\n💳 Купи PRO")
        return

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

    if state["mode"] == "profile":
        state["profile"] = text
        state["mode"] = "idle"

        await update.message.reply_text("🧠 анализ...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"ВАКАНСИЯ:\n{state['vacancy']}\n\nПРОФИЛЬ:\n{state['profile']}"}
            ],
            temperature=0.2
        )

        # ➕ increase requests only if free
        if plan != "pro":
            cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id=?", (user_id,))
            conn.commit()

        await update.message.reply_text(response.choices[0].message.content)

# =====================
# 🔥 RUN
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
