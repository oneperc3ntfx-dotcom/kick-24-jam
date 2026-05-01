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
    ContextTypes,
    MessageHandler,
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

logger = logging.getLogger("PREMIUM-BOT")

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
    plan TEXT,
    expire_time TEXT
)
""")

conn.commit()

# ======================
# PLAN
# ======================
PLAN = {
    "1d": {
        "days": 1,
        "label": "1 Hari",
        "price": "25.000"
    },

    "7d": {
        "days": 7,
        "label": "7 Hari",
        "price": "49.000"
    },

    "1m": {
        "days": 30,
        "label": "1 Bulan",
        "price": "99.000"
    },

    "1y": {
        "days": 365,
        "label": "1 Tahun",
        "price": "999.000"
    }
}

# ======================
# TEMP PAYMENT STORAGE
# ======================
pending_users = {}

# ======================
# /START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "🔥 Join 1 Hari (25K)",
                callback_data="buy_1d"
            )
        ],

        [
            InlineKeyboardButton(
                "⚡ Join 7 Hari (49K)",
                callback_data="buy_7d"
            )
        ],

        [
            InlineKeyboardButton(
                "🚀 Join 1 Bulan (99K)",
                callback_data="buy_1m"
            )
        ],

        [
            InlineKeyboardButton(
                "👑 Join 1 Tahun (999K)",
                callback_data="buy_1y"
            )
        ]
    ]

    await update.message.reply_text(
        f"""
🤖 *ONE PERCENT FX PREMIUM*

Selamat datang di Premium AI Signal 🔥

📊 Signal dianalisa menggunakan:

✅ Smart Money Concept
✅ Liquidity & Order Block
✅ Institutional Flow
✅ News Impact & Fundamental Bias

⚡ Signal keluar setiap 1 jam sekali
⚡ High probability setup only
⚡ Cocok untuk scalping & intraday

━━━━━━━━━━━━━━

💳 *PEMBAYARAN MANUAL*

Transfer ke rekening berikut:

🏦 BANK SMBC (JENIUS)
💳 90240573080
👤 AN: YURIANDI ARMA

━━━━━━━━━━━━━━

📌 Setelah transfer:
Kirim bukti transfer ke bot ini

Admin akan mengecek pembayaran kamu lalu mengirimkan link premium otomatis ✅

━━━━━━━━━━━━━━

📞 Jika ada kendala:
@ADMOnePercentsFX

━━━━━━━━━━━━━━

🔄 Jika ingin berlangganan lagi:
Gunakan command:
/renew
""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# /RENEW
# ======================
async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await start(update, context)

# ======================
# BUY BUTTON
# ======================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    data = q.data

    # ======================
    # USER BUY
    # ======================
    if data.startswith("buy_"):

        plan_key = data.split("_")[1]

        if plan_key not in PLAN:
            return

        plan = PLAN[plan_key]

        user = q.from_user

        pending_users[user.id] = {
            "plan_key": plan_key
        }

        await q.message.reply_text(
            f"""
🧾 *DETAIL PEMBAYARAN*

📦 Paket:
{plan['label']}

💰 Harga:
Rp {plan['price']}

━━━━━━━━━━━━━━

🏦 BANK SMBC (JENIUS)
💳 90240573080
👤 AN: YURIANDI ARMA

━━━━━━━━━━━━━━

📌 Silahkan transfer sesuai nominal

📤 Setelah transfer:
Kirim foto bukti transfer ke bot ini

⚠️ Admin akan mengecek pembayaran kamu terlebih dahulu
""",
            parse_mode="Markdown"
        )

    # ======================
    # APPROVE
    # ======================
    elif data.startswith("approve_"):

        if q.from_user.id != ADMIN_ID:
            return

        user_id = int(data.split("_")[1])

        if user_id not in pending_users:
            return await q.answer("Data expired")

        plan_key = pending_users[user_id]["plan_key"]

        plan = PLAN[plan_key]

        now = datetime.utcnow()

        expire = now + timedelta(
            days=plan["days"]
        )

        # ======================
        # SAVE DB
        # ======================
        cursor.execute("""
            INSERT OR REPLACE INTO users
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            "unknown",
            "unknown",
            plan["label"],
            expire.isoformat()
        ))

        conn.commit()

        # ======================
        # CREATE INVITE
        # ======================
        invite = await context.bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            member_limit=1,
            expire_date=now + timedelta(minutes=5)
        )

        # ======================
        # SEND TO USER
        # ======================
        await context.bot.send_message(
            chat_id=user_id,
            text=f"""
✅ *PEMBAYARAN BERHASIL*

📦 Paket:
{plan['label']}

⏰ Expired:
{expire.strftime('%Y-%m-%d %H:%M UTC')}

━━━━━━━━━━━━━━

🔗 LINK PREMIUM:
{invite.invite_link}

⚠️ Link hanya bisa dipakai 1x
⚠️ Link expired dalam 5 menit

━━━━━━━━━━━━━━

🔥 Selamat bergabung di AI Signal Premium

Semoga profit bersama One Percent FX 🚀📈

━━━━━━━━━━━━━━

🔄 Jika ingin perpanjang membership:
Ketik:
/renew
""",
            parse_mode="Markdown"
        )

        await q.edit_message_caption(
            caption="✅ PAYMENT APPROVED"
        )

        del pending_users[user_id]

    # ======================
    # REJECT
    # ======================
    elif data.startswith("reject_"):

        if q.from_user.id != ADMIN_ID:
            return

        user_id = int(data.split("_")[1])

        try:

            await context.bot.send_message(
                chat_id=user_id,
                text="""
❌ *TRANSAKSI DITOLAK*

Nominal transfer tidak sesuai
atau bukti transfer tidak valid

Silahkan transfer ulang sesuai paket yang dipilih
""",
                parse_mode="Markdown"
            )

        except:
            pass

        await q.edit_message_caption(
            caption="❌ PAYMENT REJECTED"
        )

# ======================
# HANDLE PHOTO
# ======================
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if user.id not in pending_users:

        return await update.message.reply_text(
            "Silahkan pilih paket terlebih dahulu dengan /start"
        )

    plan_key = pending_users[user.id]["plan_key"]

    plan = PLAN[plan_key]

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ APPROVE",
                callback_data=f"approve_{user.id}"
            ),

            InlineKeyboardButton(
                "❌ REJECT",
                callback_data=f"reject_{user.id}"
            )
        ]
    ]

    caption = f"""
📥 BUKTI TRANSFER MASUK

👤 USER:
{user.full_name}

🆔 ID:
{user.id}

📦 PLAN:
{plan['label']}

💰 NOMINAL:
Rp {plan['price']}
"""

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        """
✅ Bukti transfer berhasil dikirim

Mohon tunggu admin melakukan pengecekan pembayaran
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

                        try:

                            await app.bot.send_message(
                                chat_id=user_id,
                                text="""
⛔ Membership kamu telah expired

Terima kasih sudah bergabung bersama One Percent FX 🔥

Untuk berlangganan lagi:
Ketik /renew
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

        text += (
            f"🆔 {r[0]}\n"
            f"📦 {r[3]}\n"
            f"⏰ {r[4]}\n"
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
        "AUTO KICK RUNNING"
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
        CommandHandler("renew", renew)
    )

    app.add_handler(
        CommandHandler("member", member)
    )

    app.add_handler(
        CallbackQueryHandler(button)
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo
        )
    )

    app.post_init = post_init

    logger.info("BOT RUNNING...")

    app.run_polling()

# ======================
# START
# ======================
if __name__ == "__main__":
    main()
