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
# LOAD ENV
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

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (user_id,)
    )

    existing = cursor.fetchone()

    if existing:
        return False

    join_time = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO users
        (user_id, username, full_name, join_time, expire_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        full_name,
        join_time,
        None,
        "ACTIVE"
    ))

    conn.commit()

    return True

# ======================
# SEND ADMIN BUTTON
# ======================
async def send_admin_panel(context, user_id, full_name, username):

    keyboard = [
        [
            InlineKeyboardButton(
                "7 Hari",
                callback_data=f"plan_7d_{user_id}"
            ),
            InlineKeyboardButton(
                "1 Bulan",
                callback_data=f"plan_1m_{user_id}"
            ),
            InlineKeyboardButton(
                "1 Tahun",
                callback_data=f"plan_1y_{user_id}"
            ),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👤 MEMBER BARU JOIN\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Nama: {full_name}\n"
        f"📛 Username: @{username if username else '-'}\n\n"
        f"Pilih durasi member:"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=text,
        reply_markup=reply_markup
    )

# ======================
# DETECT MEMBER JOIN
# ======================
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:

        # skip bot
        if member.is_bot:
            continue

        user_id = member.id
        username = member.username
        full_name = member.full_name

        is_new = save_user(
            user_id,
            username,
            full_name
        )

        if not is_new:
            continue

        logger.info(f"NEW MEMBER: {user_id}")

        # welcome message
        await update.message.reply_text(
            f"👋 Welcome {full_name}\n\n"
            f"Selamat datang di grup 🚀"
        )

        # send to admin
        await send_admin_panel(
            context,
            user_id,
            full_name,
            username
        )

# ======================
# DETECT INVITE LINK JOIN
# ======================
async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    result = update.chat_member

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    # detect real join
    if old_status in ["left", "kicked"] and new_status in ["member", "administrator"]:

        member = result.new_chat_member.user

        if member.is_bot:
            return

        user_id = member.id
        username = member.username
        full_name = member.full_name

        is_new = save_user(
            user_id,
            username,
            full_name
        )

        if not is_new:
            return

        logger.info(f"INVITE JOIN: {user_id}")

        await send_admin_panel(
            context,
            user_id,
            full_name,
            username
        )

# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return await query.answer("No access", show_alert=True)

    try:
        _, plan, user_id = query.data.split("_")

        user_id = int(user_id)

    except:
        return

    days = PLAN_MAP.get(plan)

    if not days:
        return

    expire_time = datetime.utcnow() + timedelta(days=days)

    cursor.execute("""
        UPDATE users
        SET expire_time=?
        WHERE user_id=?
    """, (
        expire_time.isoformat(),
        user_id
    ))

    conn.commit()

    await query.edit_message_text(
        f"✅ Membership updated\n\n"
        f"🆔 User: {user_id}\n"
        f"📅 Plan: {days} hari\n"
        f"⛔ Expire: {expire_time.strftime('%Y-%m-%d %H:%M UTC')}"
    )

# ======================
# AUTO KICK SYSTEM
# ======================
async def checker(app):

    while True:

        try:

            now = datetime.utcnow()

            cursor.execute("""
                SELECT user_id, expire_time
                FROM users
                WHERE expire_time IS NOT NULL
            """)

            rows = cursor.fetchall()

            for user_id, expire_time in rows:

                exp = datetime.fromisoformat(expire_time)

                if now >= exp:

                    try:

                        # BAN
                        await app.bot.ban_chat_member(
                            chat_id=GROUP_ID,
                            user_id=user_id
                        )

                        # UNBAN
                        await app.bot.unban_chat_member(
                            chat_id=GROUP_ID,
                            user_id=user_id
                        )

                        cursor.execute(
                            "DELETE FROM users WHERE user_id=?",
                            (user_id,)
                        )

                        conn.commit()

                        logger.info(f"KICKED: {user_id}")

                        # notify admin
                        await app.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"⛔ Member expired & kicked\n\nUser ID: {user_id}"
                        )

                    except Exception as e:
                        logger.error(f"KICK ERROR {user_id}: {e}")

        except Exception as e:
            logger.error(f"CHECKER ERROR: {e}")

        await asyncio.sleep(60)

# ======================
# MEMBER LIST
# ======================
async def member_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ No access")

    cursor.execute("""
        SELECT user_id, username, full_name, join_time, expire_time
        FROM users
        ORDER BY join_time DESC
    """)

    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("Tidak ada member")

    text = "👥 MEMBER LIST\n\n"

    for row in rows:

        user_id, username, full_name, join_time, expire_time = row

        join_dt = datetime.fromisoformat(join_time)

        if expire_time:
            exp_dt = datetime.fromisoformat(expire_time)
            exp_text = exp_dt.strftime("%Y-%m-%d %H:%M")
        else:
            exp_text = "Belum dipilih"

        text += (
            f"🆔 {user_id}\n"
            f"👤 {full_name}\n"
            f"📛 @{username if username else '-'}\n"
            f"📥 Join: {join_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"⛔ Expire: {exp_text}\n"
            f"━━━━━━━━━━━━━━\n"
        )

    await update.message.reply_text(text[:4000])

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 Member Manager Bot Active"
    )

# ======================
# POST INIT
# ======================
async def post_init(app):

    asyncio.create_task(checker(app))

    logger.info("Checker running...")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # detect normal join
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            new_member
        )
    )

    # detect invite link / manual invite
    app.add_handler(
        ChatMemberHandler(
            member_update,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    # buttons
    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # commands
    app.add_handler(
        CommandHandler("member", member_list)
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.post_init = post_init

    logger.info("BOT RUNNING...")

    app.run_polling(
        drop_pending_updates=True
    )

# ======================
# START
# ======================
if __name__ == "__main__":
    main()
