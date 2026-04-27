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

# ======================
# DB
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
# SAVE MEMBER JOIN
# ======================
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    for member in update.message.new_chat_members:
        user_id = member.id
        join_time = datetime.utcnow().isoformat()

        cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?)",
            (user_id, join_time)
        )
        conn.commit()

        print(f"[JOIN] {user_id} at {join_time}")

# ======================
# AUTO KICK AFTER 24H
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
                    await app.bot.ban_chat_member(chat_id=GROUP_ID, user_id=user_id)
                    await app.bot.unban_chat_member(chat_id=GROUP_ID, user_id=user_id)

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()

                    print(f"[KICK] {user_id}")

                except Exception as e:
                    print("Kick error:", e)

        await asyncio.sleep(60)  # cek tiap 1 menit

# ======================
# PRIVATE CHAT
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "🤖 Bot aktif\n"
            "• Auto kick member 24 jam\n"
        )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("🏓 Bot aktif")

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

    # handler join member (SEMUA CARA JOIN)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    app.post_init = post_init

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
