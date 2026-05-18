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
# START MENU
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("🔥 Join 1 Hari (25K)", callback_data="buy_24h")],
        [InlineKeyboardButton("🚀 Join 7 Hari (49K)", callback_data="buy_7d")],
        [InlineKeyboardButton("👑 Join 1 Bulan (99K)", callback_data="buy_1m")],
        [InlineKeyboardButton("💎 Join 1 Tahun (999K)", callback_data="buy_1y")]
    ]

    await update.message.reply_text(
        "🤖 ONE PERCENT FX PREMIUM\n\nPilih paket:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# BUY BUTTON (FIXED)
# ======================
async def buy_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query

    try:
        await q.answer()

        plan_key = q.data.replace("buy_", "")

        if plan_key not in PLAN:
            await q.message.reply_text("❌ Paket tidak valid")
            return

        context.user_data["selected_plan"] = plan_key
        plan = PLAN[plan_key]

        await q.message.reply_text(
            f"""
📦 PAKET DIPILIH

📌 {plan['label']}
💰 {plan['price']}

Silahkan transfer lalu kirim bukti.
""",
        )

    except Exception as e:
        logger.error(f"BUY ERROR: {e}")
        await q.answer("Error, coba lagi", show_alert=True)

# ======================
# PHOTO HANDLER
# ======================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    plan_key = context.user_data.get("selected_plan")

    if not plan_key:
        await update.message.reply_text("⚠️ Pilih paket dulu /start")
        return

    photo = update.message.photo[-1].file_id

    pending_proofs[user.id] = {
        "photo": photo,
        "plan": plan_key
    }

    keyboard = [
        [InlineKeyboardButton("✅ Konfirmasi", callback_data=f"confirm_{user.id}")]
    ]

    await update.message.reply_text(
        "📥 Bukti diterima, klik konfirmasi.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# CONFIRM (ADMIN FLOW SIMPLIFIED)
# ======================
async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    user_id = int(q.data.split("_")[1])

    if user_id not in pending_proofs:
        return

    data = pending_proofs[user_id]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=data["photo"],
        caption=f"BUKTI USER {user_id}"
    )

    await q.edit_message_text("✅ Dikirim ke admin")

# ======================
# ADMIN ACTION
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

        await q.edit_message_caption("APPROVED")

    elif action == "reject":

        user_id = int(data[1])

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ditolak"
        )

        await q.edit_message_caption("REJECTED")

# ======================
# TEXT HANDLER
# ======================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("Gunakan /start")

# ======================
# AUTO CHECKER
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

                except Exception as e:
                    logger.error(f"KICK ERROR: {e}")

        await asyncio.sleep(30)

# ======================
# POST INIT
# ======================
async def post_init(app):
    asyncio.create_task(checker(app))
    logger.info("CHECKER RUNNING")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(buy_button, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_transfer, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.post_init = post_init

    print("BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
