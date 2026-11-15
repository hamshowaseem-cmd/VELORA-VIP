import os
import sys
import re
import html
import sqlite3
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import telebot
from telebot import types

# إعدادات آمنة من متغيرات بيئة الاستضافة
TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ADMIN_ID_RAW = (os.getenv("ADMIN_TELEGRAM_ID") or "6012187178").strip()
DB_PATH = os.getenv("DATABASE_PATH", "velora.db")

if not TOKEN or ":" not in TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN غير مضبوط. أضف رمز BotFather الصحيح في إعدادات الاستضافة.")
if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError("ADMIN_TELEGRAM_ID يجب أن يكون رقماً صحيحاً.")
ADMIN_ID = int(ADMIN_ID_RAW)

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
user_steps = {}

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                kind TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount TEXT NOT NULL,
                note TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ طلب إيداع", callback_data="new:deposit"),
        types.InlineKeyboardButton("➖ طلب سحب", callback_data="new:withdraw")
    )
    kb.add(
        types.InlineKeyboardButton("📋 طلباتي", callback_data="my_requests"),
        types.InlineKeyboardButton("☎️ التواصل مع الإدارة", callback_data="contact")
    )
    return kb

def back_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"))
    return kb

def currency_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💵 الدولار الأمريكي USD", callback_data="currency:USD"),
        types.InlineKeyboardButton("🇸🇾 الليرة السورية SYP", callback_data="currency:SYP"),
        types.InlineKeyboardButton("إلغاء", callback_data="cancel")
    )
    return kb

def safe(value):
    return html.escape(str(value or ""))

@bot.message_handler(commands=["start", "menu"])
def start(message):
    user_steps.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "أهلاً بك في <b>VELORA-VIP</b> 🌟\n"
        "خدمات طلبات الكاشيرة باللغة العربية.\n\n"
        "اختر الخدمة المطلوبة. جميع الطلبات تبقى قيد المراجعة، ولا تعتبر الموافقة داخل البوت إثباتاً لتحويل مالي.",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(message.chat.id, "أرسل /start لعرض القائمة الرئيسية. لا ترسل كلمات المرور أو رموز التحقق أو بيانات البطاقات.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("new:"))
def new_request(call):
    kind = call.data.split(":", 1)[1]
    user_steps[call.from_user.id] = {"kind": kind}
    bot.answer_callback_query(call.id)
    label = "الإيداع" if kind == "deposit" else "السحب"
    bot.send_message(call.message.chat.id, f"اختر عملة طلب {label}:", reply_markup=currency_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith("currency:"))
def choose_currency(call):
    currency = call.data.split(":", 1)[1]
    data = user_steps.get(call.from_user.id)
    if not data:
        bot.answer_callback_query(call.id, "ابدأ طلباً جديداً من القائمة.", show_alert=True)
        return
    data["currency"] = currency
    data["step"] = "amount"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"أرسل المبلغ بالأرقام فقط ({currency}).")

@bot.message_handler(func=lambda m: m.from_user.id in user_steps and user_steps[m.from_user.id].get("step") == "amount", content_types=["text"])
def get_amount(message):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("100000000"):
            raise InvalidOperation
        amount_text = format(amount.normalize(), "f")
    except (InvalidOperation, ValueError):
        bot.send_message(message.chat.id, "المبلغ غير صحيح. أرسل رقماً أكبر من صفر، مثل 25 أو 25.50.")
        return
    user_steps[message.from_user.id]["amount"] = amount_text
    user_steps[message.from_user.id]["step"] = "note"
    bot.send_message(message.chat.id, "أرسل ملاحظة مختصرة أو رقم مرجع إن وجد، أو أرسل - إذا لا توجد ملاحظة. لا ترسل كلمات مرور أو رموز تحقق.")

