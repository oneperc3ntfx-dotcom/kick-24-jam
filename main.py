import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# ======================
# LOAD ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

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
# USER JOIN
# ======================
def new_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        user_id = member.id
        join_time = datetime.now().isoformat()

        cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?)",
            (user_id, join_time)
        )
        conn.commit()

        print(f"{user_id} joined")

# ======================
# CHECK 24 JAM
# ======================
def check_users():
    now = datetime.now()

    cursor.execute("SELECT user_id, join_time FROM users")
    rows = cursor.fetchall()

    for user_id, join_time in rows:
        join_time = datetime.fromisoformat(join_time)

        if now - join_time > timedelta(hours=24):
            try:
                updater.bot.kick_chat_member(
                    chat_id=GROUP_ID,
                    user_id=user_id
                )

                updater.bot.unban_chat_member(
                    chat_id=GROUP_ID,
                    user_id=user_id
                )

                cursor.execute(
                    "DELETE FROM users WHERE user_id=?",
                    (user_id,)
                )
                conn.commit()

                print(f"{user_id} kicked after 24 hours")

            except Exception as e:
                print(f"Error: {e}")

# ======================
# PRIVATE CHAT
# ======================
def start(update: Update, context: CallbackContext):
    if update.message.chat.type == "private":
        update.message.reply_text(
            "🤖 Bot aktif!\n\n"
            "Fitur:\n"
            "✅ Auto kick member setelah 24 jam\n\n"
            "Ketik 'ping' untuk cek status bot."
        )

def reply_private(update: Update, context: CallbackContext):
    if update.message.chat.type == "private":
        text = update.message.text.lower()

        if "ping" in text:
            update.message.reply_text("🏓 Pong! Bot aktif dan berjalan normal.")
        else:
            update.message.reply_text("Bot aktif ✅")

# ======================
# TELEGRAM SETUP
# ======================
updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

# detect member join
dp.add_handler(
    MessageHandler(
        Filters.status_update.new_chat_members,
        new_member
    )
)

# command /start
dp.add_handler(CommandHandler("start", start))

# reply private chat
dp.add_handler(
    MessageHandler(
        Filters.text & ~Filters.command,
        reply_private
    )
)

# ======================
# SCHEDULER
# ======================
scheduler = BackgroundScheduler()
scheduler.add_job(check_users, "interval", minutes=5)
scheduler.start()

print("Bot running...")

# ======================
# RUN BOT
# ======================
updater.start_polling()
updater.idle()
