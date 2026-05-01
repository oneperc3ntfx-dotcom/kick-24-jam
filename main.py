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
        "label": "1 Hari",
        "price": "25K"
    },

    "7d": {
        "days": 7,
        "label": "7 Hari",
        "price": "49K"
    },

    "1m": {
        "days": 30,
        "label": "1 Bulan",
        "price": "99K"
    },

    "1y": {
        "days": 365,
        "label": "1 Tahun",
        "price": "999K"
    }
}

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [

        [
            InlineKeyboardButton(
                "🔥 Join 1 Hari (25K)",
                callback_data="buy_24h"
            )
        ],

        [
            InlineKeyboardButton(
                "🚀 Join 7 Hari (49K)",
                callback_data="buy_7d"
            )
        ],

        [
            InlineKeyboardButton(
                "👑 Join 1 Bulan (99K)",
                callback_data="buy_1m"
            )
        ],

        [
            InlineKeyboardButton(
                "💎 Join 1 Tahun (999K)",
                callback_data="buy_1y"
            )
        ]
    ]

    await update.message.reply_text(
        """
🤖 *ONE PERCENT FX PREMIUM*

Selamat datang di Premium AI Signal Group 📈

Signal dianalisa menggunakan:

✅ Smart Money Concept
✅ Liquidity & Market Structure
✅ Order Block Institution
✅ News Impact Analysis
✅ Market Bias AI System

📊 Signal keluar setiap 1 jam sekali
📰 Disertai berita & rekomendasi bias market

━━━━━━━━━━━━━━

💰 *PEMBAYARAN VIA BANK*

🏦 BANK SMBC (JENIUS)
💳 90240573080
👤 A/N YURIANDI ARMA

━━━━━━━━━━━━━━

📌 Setelah transfer:
Silahkan kirim bukti transfer berupa foto/screenshoot ke bot ini

📞 Bantuan:
@ADMOnePercentsFX

⚡ Semoga profit bergabung bersama AI Signal kami 🚀
""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# RENEW
# ======================
async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await start(update, context)

# ======================
# BUY BUTTON
# ======================
async def buy_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    plan_key = q.data.replace("buy_", "")

    if plan_key not in PLAN:
        return

    plan = PLAN[plan_key]

    context.user_data["selected_plan"] = plan_key

    await q.message.reply_text(
        f"""
📦 *PAKET DIPILIH*

📌 Paket:
{plan['label']}

💰 Harga:
{plan['price']}

━━━━━━━━━━━━━━

💳 Transfer ke:

🏦 BANK SMBC (JENIUS)
💳 90240573080
👤 A/N YURIANDI ARMA

━━━━━━━━━━━━━━

📌 Setelah transfer:
Kirim bukti transfer berupa foto/screenshoot ke bot ini

📞 Bantuan:
@ADMOnePercentsFX
""",
        parse_mode="Markdown"
    )

# ======================
# PHOTO HANDLER
# ======================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    plan_key = context.user_data.get("selected_plan")

    if not plan_key:
        return await update.message.reply_text(
            """
⚠️ Kamu belum memilih paket

Gunakan:
/start

Untuk memilih paket membership
"""
        )

    plan = PLAN[plan_key]

    photo = update.message.photo[-1].file_id

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ APPROVE",
                callback_data=f"approve_{plan_key}_{user.id}"
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

💰 PRICE:
{plan['price']}
"""

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        """
✅ Bukti transfer berhasil dikirim

Mohon tunggu admin melakukan verifikasi pembayaran ⏳
"""
    )

# ======================
# ADMIN BUTTON
# ======================
async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    data = q.data.split("_")

    action = data[0]

    # ======================
    # APPROVE
    # ======================
    if action == "approve":

        plan_key = data[1]
        user_id = int(data[2])

        plan = PLAN[plan_key]

        now = datetime.utcnow()

        expire = now + timedelta(days=plan["days"])

        # save DB
        cursor.execute("""
            INSERT OR REPLACE INTO users
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            "unknown",
            "unknown",
            now.isoformat(),
            expire.isoformat(),
            plan["label"]
        ))

        conn.commit()

        # create invite
        invite = await context.bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            member_limit=1,
            expire_date=now + timedelta(minutes=5)
        )

        # send to member
        await context.bot.send_message(
            chat_id=user_id,
            text=f"""
🎉 *PEMBAYARAN BERHASIL DIKONFIRMASI*

📦 Paket:
{plan['label']}

⏰ Expired:
{expire.strftime('%Y-%m-%d %H:%M UTC')}

━━━━━━━━━━━━━━

🔗 LINK JOIN GROUP:

{invite.invite_link}

━━━━━━━━━━━━━━

⚠️ Link hanya bisa dipakai 1x
⚠️ Link expired dalam 5 menit
⚠️ Membership auto kick saat expired

🚀 Semoga profit bersama AI Signal kami
""",
            parse_mode="Markdown"
        )

        await q.edit_message_caption(
            caption=q.message.caption + "\n\n✅ APPROVED"
        )

    # ======================
    # REJECT
    # ======================
    elif action == "reject":

        user_id = int(data[1])

        await context.bot.send_message(
            chat_id=user_id,
            text="""
❌ TRANSAKSI DITOLAK

Nominal transfer tidak sesuai
atau bukti transfer tidak valid

Silahkan transfer ulang sesuai paket yang dipilih

📞 Bantuan:
@ADMOnePercentsFX
"""
        )

        await q.edit_message_caption(
            caption=q.message.caption + "\n\n❌ REJECTED"
        )

# ======================
# AUTO REPLY RANDOM CHAT
# ======================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """
🤖 ONE PERCENT FX PREMIUM

Gunakan menu berikut:

/start → lihat paket premium
/renew → perpanjang membership

📌 Jika sudah transfer:
kirim bukti transfer berupa foto/screenshoot ke bot ini

📞 Bantuan:
@ADMOnePercentsFX
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

                # expired
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

Silahkan renew untuk mendapatkan akses kembali

Gunakan:
/renew
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
        CommandHandler("renew", renew)
    )

    app.add_handler(
        CommandHandler("member", member)
    )

    app.add_handler(
        CallbackQueryHandler(
            buy_button,
            pattern="^buy_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_button,
            pattern="^(approve|reject)_"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
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
