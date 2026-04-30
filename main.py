import os
import sqlite3
import asyncio
from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# ======================
# DB
# ======================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    join_time TEXT,
    expire_time TEXT,
    name TEXT
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
# NEW MEMBER DETECT
# ======================
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    for member in update.message.new_chat_members:
        user_id = member.id
        name = member.first_name
        join_time = datetime.utcnow()

        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, join_time, expire_time, name) VALUES (?, ?, ?, ?)",
            (user_id, join_time.isoformat(), None, name)
        )
        conn.commit()

        # BUTTONS FOR ADMIN
        keyboard = [
            [
                InlineKeyboardButton("7 Hari", callback_data=f"set_7d_{user_id}"),
                InlineKeyboardButton("1 Bulan", callback_data=f"set_1m_{user_id}"),
                InlineKeyboardButton("1 Tahun", callback_data=f"set_1y_{user_id}")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # DM ADMIN
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👤 Member baru join:\n\n🆔 {user_id}\nNama: {name}\n\nPilih durasi:",
            reply_markup=reply_markup
        )

        print(f"[JOIN] {user_id}")

# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    data = query.data  # set_7d_12345

    try:
        action, plan, user_id = data.split("_")
        user_id = int(user_id)
    except:
        return

    days = PLAN_MAP.get(plan, 7)

    expire_time = datetime.utcnow() + timedelta(days=days)

    cursor.execute("""
        UPDATE users
        SET expire_time=?
        WHERE user_id=?
    """, (expire_time.isoformat(), user_id))
    conn.commit()

    await query.edit_message_text(
        f"✅ User {user_id} set {days} hari\n⏰ Expire: {expire_time}"
    )

# ======================
# AUTO KICK SYSTEM
# ======================
async def checker(app):

    while True:
        now = datetime.utcnow()

        cursor.execute("SELECT user_id, expire_time FROM users")
        rows = cursor.fetchall()

        for user_id, expire_time in rows:

            if not expire_time:
                continue

            exp = datetime.fromisoformat(expire_time)

            if now >= exp:
                try:
                    await app.bot.ban_chat_member(chat_id=GROUP_ID, user_id=user_id)
                    await app.bot.unban_chat_member(chat_id=GROUP_ID, user_id=user_id)

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()

                    print(f"[KICK] {user_id}")

                except Exception as e:
                    print("Kick error:", e)

        await asyncio.sleep(60)

# ======================
# MEMBER LIST
# ======================
async def member_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("No access")

    cursor.execute("SELECT user_id, join_time, expire_time, name FROM users")
    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("No member")

    text = "👥 MEMBER LIST\n\n"

    for user_id, join_time, expire_time, name in rows:

        join_dt = datetime.fromisoformat(join_time)
        exp_dt = datetime.fromisoformat(expire_time) if expire_time else None

        text += (
            f"🆔 {user_id}\n"
            f"👤 {name}\n"
            f"📥 Join: {join_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"⛔ Expire: {exp_dt.strftime('%Y-%m-%d %H:%M') if exp_dt else 'Not set'}\n"
            "━━━━━━━━━━━━━━\n"
        )

    await update.message.reply_text(text)

# ======================
# INIT TASK
# ======================
async def post_init(app):
    asyncio.create_task(checker(app))
    print("Scheduler running...")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(CommandHandler("member", member_list))

    app.post_init = post_init

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
