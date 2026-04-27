import os
import sqlite3
import asyncio
from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
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
# DATABASE
# ======================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    join_time TEXT
)
""")
conn.commit()

# ======================
# JOIN DETECTION + WELCOME
# ======================
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    for member in update.message.new_chat_members:
        user_id = member.id
        name = member.first_name

        join_time = datetime.utcnow().isoformat()

        cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?)",
            (user_id, join_time)
        )
        conn.commit()

        await update.message.reply_text(
            f"👋 Welcome {name}!\n\n"
            "Selamat datang di grup 🚀\n"
            "Kamu akan otomatis dievaluasi selama 24 jam."
        )

        print(f"[JOIN] {user_id}")

# ======================
# AUTO KICK 24 JAM
# ======================
async def check_users(app):
    while True:
        now = datetime.utcnow()

        cursor.execute("SELECT user_id, join_time FROM users")
        rows = cursor.fetchall()

        for user_id, join_time in rows:
            join_dt = datetime.fromisoformat(join_time)

            if now - join_dt >= timedelta(hours=24):
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

                    print(f"[KICK] {user_id}")

                except Exception as e:
                    print("Kick error:", e)

        await asyncio.sleep(60)

# ======================
# /MEMBER COMMAND
# ======================
async def member_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ No access")

    cursor.execute("SELECT user_id, join_time FROM users")
    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("Tidak ada member aktif")

    text = "👥 LIST MEMBER AKTIF\n\n"

    for user_id, join_time in rows:
        join_dt = datetime.fromisoformat(join_time)
        kick_time = join_dt + timedelta(hours=24)

        text += (
            f"🆔 {user_id}\n"
            f"⏰ Join: {join_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"⛔ Kick: {kick_time.strftime('%Y-%m-%d %H:%M')}\n"
            "━━━━━━━━━━━━━━\n"
        )

    await update.message.reply_text(text)

# ======================
# PRIVATE COMMANDS
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("🤖 Bot aktif")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("🏓 Pong")

# ======================
# BACKGROUND TASK
# ======================
async def post_init(app):
    app.create_task(check_users(app))
    print("Scheduler running...")

# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # detect join
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member)
    )

    # commands
    app.add_handler(CommandHandler("member", member_list))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    app.post_init = post_init

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
