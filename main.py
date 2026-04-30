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
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
)

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

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
    expire_time TEXT
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
        INSERT INTO users VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        full_name,
        datetime.utcnow().isoformat(),
        None
    ))

    conn.commit()
    return True

# ======================
# ADMIN PANEL
# ======================
async def send_admin_panel(context, user_id, full_name, username):

    keyboard = [[
        InlineKeyboardButton("7 Hari", callback_data=f"plan_7d_{user_id}"),
        InlineKeyboardButton("1 Bulan", callback_data=f"plan_1m_{user_id}"),
        InlineKeyboardButton("1 Tahun", callback_data=f"plan_1y_{user_id}")
    ]]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"""
👤 MEMBER BARU

🆔 {user_id}
👤 {full_name}
📛 @{username if username else '-'}

Pilih plan:
""",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# 🔥 FIXED JOIN DETECTOR (INI INTI FIX)
# ======================
async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cm = update.chat_member

    old = cm.old_chat_member.status
    new = cm.new_chat_member.status
    user = cm.new_chat_member.user

    logger.info(f"{old} -> {new} | {user.id}")

    # detect ALL JOIN TYPES
    if old in ["left", "kicked"] and new in ["member", "administrator"]:

        if user.is_bot:
            return

        if save_user(user.id, user.username, user.full_name):

            # optional welcome (tidak tergantung grup message visible)
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"👋 Welcome {user.full_name}"
                )
            except:
                pass

            await send_admin_panel(context, user.id, user.full_name, user.username)

# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    _, plan, user_id = q.data.split("_")
    user_id = int(user_id)

    days = PLAN_MAP[plan]
    exp = datetime.utcnow() + timedelta(days=days)

    cursor.execute("""
        UPDATE users SET expire_time=? WHERE user_id=?
    """, (exp.isoformat(), user_id))
    conn.commit()

    await q.edit_message_text(f"✅ Set {days} hari untuk {user_id}")

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

        await asyncio.sleep(30)

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

    # 🔥 ONLY THIS IS REQUIRED FOR JOIN DETECTION
    app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("member", member_list))
    app.add_handler(CommandHandler("start", start))

    app.post_init = post_init

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
