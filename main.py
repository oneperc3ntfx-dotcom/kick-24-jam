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
    ContextTypes
)

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# ======================
# LOG
# ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MEMBER-BOT")

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
    expire_time TEXT
)
""")
conn.commit()

# ======================
# PLAN MAP
# ======================
PLAN = {
    "7d": 7,
    "1m": 30,
    "1y": 365
}

# ======================
# TEMP STORAGE
# ======================
pending = {}

# ======================
# /ADD USER
# ======================
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text("Usage: /add <user_id>")

    user_id = int(context.args[0])
    pending[user_id] = True

    keyboard = [
        [
            InlineKeyboardButton("7 Hari", callback_data=f"plan_7d_{user_id}"),
            InlineKeyboardButton("1 Bulan", callback_data=f"plan_1m_{user_id}"),
            InlineKeyboardButton("1 Tahun", callback_data=f"plan_1y_{user_id}")
        ]
    ]

    await update.message.reply_text(
        f"Set plan untuk user: {user_id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# BUTTON HANDLER
# ======================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    _, plan, user_id = q.data.split("_")
    user_id = int(user_id)

    days = PLAN[plan]
    expire = datetime.utcnow() + timedelta(days=days)

    # save DB
    cursor.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        "unknown",
        "unknown",
        datetime.utcnow().isoformat(),
        expire.isoformat()
    ))
    conn.commit()

    # ======================
    # 🔥 SINGLE USE INVITE LINK (FIX INTI)
    # ======================
    invite = await context.bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1,  # sekali pakai
        expire_date=datetime.utcnow() + timedelta(minutes=2)  # auto mati cepat
    )

    await q.edit_message_text(
        f"""
✅ MEMBER SET

ID: {user_id}
Plan: {days} hari
Expire: {expire}

🔗 SINGLE USE INVITE LINK:
{invite.invite_link}

⚠️ Link hanya bisa dipakai 1 kali & aktif 2 menit
"""
    )

# ======================
# AUTO KICK EXPIRED
# ======================
async def checker(app):

    while True:
        now = datetime.utcnow()

        cursor.execute("SELECT user_id, expire_time FROM users")
        rows = cursor.fetchall()

        for user_id, exp in rows:

            if not exp:
                continue

            exp_dt = datetime.fromisoformat(exp)

            if now >= exp_dt:
                try:
                    await app.bot.ban_chat_member(GROUP_ID, user_id)
                    await app.bot.unban_chat_member(GROUP_ID, user_id)

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()

                    logger.info(f"KICKED {user_id}")

                except Exception as e:
                    logger.error(e)

        await asyncio.sleep(30)

# ======================
# MEMBER LIST
# ======================
async def member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("No member")

    text = "👥 MEMBER LIST\n\n"

    for r in rows:
        user_id, username, name, join, exp = r

        text += (
            f"ID: {user_id}\n"
            f"Name: {name}\n"
            f"Expire: {exp}\n"
            f"━━━━━━━━━━\n"
        )

    await update.message.reply_text(text[:4000])

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif")

# ======================
# INIT
# ======================
async def post_init(app):
    asyncio.create_task(checker(app))
    logger.info("BOT RUNNING")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("member", member))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    app.post_init = post_init

    app.run_polling()

if __name__ == "__main__":
    main()
