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

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# ======================
# LOGGING
# ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MEMBER-BOT")

# ======================
# DATABASE
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
# PLAN MAP
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
        text=(
            f"👤 MEMBER BARU JOIN\n\n"
            f"🆔 ID: {user_id}\n"
            f"👤 Nama: {full_name}\n"
            f"📛 Username: @{username if username else '-'}\n\n"
            f"Pilih durasi:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# 🔥 FIXED JOIN DETECTOR (FULL COVER)
# ======================
async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cm = update.chat_member

    old = cm.old_chat_member.status
    new = cm.new_chat_member.status
    user = cm.new_chat_member.user

    logger.info(f"JOIN EVENT: {old} -> {new} | {user.id}")

    # DETECT SEMUA JENIS JOIN
    if old in ["left", "kicked"] and new in ["member", "administrator"]:

        if user.is_bot:
            return

        user_id = user.id
        username = user.username
        full_name = user.full_name

        # simpan database
        save_user(user_id, username, full_name)

        # welcome message di group
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Welcome {full_name}"
            )
        except:
            pass

        # kirim ke admin
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
    exp = datetime.utcnow() + timedelta(days=days)

    cursor.execute("""
        UPDATE users SET expire_time=? WHERE user_id=?
    """, (exp.isoformat(), user_id))
    conn.commit()

    await query.edit_message_text(
        f"✅ Member {user_id} aktif {days} hari\n⏰ Expire: {exp}"
    )

# ======================
# AUTO KICK SYSTEM
# ======================
async def checker(app):

    while True:
        now = datetime.utcnow()

        cursor.execute("""
            SELECT user_id, expire_time
            FROM users
            WHERE expire_time IS NOT NULL
        """)

        rows = cursor.fetchall()

        for user_id, exp in rows:

            exp_dt = datetime.fromisoformat(exp)

            if now >= exp_dt:
                try:
                    await app.bot.ban_chat_member(
                        chat_id=GROUP_ID,
                        user_id=user_id
                    )

                    await app.bot.unban_chat_member(
                        chat_id=GROUP_ID,
                        user_id=user_id
                    )

                    cursor.execute(
                        "DELETE FROM users WHERE user_id=?",
                        (user_id,)
                    )
                    conn.commit()

                    logger.info(f"KICKED {user_id}")

                except Exception as e:
                    logger.error(f"KICK ERROR: {e}")

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
        text += (
            f"ID: {r[0]}\n"
            f"Name: {r[2]}\n"
            f"Expire: {r[4]}\n"
            "━━━━━━━━━━\n"
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
    logger.info("BOT RUNNING...")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 🔥 IMPORTANT FIX: FULL CHAT MEMBER UPDATE
    app.add_handler(
        ChatMemberHandler(
            member_update,
            ChatMemberHandler.CHAT_MEMBER_UPDATED
        )
    )

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("member", member_list))
    app.add_handler(CommandHandler("start", start))

    app.post_init = post_init

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
