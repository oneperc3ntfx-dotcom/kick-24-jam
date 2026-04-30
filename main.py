#!/usr/bin/env python3
import os
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# ======================
# LOGGING
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
    expire_time TEXT,
    status TEXT
)
""")
conn.commit()

# ======================
# PLAN
# ======================
PLAN_MAP = {
    "7d": 7,
    "1m": 30,
    "1y": 365
}

# ======================
# SAVE USER
# ======================
def save_user(user_id, username, full_name):
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        return False

    cursor.execute("""
        INSERT INTO users (user_id, username, full_name, join_time, expire_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        full_name,
        datetime.utcnow().isoformat(),
        None,
        "ACTIVE"
    ))

    conn.commit()
    return True

# ======================
# ADMIN PANEL
# ======================
async def send_admin_panel(context, user_id, full_name, username):

    keyboard = [
        [
            InlineKeyboardButton("7 Hari", callback_data=f"plan_7d_{user_id}"),
            InlineKeyboardButton("1 Bulan", callback_data=f"plan_1m_{user_id}"),
            InlineKeyboardButton("1 Tahun", callback_data=f"plan_1y_{user_id}")
        ]
    ]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👤 MEMBER BARU\n\nID: {user_id}\nNama: {full_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# FIXED JOIN DETECTOR (INI YANG PENTING)
# ======================
async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    result = update.chat_member
    old = result.old_chat_member.status
    new = result.new_chat_member.status

    user = result.new_chat_member.user

    # detect JOIN semua jenis
    if old in ["left", "kicked"] and new in ["member", "administrator"]:

        if user.is_bot:
            return

        user_id = user.id
        username = user.username
        full_name = user.full_name

        if save_user(user_id, username, full_name):
            logger.info(f"JOIN DETECTED: {user_id}")

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {full_name}"
            )

            await send_admin_panel(context, user_id, full_name, username)

# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return await query.answer("No access", show_alert=True)

    _, plan, user_id = query.data.split("_")
    user_id = int(user_id)

    days = PLAN_MAP.get(plan, 7)
    expire_time = datetime.utcnow() + timedelta(days=days)

    cursor.execute("""
        UPDATE users SET expire_time=? WHERE user_id=?
    """, (expire_time.isoformat(), user_id))
    conn.commit()

    await query.edit_message_text(
        f"✅ Set {days} hari untuk {user_id}"
    )

# ======================
# AUTO KICK
# ======================
async def checker(app):

    while True:
        now = datetime.utcnow()

        cursor.execute("SELECT user_id, expire_time FROM users WHERE expire_time IS NOT NULL")
        rows = cursor.fetchall()

        for user_id, exp in rows:

            exp_dt = datetime.fromisoformat(exp)

            if now >= exp_dt:
                try:
                    await app.bot.ban_chat_member(GROUP_ID, user_id)
                    await app.bot.unban_chat_member(GROUP_ID, user_id)

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()

                    logger.info(f"KICKED {user_id}")

                except Exception as e:
                    logger.error(f"KICK ERROR {e}")

        await asyncio.sleep(60)

# ======================
# MEMBER LIST
# ======================
async def member_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("No access")

    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()

    text = "👥 MEMBER LIST\n\n"

    for r in rows:
        text += f"ID: {r[0]}\nName: {r[2]}\nExpire: {r[4]}\n━━━━━━━━━━\n"

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
    logger.info("BOT RUNNING...")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 🔥 FIX IMPORTANT: detect join semua tipe
    app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("member", member_list))
    app.add_handler(CommandHandler("start", start))

    app.post_init = post_init

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
