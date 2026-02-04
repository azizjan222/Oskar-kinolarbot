import telebot
import psycopg2
import os
import re
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ================== SOZLAMALAR ==================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_ID = 5660204735
CHANNEL_ID = -1002392958296
INVITE_LINK = "https://t.me/+M0Dauf0h0QoxMzgy"

bot = telebot.TeleBot(BOT_TOKEN)

# ================== DATABASE ==================

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY,
    file_id TEXT,
    title TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    last_active TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    requests INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    sent INTEGER,
    failed INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
)
""")

cur.execute(
    "INSERT INTO stats (id, requests) VALUES (1,0) ON CONFLICT DO NOTHING"
)

conn.commit()

# ================== MAJBURIY OBUNA ==================

subscribed_users = set()

def force_join_message(chat_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔔 Kanalga obuna bo‘lish", url=INVITE_LINK),
        InlineKeyboardButton("✅ Obuna bo‘ldim", callback_data="joined")
    )
    bot.send_message(
        chat_id,
        "❌ Kino olishdan oldin kanalga obuna bo‘ling 👇",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "joined")
def joined_callback(call):
    subscribed_users.add(call.from_user.id)
    bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
    bot.send_message(call.message.chat.id, "🎬 Endi kino ID yozing")

# ================== YORDAMCHI ==================

def save_user(user_id):
    cur.execute(
        """
        INSERT INTO users (user_id, last_active)
        VALUES (%s, NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET last_active = NOW()
        """,
        (user_id,)
    )
    conn.commit()

def add_request():
    cur.execute("UPDATE stats SET requests = requests + 1 WHERE id=1")
    conn.commit()

# ================== START ==================

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🎬 *Oskar Kinolar* botiga xush kelibsiz!\n\n"
        "Kino olish uchun *ID raqamini* yuboring.\n"
        "Masalan: `125`",
        parse_mode="Markdown"
    )

# ================== KANALDAN KINO SAQLASH ==================

@bot.channel_post_handler(content_types=['video'])
def save_movie(message):
    if message.chat.id != CHANNEL_ID:
        return

    if not message.caption:
        return

    match = re.search(r'ID:\s*(\d+)', message.caption)
    if not match:
        return

    movie_id = int(match.group(1))
    file_id = message.video.file_id
    title = message.caption.split('\n')[0]

    cur.execute(
        """
        INSERT INTO movies (id, file_id, title)
        VALUES (%s,%s,%s)
        ON CONFLICT (id) DO NOTHING
        """,
        (movie_id, file_id, title)
    )
    conn.commit()

# ================== KINO BERISH ==================

@bot.message_handler(func=lambda m: m.text.isdigit())
def send_movie(message):

    if message.from_user.id != ADMIN_ID:
        if message.from_user.id not in subscribed_users:
            force_join_message(message.chat.id)
            return

    movie_id = int(message.text)

    cur.execute(
        "SELECT file_id, title FROM movies WHERE id=%s",
        (movie_id,)
    )
    data = cur.fetchone()

    if data:
        save_user(message.from_user.id)
        add_request()

        bot.send_video(
            message.chat.id,
            data[0],
            caption=f"🎬 {data[1]}"
        )
    else:
        bot.reply_to(message, "❌ Bunday ID dagi kino topilmadi")

# ================== ADMIN PANEL ==================

broadcast_mode = False

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton("📊 Statistika"),
        KeyboardButton("🗑 Kino o‘chirish"),
        KeyboardButton("📢 Broadcast")
    )

    bot.send_message(message.chat.id, "👮 Admin panel", reply_markup=kb)

# ================== STATISTIKA ==================

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM users
        WHERE last_active >= NOW() - INTERVAL '7 days'
    """)
    active_users = cur.fetchone()[0]

    cur.execute("SELECT requests FROM stats WHERE id=1")
    requests = cur.fetchone()[0]

    bot.send_message(
        message.chat.id,
        f"📊 Statistika\n\n"
        f"👥 Obuna bo‘lganlar: {total_users}\n"
        f"🔥 Aktiv (7 kun): {active_users}\n"
        f"🎬 Jami so‘rovlar: {requests}"
    )

# ================== BROADCAST ==================

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def start_broadcast(message):
    global broadcast_mode
    if message.from_user.id != ADMIN_ID:
        return
    broadcast_mode = True
    bot.send_message(
        message.chat.id,
        "📢 Broadcast boshlandi.\n\n"
        "Matn / rasm / video yuboring.\n"
        "Bekor qilish: /cancel"
    )

@bot.message_handler(commands=['cancel'])
def cancel_broadcast(message):
    global broadcast_mode
    if message.from_user.id == ADMIN_ID:
        broadcast_mode = False
        bot.send_message(message.chat.id, "❌ Broadcast bekor qilindi")

@bot.message_handler(
    func=lambda m: broadcast_mode and m.from_user.id == ADMIN_ID,
    content_types=['text', 'photo', 'video']
)
def send_broadcast(message):
    global broadcast_mode

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    sent = 0
    failed = 0

    for (uid,) in users:
        try:
            if message.content_type == 'text':
                bot.send_message(uid, message.text)
            elif message.content_type == 'photo':
                bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'video':
                bot.send_video(uid, message.video.file_id, caption=message.caption)
            sent += 1
        except:
            failed += 1

    cur.execute(
        "INSERT INTO broadcasts (sent, failed) VALUES (%s,%s)",
        (sent, failed)
    )
    conn.commit()

    broadcast_mode = False

    bot.send_message(
        message.chat.id,
        f"📢 Broadcast tugadi\n\n"
        f"👀 Ko‘rildi: {sent}\n"
        f"❌ Yetmadi: {failed}\n"
        f"📊 Jami: {sent + failed}"
    )

# ================== START ==================

bot.infinity_polling()
