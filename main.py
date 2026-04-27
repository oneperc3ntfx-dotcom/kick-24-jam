import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

# ======================
# LOAD ENV
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
# DETECT MEMBER JOIN
# ======================
async def on_member_join(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.new_chat_members:
        return

    for user in update.message.new_chat_members:

        user_id = user.id
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
async def check_kick(app):

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

                    print(f"[KICKED] {user_id}")

                except Exception as e:
                    print(f"[ERROR] {e}")

        await asyncio.sleep(60)  # check tiap 1 menit

# ======================
# START BOT
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif")

# ======================
# POST INIT
# ======================
async def post_init(app):
    import asyncio
    asyncio.create_task(check_kick(app))
    print("Scheduler started")

# ======================
# MAIN
# ======================
def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # detect join (ALL METHOD: invite link + admin add)
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            on_member_join
        )
    )

    app.add_handler(MessageHandler(filters.COMMAND, start))

    app.post_init = post_init

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
