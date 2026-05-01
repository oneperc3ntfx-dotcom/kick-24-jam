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
    InlineKeyboardMarkup
)

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
conn = sqlite3.connect(
    "users.db",
    check_same_thread=False
)

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
# PLAN MAP
# ======================
PLAN = {
    "24h": {
        "days": 1,
        "label": "24 Jam"
    },

    "7d": {
        "days": 7,
        "label": "7 Hari"
    },

    "1m": {
        "days": 30,
        "label": "1 Bulan"
    },

    "1y": {
        "days": 365,
        "label": "1 Tahun"
    }
}

# ======================
# /START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 MEMBER BOT ACTIVE"
    )

# ======================
# /ADD USER
# ======================
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:

        return await update.message.reply_text(
            "Usage:\n/add USER_ID"
        )

    try:
        user_id = int(context.args[0])

    except:
        return await update.message.reply_text(
            "USER ID invalid"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "24 Jam",
                callback_data=f"plan_24h_{user_id}"
            ),

            InlineKeyboardButton(
                "7 Hari",
                callback_data=f"plan_7d_{user_id}"
            )
        ],

        [
            InlineKeyboardButton(
                "1 Bulan",
                callback_data=f"plan_1m_{user_id}"
            ),

            InlineKeyboardButton(
                "1 Tahun",
                callback_data=f"plan_1y_{user_id}"
            )
        ]
    ]

    await update.message.reply_text(
        f"""
👤 SET MEMBER

🆔 USER ID: {user_id}

Pilih durasi membership:
""",
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

    try:

        _, plan_key, user_id = q.data.split("_")

        user_id = int(user_id)

    except:
        return

    if plan_key not in PLAN:
        return

    days = PLAN[plan_key]["days"]
    label = PLAN[plan_key]["label"]

    now = datetime.utcnow()

    expire = now + timedelta(days=days)

    # ======================
    # SAVE DB
    # ======================
    cursor.execute("""
        INSERT OR REPLACE INTO users
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "unknown",
        "unknown",
        now.isoformat(),
        expire.isoformat(),
        label
    ))

    conn.commit()

    # ======================
    # CREATE SINGLE USE LINK
    # ======================
    invite = await context.bot.create_chat_invite_link(
        chat_id=GROUP_ID,

        member_limit=1,

        expire_date=now + timedelta(minutes=2)
    )

    # ======================
    # SEND RESULT
    # ======================
    await q.edit_message_text(
        f"""
✅ MEMBER BERHASIL DIBUAT

🆔 USER ID:
{user_id}

📦 PLAN:
{label}

⏰ EXPIRE:
{expire.strftime('%Y-%m-%d %H:%M UTC')}

🔗 LINK INVITE:
{invite.invite_link}

⚠️ Link hanya bisa dipakai 1x
⚠️ Link expired dalam 2 menit
⚠️ Member auto kick saat expired
"""
    )

# ======================
# AUTO KICK
# ======================
async def checker(app):

    while True:

        try:

            now = datetime.utcnow()

            cursor.execute("""
                SELECT user_id, expire_time
                FROM users
            """)

            rows = cursor.fetchall()

            for row in rows:

                user_id = row[0]
                expire_time = row[1]

                if not expire_time:
                    continue

                exp_dt = datetime.fromisoformat(
                    expire_time
                )

                # ======================
                # EXPIRED
                # ======================
                if now >= exp_dt:

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

                        # DELETE DB
                        cursor.execute("""
                            DELETE FROM users
                            WHERE user_id=?
                        """, (
                            user_id,
                        ))

                        conn.commit()

                        logger.info(
                            f"KICKED {user_id}"
                        )

                        # NOTIFY ADMIN
                        try:

                            await app.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=f"""
⛔ MEMBER EXPIRED

🆔 USER:
{user_id}

Member berhasil di kick otomatis
"""
                            )

                        except:
                            pass

                    except Exception as e:

                        logger.error(
                            f"KICK ERROR {e}"
                        )

        except Exception as e:

            logger.error(
                f"CHECKER ERROR {e}"
            )

        await asyncio.sleep(30)

# ======================
# MEMBER LIST
# ======================
async def member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY expire_time ASC
    """)

    rows = cursor.fetchall()

    if not rows:

        return await update.message.reply_text(
            "Tidak ada member"
        )

    text = "👥 MEMBER LIST\n\n"

    for r in rows:

        user_id = r[0]
        username = r[1]
        full_name = r[2]
        join_time = r[3]
        expire_time = r[4]
        plan = r[5]

        text += (
            f"🆔 ID: {user_id}\n"
            f"📦 Plan: {plan}\n"
            f"📅 Expire: {expire_time}\n"
            f"━━━━━━━━━━━━━━\n"
        )

    await update.message.reply_text(
        text[:4000]
    )

# ======================
# POST INIT
# ======================
async def post_init(app):

    asyncio.create_task(
        checker(app)
    )

    logger.info(
        "AUTO KICK CHECKER RUNNING"
    )

# ======================
# MAIN
# ======================
def main():

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("add", add)
    )

    app.add_handler(
        CommandHandler("member", member)
    )

    app.add_handler(
        CallbackQueryHandler(button)
    )

    app.post_init = post_init

    logger.info("BOT RUNNING...")

    app.run_polling()

# ======================
# START
# ======================
if __name__ == "__main__":
    main()
