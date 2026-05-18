#!/usr/bin/env python3

import os
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("AUTHORIZED_USER_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# ======================
# LOGGING
# ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BOT")

# ======================
# DB
# ======================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    join_time TEXT,
    expire_time TEXT,
    plan TEXT
)
""")
conn.commit()

# ======================
# PLAN
# ======================
PLAN = {
    "24h": {"days": 1, "label": "1 Hari", "price": "25K"},
    "7d": {"days": 7, "label": "7 Hari", "price": "49K"},
    "1m": {"days": 30, "label": "1 Bulan", "price": "99K"},
    "1y": {"days": 365, "label": "1 Tahun", "price": "999K"},
}

pending_proofs = {}

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🔥 1 Hari", callback_data="buy_24h")],
        [InlineKeyboardButton("🚀 7 Hari", callback_data="buy_7d")],
        [InlineKeyboardButton("👑 1 Bulan", callback_data="buy_1m")],
        [InlineKeyboardButton("💎 1 Tahun", callback_data="buy_1y")]
    ]

    await update.message.reply_text(
        "Pilih paket:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# CALLBACK BUY (FIXED 100%)
# ======================
async def buy_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query

    print("🔥 CALLBACK RECEIVED:", q.data)

    try:
        await q.answer()  # WAJIB

        plan_key = q.data.replace("buy_", "")

        print("📦 PLAN:", plan_key)

        if plan_key not in PLAN:
            await q.message.reply_text("❌ INVALID PLAN")
            return

        context.user_data["selected_plan"] = plan_key
        plan = PLAN[plan_key]

        await q.message.reply_text(
            f"""
📦 PILIHAN:

{plan['label']}
💰 {plan['price']}
"""
        )

    except Exception as e:
        print("❌ BUY ERROR:", e)
        try:
            await q.answer("ERROR", show_alert=True)
        except:
            pass

# ======================
# PHOTO
# ======================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    plan_key = context.user_data.get("selected_plan")

    if not plan_key:
        await update.message.reply_text("Pilih paket dulu /start")
        return

    pending_proofs[user.id] = {
        "photo": update.message.photo[-1].file_id,
        "plan": plan_key
    }

    await update.message.reply_text("📥 Bukti diterima")

# ======================
# ADMIN APPROVE / REJECT
# ======================
async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    data = q.data.split("_")
    action = data[0]

    if action == "approve":

        plan_key = data[1]
        user_id = int(data[2])

        plan = PLAN[plan_key]
        now = datetime.utcnow()
        expire = now + timedelta(days=plan["days"])

        cursor.execute("""
            INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            "user",
            "user",
            now.isoformat(),
            expire.isoformat(),
            plan["label"]
        ))
        conn.commit()

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Approved sampai {expire}"
        )

        await q.edit_message_text("APPROVED")

    elif action == "reject":

        user_id = int(data[1])

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ REJECTED"
        )

        await q.edit_message_text("REJECTED")

# ======================
# TEXT HANDLER
# ======================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gunakan /start")

# ======================
# CHECKER AUTO KICK
# ======================
async def checker(app):

    while True:

        now = datetime.utcnow()

        cursor.execute("SELECT user_id, expire_time FROM users")
        rows = cursor.fetchall()

        for user_id, exp in rows:

            try:
                if not exp:
                    continue

                if now >= datetime.fromisoformat(exp):

                    await app.bot.ban_chat_member(GROUP_ID, user_id)
                    await app.bot.unban_chat_member(GROUP_ID, user_id)

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()

                    print("KICKED:", user_id)

            except Exception as e:
                print("KICK ERROR:", e)

        await asyncio.sleep(30)

# ======================
# POST INIT
# ======================
async def post_init(app):
    asyncio.create_task(checker(app))
    print("CHECKER RUNNING")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(buy_button, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.post_init = post_init

    print("BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