@bot.message_handler(func=lambda m: m.from_user.id in user_steps and user_steps[m.from_user.id].get("step") == "note", content_types=["text"])
def get_note(message):
    data = user_steps.get(message.from_user.id)
    if not data:
        return
    note = (message.text or "").strip()
    if len(note) > 400:
        bot.send_message(message.chat.id, "الملاحظة طويلة. أرسل 400 حرف أو أقل.")
        return
    if note == "-":
        note = ""
    user = message.from_user
    with connect_db() as conn:
        cur = conn.execute(
            """INSERT INTO requests
            (user_id, username, full_name, kind, currency, amount, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, user.first_name or "", data["kind"], data["currency"],
             data["amount"], note, datetime.now(timezone.utc).isoformat())
        )
        request_id = cur.lastrowid
    user_steps.pop(user.id, None)

    kind_ar = "إيداع" if data["kind"] == "deposit" else "سحب"
    currency_ar = "دولار أمريكي" if data["currency"] == "USD" else "ليرة سورية"
    bot.send_message(
        message.chat.id,
        f"✅ تم استلام طلبك رقم <b>#{request_id}</b>.\n"
        f"النوع: {kind_ar}\nالعملة: {currency_ar}\nالمبلغ: {safe(data['amount'])}\n"
        "الحالة: قيد المراجعة.\nسنرسل لك إشعاراً بعد مراجعة الإدارة.",
        reply_markup=main_menu()
    )

    admin_kb = types.InlineKeyboardMarkup(row_width=2)
    admin_kb.add(
        types.InlineKeyboardButton("✅ موافقة على الطلب", callback_data=f"decision:approved:{request_id}"),
        types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"decision:rejected:{request_id}")
    )
    username = ("@" + user.username) if user.username else "غير متوفر"
    admin_text = (
        f"🔔 <b>طلب جديد #{request_id}</b>\n"
        f"العميل: {safe(user.first_name)}\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"اسم المستخدم: {safe(username)}\n"
        f"النوع: {kind_ar}\nالعملة: {currency_ar}\n"
        f"المبلغ: {safe(data['amount'])}\n"
        f"ملاحظة: {safe(note) if note else 'لا توجد'}\n\n"
        "راجع العملية خارج البوت وفق إجراءات iChancy قبل تسجيل قرارك. زر الموافقة يغيّر حالة الطلب فقط ولا ينفذ تحويلاً مالياً."
    )
    try:
        bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
    except Exception:
        logging.exception("Could not notify admin")

@bot.callback_query_handler(func=lambda call: call.data.startswith("decision:"))
def decide_request(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "هذا الإجراء مخصص للإدارة فقط.", show_alert=True)
        return
    parts = call.data.split(":")
    if len(parts) != 3 or parts[1] not in ("approved", "rejected") or not parts[2].isdigit():
        bot.answer_callback_query(call.id, "طلب غير صالح.", show_alert=True)
        return
    status, request_id = parts[1], int(parts[2])
    with connect_db() as conn:
        req = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            bot.answer_callback_query(call.id, "الطلب غير موجود.", show_alert=True)
            return
        if req["status"] != "pending":
            bot.answer_callback_query(call.id, "تمت معالجة هذا الطلب مسبقاً.", show_alert=True)
            return
        conn.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))

    status_ar = "تمت الموافقة على طلبك بعد المراجعة" if status == "approved" else "تم رفض طلبك بعد المراجعة"
    try:
        bot.send_message(req["user_id"], f"تحديث الطلب <b>#{request_id}</b>: {status_ar}. للاستفسار تواصل مع الإدارة.")
    except Exception:
        logging.exception("Could not notify customer")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.answer_callback_query(call.id, "تم حفظ القرار.")
    bot.send_message(call.message.chat.id, f"تم تحديث حالة الطلب #{request_id}: {'مقبول' if status == 'approved' else 'مرفوض'}.")

@bot.callback_query_handler(func=lambda call: call.data == "my_requests")
def my_requests(call):
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT id, kind, currency, amount, status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (call.from_user.id,)
        ).fetchall()
    bot.answer_callback_query(call.id)
    if not rows:
        bot.send_message(call.message.chat.id, "ليس لديك طلبات مسجلة حتى الآن.", reply_markup=back_menu())
        return
    lines = ["📋 <b>آخر طلباتك:</b>"]
    for row in rows:
        kind = "إيداع" if row["kind"] == "deposit" else "سحب"
        status = {"pending": "قيد المراجعة", "approved": "مقبول", "rejected": "مرفوض"}.get(row["status"], row["status"])
        lines.append(f"#{row['id']} — {kind} — {safe(row['amount'])} {row['currency']} — {status}")
    bot.send_message(call.message.chat.id, "\n".join(lines), reply_markup=back_menu())

@bot.callback_query_handler(func=lambda call: call.data == "contact")
def contact(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "للتواصل مع الإدارة، أرسل رسالتك إلى حساب الكاشيرة عبر قناة التواصل التي تزودنا بها لاحقاً.", reply_markup=back_menu())

@bot.callback_query_handler(func=lambda call: call.data == "home")
def home(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "القائمة الرئيسية:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel(call):
    user_steps.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "تم إلغاء الطلب.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: True, content_types=["text"])
def fallback(message):
    bot.send_message(message.chat.id, "لم أفهم طلبك. أرسل /start لعرض القائمة الرئيسية.", reply_markup=main_menu())

if __name__ == "__main__":
    init_db()
    logging.info("VELORA-VIP is starting")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
