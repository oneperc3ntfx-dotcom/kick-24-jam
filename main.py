import os
import asyncio
import sqlite3
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# ======================
# LOAD ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan")

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
# SAVE MEMBER JOIN
# ======================
async def on_join(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.new_chat_members:
        return

    for user in update.message.new_chat_members:

        cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?)",
            (user.id, datetime.utcnow().isoformat())
        )
        conn.commit()

        print(f"[JOIN] {user.id}")

# ======================
# AUTO KICK SYSTEM
# ======================
async def kick_scheduler(app):

    while True:

        now = datetime.utcnow()

        cursor.execute("SELECT user_id, join_time FROM users")
        users = cursor.fetchall()

        for user_id, join_time in users:

            join_time = datetime.fromisoformat(join_time)

            if now - join_time >= timedelta(hours=24):

                try:
                    # BAN lalu UNBAN (biar bisa join lagi nanti)
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

                    print(f"[KICKED 24H] {user_id}")

                except Exception as e:
                    print(f"[ERROR] {e}")

        await asyncio.sleep(60)

# ======================
# COMMAND START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.chat.type == "private":
        await update.message.reply_text(
            "🤖 Bot aktif\n\n"
            "Fitur:\n"
            "✔ Auto track member join\n"
            "✔ Auto kick setelah 24 jam"
        )

# ======================
# POST INIT
# ======================
async def post_init(app):
    asyncio.create_task(kick_scheduler(app))
    print("Scheduler aktif")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # detect join (invite link + admin add)
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            on_join
        )
    )

    app.add_handler(CommandHandler("start", start))

    app.post_init = post_init

    print("BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
