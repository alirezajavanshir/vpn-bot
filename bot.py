import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = "8807666855:AAHMD_aB4qz53ILr78qKn1fPCl9dqGzWT8o"
ADMINS = [857857453]
CONFIG_TEXT = "vmess://YOUR_CONFIG"

# DB
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    user_id INTEGER,
    plan TEXT,
    receipt TEXT,
    status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cur.execute("INSERT OR IGNORE INTO settings VALUES ('card', '6037-XXXX-XXXX-XXXX')")
conn.commit()


# ---------------- SETTINGS ----------------

def get_card():
    cur.execute("SELECT value FROM settings WHERE key='card'")
    r = cur.fetchone()
    return r[0] if r else "NOT SET"


# ---------------- ADMIN PANEL ----------------

def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن پلن", callback_data="add")],
        [InlineKeyboardButton("📦 لیست پلن‌ها", callback_data="list")],
        [InlineKeyboardButton("❌ حذف پلن", callback_data="del")]
    ])


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in ADMINS:
        await update.message.reply_text("👑 پنل ادمین:", reply_markup=admin_panel())
        return

    await show_plans(update, context)


# ---------------- SHOW PLANS ----------------

async def show_plans(update, context):
    cur.execute("SELECT * FROM plans")
    plans = cur.fetchall()

    if not plans:
        await update.message.reply_text("❌ پلنی موجود نیست")
        return

    keyboard = [
        [InlineKeyboardButton(f"{p[1]} - {p[2]}", callback_data=f"buy_{p[0]}")]
        for p in plans
    ]

    await update.message.reply_text(
        "📦 پلن‌ها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- BUY ----------------

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    plan_id = q.data.split("_")[1]

    cur.execute("SELECT name, price FROM plans WHERE id=?", (plan_id,))
    plan = cur.fetchone()

    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?)", (q.from_user.id, plan[0], None, "waiting"))
    conn.commit()

    await q.message.reply_text(
        f"""💳 خرید پلن:

📦 {plan[0]}
💰 {plan[1]}

💳 شماره کارت:
{get_card()}

📸 بعد از پرداخت فیش را ارسال کنید.
"""
    )


# ---------------- RECEIPT ----------------

async def receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_id = update.message.photo[-1].file_id

    cur.execute("UPDATE orders SET receipt=?, status='paid' WHERE user_id=?", (file_id, user.id))
    conn.commit()

    for admin in ADMINS:
        await context.bot.send_photo(
            chat_id=admin,
            photo=file_id,
            caption=f"💰 پرداخت جدید\nUser: {user.id}\n/approve {user.id}"
        )


# ---------------- APPROVE ----------------

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        return

    user_id = context.args[0]

    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ پرداخت تایید شد\n\n📡 کانفیگ:\n{CONFIG_TEXT}"
    )

    await update.message.reply_text("ارسال شد")


# ---------------- ADMIN CALLBACK ----------------

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "list":
        cur.execute("SELECT * FROM plans")
        plans = cur.fetchall()

        text = "📦 پلن‌ها:\n\n"
        for p in plans:
            text += f"{p[0]} - {p[1]} | {p[2]}\n"

        await q.message.reply_text(text)

    elif q.data == "add":
        await q.message.reply_text("➕ /add name price")

    elif q.data == "del":
        await q.message.reply_text("❌ /delete id")


# ---------------- ADD PLAN ----------------

async def add_plan(update, context):
    if update.message.from_user.id not in ADMINS:
        return

    name = context.args[0]
    price = context.args[1]

    cur.execute("INSERT INTO plans (name, price) VALUES (?, ?)", (name, price))
    conn.commit()

    await update.message.reply_text("✅ پلن اضافه شد")


# ---------------- DELETE PLAN ----------------

async def delete_plan(update, context):
    if update.message.from_user.id not in ADMINS:
        return

    plan_id = context.args[0]

    cur.execute("DELETE FROM plans WHERE id=?", (plan_id,))
    conn.commit()

    await update.message.reply_text("❌ حذف شد")


# ---------------- SET CARD ----------------

async def set_card(update, context):
    if update.message.from_user.id not in ADMINS:
        return

    new_card = " ".join(context.args)

    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES ('card', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (new_card,))

    conn.commit()

    await update.message.reply_text("✅ شماره کارت بروزرسانی شد")


# ---------------- APP ----------------

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(CallbackQueryHandler(buy_plan, pattern="buy_"))
app.add_handler(CallbackQueryHandler(admin_actions))

app.add_handler(CommandHandler("add", add_plan))
app.add_handler(CommandHandler("delete", delete_plan))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("setcard", set_card))

app.add_handler(MessageHandler(filters.PHOTO, receipt))

app.run_polling()