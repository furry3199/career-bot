print("IMPORT OK")

import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from groq import Groq
import os
import nest_asyncio
nest_asyncio.apply()
# =====================
# 🔑 CONFIG
# =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
# 💰 SERVICES (ДОБАВЛЕНО ТОЛЬКО ЭТО)
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

YOOMONEY_LINK = "https://yoomoney.ru/to/YOUR_LINK"

# =====================
# 💰 SETTINGS
# =====================

FREE_LIMIT = 3
PRO_CODE = "SECRET123"

# =====================
# 🧠 STATE
# =====================

user_state = {}

# =====================
# 🧠 SYSTEM PROMPT (НЕ ТРОГАЛ ВООБЩЕ)
# =====================

SYSTEM_PROMPT = """
Ты карьерный AI-ассистент уровня senior HR.

Твоя задача:
делать честный, структурный и реалистичный анализ кандидата и вакансии.

--- 

🚨 ЖЁСТКИЕ ПРАВИЛА:

- НЕ выдумывай навыки
- НЕ додумывай информацию
- НЕ используй “возможно”, “скорее всего”
- используй ТОЛЬКО явные данные из текста

Если информации нет → считай, что её нет.

--- 

📊 ФОРМАТ:

📊 Шанс: X/100

📉 Почему не берут:
- причины

🟢 Сильные стороны:
- совпадения

🔴 Чего не хватает:
- пробелы

⚡ Что улучшить:
- навыки

🚀 План 7 дней:
- шаги
"""

# =====================
# 🚀 START (ТОЛЬКО ДОБАВИЛ КНОПКУ)
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
# 💰 CALLBACK (НОВОЕ)
# =====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    service = SERVICES.get(query.data)
    if not service:
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Оплатить {service['price']}₽", url=YOOMONEY_LINK)]
    ])

    await query.message.reply_text(
        f"🧾 {service['name']}\n\n"
        f"💰 Цена: {service['price']}₽\n"
        f"📌 {service['desc']}\n\n"
        "После оплаты приступим к разбору.",
        reply_markup=keyboard
    )

# =====================
# 🎯 HANDLER (ТВОЙ КОД НЕ ТРОГАЛ)
# =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        user_state[user_id] = {"mode": "idle", "vacancy": "", "profile": ""}

    state = user_state[user_id]

    # =====================
    # 💰 УСЛУГИ
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

    # =====================
    # 📊 О БОТЕ
    # =====================

    if text == "📊 О боте":
        await update.message.reply_text(
            "💼 Career AI — AI карьерный ассистент\n\n"

            "❌ Почему люди не проходят собеседования:\n"
            "— резюме не соответствует вакансии\n"
            "— не хватает ключевых навыков\n"
            "— слабая подача опыта\n"
            "— непонимание требований работодателя\n\n"

            "🤖 Что делает бот:\n"
            "— анализирует резюме и вакансию\n"
            "— сравнивает их 1 к 1\n"
            "— находит реальные причины отказа\n"
            "— показывает слабые места без воды\n"
            "— даёт план улучшения на 7 дней\n\n"

            "💰 Что ты получаешь:\n"
            "— честный HR-разбор\n"
            "— конкретные ошибки\n"
            "— понимание, почему не берут\n"
            "— готовый текст для отклика\n\n"

            "🚀 Результат:\n"
            "Ты понимаешь, что именно мешает получить работу и как это исправить"
        )
        return

    # =====================
    # 💳 PRO
    # =====================

    if text == "💳 PRO":
        await update.message.reply_text(
            "💳 PRO доступ\n\n— без лимитов\n— быстрые ответы\n\nАктивация: /activate SECRET123"
        )
        return

    # =====================
    # 📌 VACANCY
    # =====================

    if text == "📌 Вакансия":
        state["mode"] = "vacancy"
        await update.message.reply_text("📌 отправь вакансию")
        return

    if text == "👤 Профиль":
        state["mode"] = "profile"
        await update.message.reply_text("👤 отправь профиль")
        return

    if state["mode"] == "vacancy":
        state["vacancy"] = text
        state["mode"] = "idle"
        await update.message.reply_text("✅ вакансия сохранена")
        return

    if state["mode"] == "profile":
        state["profile"] = text
        state["mode"] = "idle"

        await update.message.reply_text("🧠 анализ...")

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"ВАКАНСИЯ:\n{state['vacancy']}\n\nПРОФИЛЬ:\n{state['profile']}"}
                ],
                temperature=0.2
            )

            result = response.choices[0].message.content
            await update.message.reply_text(result)

        except Exception as e:
            await update.message.reply_text(f"❌ ошибка: {e}")

# =====================
# 🔥 RUN
# =====================

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_callback))

print("🚀 bot running")
app.run_polling()
