import os
import sys
import re
import html
import secrets
import string
import unicodedata
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
SHAM_CASH_WALLET_CODE = (os.getenv("SHAM_CASH_WALLET_CODE") or "").strip()
SHAM_CASH_WALLET_NAME = (os.getenv("SHAM_CASH_WALLET_NAME") or "").strip()

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                desired_username TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)


def make_player_username(first_name, conn):
    # تحويل مبسط للاسم العربي إلى أحرف لاتينية ثم إضافة اللاحقة المطلوبة.
    arabic = {
        "ا":"a","أ":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j",
        "ح":"h","خ":"kh","د":"d","ذ":"th","ر":"r","ز":"z","س":"s","ش":"sh",
        "ص":"s","ض":"d","ط":"t","ظ":"z","ع":"a","غ":"gh","ف":"f","ق":"q",
        "ك":"k","ل":"l","م":"m","ن":"n","ه":"h","و":"w","ي":"y","ى":"a",
        "ة":"h","ؤ":"w","ئ":"y"
    }
    parts = []
    for char in first_name.lower():
        if char in arabic:
            parts.append(arabic[char])
        elif char.isascii() and char.isalnum():
            parts.append(char)
        elif char.isspace() or char in "-_":
            parts.append("_")
    base = re.sub(r"_+", "_", "".join(parts)).strip("_") or "player"
    base = base[:20].rstrip("_") or "player"
    candidate = f"{base}_velora"
    suffix = 2
    while conn.execute(
        "SELECT 1 FROM player_registrations WHERE lower(desired_username)=lower(?) LIMIT 1",
        (candidate,)
    ).fetchone():
        tail = str(suffix)
        candidate = f"{base[:max(1, 20-len(tail))]}_velora{tail}"
        suffix += 1
    return candidate

def make_player_password():
    # كلمة المرور الموحدة التي طلبتها الإدارة.
    # استخدام كلمة واحدة لجميع اللاعبين غير آمن؛ يجب تغييرها إلى كلمة فريدة لكل لاعب.
    return "W1234"

def main_menu(user_id=None):
    # أزرار تيليغرام الأصلية؛ لا تسمح واجهة Bot API بتغيير ألوان الأزرار.
    kb = types.InlineKeyboardMarkup(row_width=2)
    if user_id == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("🛠️ لوحة الإدارة", callback_data="admin:home"))
    kb.row(
        types.InlineKeyboardButton("⚡ معلومات الحساب", callback_data="account_info"),
        types.InlineKeyboardButton("💥 جميع العروض", callback_data="offers")
    )
    kb.row(
        types.InlineKeyboardButton("💳 طلب إيداع", callback_data="new:deposit"),
        types.InlineKeyboardButton("💸 طلب سحب", callback_data="new:withdraw")
    )
    kb.row(
        types.InlineKeyboardButton("👤 إنشاء حساب لاعب", callback_data="player_register"),
        types.InlineKeyboardButton("📋 السجل المالي / طلباتي", callback_data="my_requests")
    )
    kb.row(
        types.InlineKeyboardButton("🎁 كود هدية", callback_data="coming:gift"),
        types.InlineKeyboardButton("🎁 إهداء رصيد", callback_data="coming:gift_balance")
    )
    kb.row(
        types.InlineKeyboardButton("👥 الإحالات", callback_data="coming:referrals"),
        types.InlineKeyboardButton("🎡 تدوير العجلة", callback_data="coming:wheel")
    )
    kb.row(
        types.InlineKeyboardButton("📜 دليل المستخدم والشروط", callback_data="coming:guide"),
        types.InlineKeyboardButton("☎️ مراسلة الدعم", callback_data="contact")
    )
    return kb

def registration_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔐 فتح موقع iChancy الرسمي", url="https://ichancy.com/"))
    kb.add(types.InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"))
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

def admin_panel_markup():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊 ملخص الكاشيرة", callback_data="admin:stats"),
        types.InlineKeyboardButton("💳 طلبات الإيداع والسحب المعلقة", callback_data="admin:pending"),
        types.InlineKeyboardButton("👤 طلبات تسجيل اللاعبين المعلقة", callback_data="admin:registrations"),
        types.InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")
    )
    return kb

def send_admin_panel(chat_id):
    bot.send_message(
        chat_id,
        "🛠️ <b>لوحة إدارة VELORA-VIP</b>\nاختر القسم الذي تريد متابعته.\n\n"
        "تنبيه: هذه اللوحة تدير الطلبات والسجلات فقط، ولا تنفّذ تحويلات مالية إلى iChancy.",
        reply_markup=admin_panel_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin:"))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "هذا القسم مخصص للإدارة فقط.", show_alert=True)
        return
    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    if action == "home":
        send_admin_panel(call.message.chat.id)
        return
    if action == "stats":
        with connect_db() as conn:
            request_counts = conn.execute(
                "SELECT kind, status, COUNT(*) AS n FROM requests GROUP BY kind, status"
            ).fetchall()
            registration_counts = conn.execute(
                "SELECT status, COUNT(*) AS n FROM player_registrations GROUP BY status"
            ).fetchall()
        lines = ["📊 <b>ملخص الكاشيرة</b>", "", "<b>طلبات الإيداع والسحب:</b>"]
        for row in request_counts:
            kind = "إيداع" if row["kind"] == "deposit" else "سحب"
            status = {"pending": "معلقة", "approved": "مقبولة", "rejected": "مرفوضة"}.get(row["status"], row["status"])
            lines.append(f"{kind} — {status}: {row['n']}")
        lines.append("")
        lines.append("<b>تسجيل اللاعبين:</b>")
        for row in registration_counts:
            status = {"pending": "قيد المراجعة", "approved": "مقبولة مبدئياً", "rejected": "مرفوضة"}.get(row["status"], row["status"])
            lines.append(f"{status}: {row['n']}")
        if not request_counts:
            lines.append("لا توجد طلبات مالية بعد.")
        if not registration_counts:
            lines.append("لا توجد طلبات تسجيل بعد.")
        lines.extend(["", "لا يتضمن هذا الملخص رصيد محفظة iChancy الفعلي."])
        bot.send_message(call.message.chat.id, "\n".join(lines), reply_markup=admin_panel_markup())
        return
    if action == "pending":
        with connect_db() as conn:
            rows = conn.execute(
                "SELECT * FROM requests WHERE status='pending' ORDER BY id DESC LIMIT 10"
            ).fetchall()
        if not rows:
            bot.send_message(call.message.chat.id, "لا توجد طلبات إيداع أو سحب معلقة.", reply_markup=admin_panel_markup())
            return
        bot.send_message(call.message.chat.id, "💳 <b>الطلبات المالية المعلقة</b>")
        for row in rows:
            kind = "إيداع" if row["kind"] == "deposit" else "سحب"
            currency = "دولار" if row["currency"] == "USD" else "ليرة سورية"
            text = (
                f"طلب #{row['id']} — {kind}\n"
                f"العميل: {safe(row['full_name'])}\n"
                f"المبلغ: {safe(row['amount'])} {currency}\n"
                f"ملاحظة: {safe(row['note']) if row['note'] else 'لا توجد'}\n"
                "الموافقة هنا تغيّر حالة الطلب فقط ولا تحوّل الأموال."
            )
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✅ قبول الطلب", callback_data=f"decision:approved:{row['id']}"),
                types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"decision:rejected:{row['id']}")
            )
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        return
    if action == "registrations":
        with connect_db() as conn:
            rows = conn.execute(
                "SELECT * FROM player_registrations WHERE status='pending' ORDER BY id DESC LIMIT 10"
            ).fetchall()
        if not rows:
            bot.send_message(call.message.chat.id, "لا توجد طلبات تسجيل معلقة.", reply_markup=admin_panel_markup())
            return
        bot.send_message(call.message.chat.id, "👤 <b>طلبات تسجيل اللاعبين المعلقة</b>")
        for row in rows:
            text = (
                f"طلب تسجيل #{row['id']}\n"
                f"الاسم: {safe(row['first_name'])} {safe(row['last_name'])}\n"
                f"اسم المستخدم: <code>{safe(row['desired_username'])}</code>\n"
                "القرار لا ينشئ حساب iChancy تلقائياً."
            )
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✅ قبول الطلب", callback_data=f"player_decision:approved:{row['id']}"),
                types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"player_decision:rejected:{row['id']}")
            )
            bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.message_handler(commands=["start", "menu"])
def start(message):
    user_steps.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "أهلاً بك في <b>VELORA-VIP</b> 🌟\n"
        "خدمات طلبات الكاشيرة باللغة العربية.\n\n"
        "اختر الخدمة المطلوبة. جميع الطلبات تبقى قيد المراجعة، ولا تعتبر الموافقة داخل البوت إثباتاً لتحويل مالي.",
        reply_markup=main_menu(message.from_user.id)
    )

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "هذا القسم مخصص للإدارة فقط.")
        return
    send_admin_panel(message.chat.id)

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(message.chat.id, "أرسل /start لعرض القائمة الرئيسية. لا ترسل كلمات المرور أو رموز التحقق أو بيانات البطاقات.")

@bot.callback_query_handler(func=lambda call: call.data == "account_info")
def account_info(call):
    user = call.from_user
    username = ("@" + user.username) if user.username else "غير محدد"
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "⚡ <b>معلومات حسابك في VELORA-VIP</b>\n"
        f"الاسم: {safe(user.first_name)}\n"
        f"اسم تيليغرام: {safe(username)}\n"
        f"رقم تيليغرام: <code>{user.id}</code>\n\n"
        "هذه بيانات تيليغرام فقط، وليست بيانات دخول iChancy.",
        reply_markup=back_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "offers")
def offers(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "💥 <b>العروض</b>\nلا توجد عروض مفعّلة حالياً. تابع إشعارات البوت لمعرفة العروض المعتمدة.",
        reply_markup=back_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("coming:"))
def coming_soon(call):
    labels = {
        "gift": "كود الهدية",
        "gift_balance": "إهداء الرصيد",
        "referrals": "الإحالات",
        "wheel": "تدوير العجلة",
        "guide": "دليل المستخدم والشروط"
    }
    key = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"🛠️ <b>{safe(labels.get(key, 'هذه الخدمة'))}</b>\nهذه الخدمة غير مفعّلة بعد. سنعلن عنها عند تجهيزها.",
        reply_markup=back_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "player_register")
def player_register(call):
    bot.answer_callback_query(call.id)
    if call.message.chat.type != "private":
        bot.send_message(call.message.chat.id, "يرجى فتح البوت في محادثة خاصة لإتمام التسجيل بأمان.")
        return
    user_steps[call.from_user.id] = {"flow": "player_registration", "step": "player_first_name"}
    bot.send_message(
        call.message.chat.id,
        "👤 <b>طلب التسجيل في VELORA VIP</b>\n"
        "سيُنشئ البوت اسم مستخدم بصيغة الاسم_velora ويعطيك كلمة المرور الموحدة المعتمدة. "
        "ستستخدمهما بنفسك عند التسجيل في موقع iChancy الرسمي.\n\n"
        "أرسل الاسم الأول:"
    )

@bot.message_handler(func=lambda m: m.from_user.id in user_steps and user_steps[m.from_user.id].get("step") == "player_first_name", content_types=["text"])
def player_first_name(message):
    value = (message.text or "").strip()
    if not value or len(value) > 60:
        bot.send_message(message.chat.id, "الاسم الأول غير صالح. أرسله بطول لا يتجاوز 60 حرفاً.")
        return
    user_steps[message.from_user.id]["first_name"] = value
    user_steps[message.from_user.id]["step"] = "player_last_name"
    bot.send_message(message.chat.id, "أرسل اسم العائلة:")

@bot.message_handler(func=lambda m: m.from_user.id in user_steps and user_steps[m.from_user.id].get("step") == "player_last_name", content_types=["text"])
def player_last_name(message):
    value = (message.text or "").strip()
    if not value or len(value) > 60:
        bot.send_message(message.chat.id, "اسم العائلة غير صالح. أرسله بطول لا يتجاوز 60 حرفاً.")
        return
    user_steps[message.from_user.id]["last_name"] = value
    user_steps[message.from_user.id]["step"] = "player_confirm_details"
    data = user_steps[message.from_user.id]
    user = message.from_user
    with connect_db() as conn:
        desired_username = make_player_username(data["first_name"], conn)
        cur = conn.execute(
            """INSERT INTO player_registrations
            (user_id, telegram_username, first_name, last_name, desired_username, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.id, user.username, data["first_name"], data["last_name"], desired_username,
             datetime.now(timezone.utc).isoformat())
        )
        registration_id = cur.lastrowid
    password = make_player_password()
    user_steps.pop(user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ <b>جهزنا بيانات التسجيل رقم #{registration_id}</b>\n"
        f"الاسم: {safe(data['first_name'])} {safe(data['last_name'])}\n"
        f"اسم المستخدم: <code>{safe(desired_username)}</code>\n"
        f"كلمة المرور الموحدة: <code>{safe(password)}</code>\n\n"
        "احفظ كلمة المرور ولا تشاركها مع أحد. افتح موقع iChancy الرسمي وسجّل بنفسك بهذه البيانات، "
        "إذا كانت شروط الموقع تسمح باسم المستخدم وكلمة المرور. غيّر كلمة المرور بعد الدخول إن أمكن. "
        "هذا البوت لا ينشئ الحساب داخل iChancy ولا يتحقق من قبول الاسم هناك.",
        reply_markup=registration_menu()
    )
    admin_kb = types.InlineKeyboardMarkup(row_width=2)
    admin_kb.add(
        types.InlineKeyboardButton("✅ قبول الطلب", callback_data=f"player_decision:approved:{registration_id}"),
        types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"player_decision:rejected:{registration_id}")
    )
    tg_name = ("@" + user.username) if user.username else "غير متوفر"
    admin_text = (
        f"👤 <b>طلب تسجيل لاعب جديد #{registration_id}</b>\n"
        f"الاسم: {safe(data['first_name'])} {safe(data['last_name'])}\n"
        f"اسم المستخدم المقترح: <code>{safe(desired_username)}</code>\n"
        f"Telegram: {safe(tg_name)} — ID: <code>{user.id}</code>\n\n"
        "اللاعب هو من يُدخل البيانات بنفسه في موقع iChancy. لا تُرسل كلمة المرور إلى الإدارة."
    )
    try:
        bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
    except Exception:
        logging.exception("Could not notify admin about player registration")

@bot.callback_query_handler(func=lambda call: call.data.startswith("player_decision:"))
def decide_player_registration(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "هذا الإجراء مخصص للإدارة فقط.", show_alert=True)
        return
    parts = call.data.split(":")
    if len(parts) != 3 or parts[1] not in ("approved", "rejected") or not parts[2].isdigit():
        bot.answer_callback_query(call.id, "طلب غير صالح.", show_alert=True)
        return
    status, registration_id = parts[1], int(parts[2])
    with connect_db() as conn:
        req = conn.execute("SELECT * FROM player_registrations WHERE id=?", (registration_id,)).fetchone()
        if not req:
            bot.answer_callback_query(call.id, "الطلب غير موجود.", show_alert=True)
            return
        if req["status"] != "pending":
            bot.answer_callback_query(call.id, "تمت معالجة هذا الطلب مسبقاً.", show_alert=True)
            return
        conn.execute("UPDATE player_registrations SET status=? WHERE id=?", (status, registration_id))
    message = ("تم قبول طلب التسجيل مبدئياً، وستتواصل معك الإدارة لإكمال الإجراء المعتمد."
               if status == "approved" else "نعتذر، تم رفض طلب التسجيل. تواصل مع الإدارة للاستفسار.")
    try:
        bot.send_message(req["user_id"], f"تحديث طلب التسجيل <b>#{registration_id}</b>: {message}")
    except Exception:
        logging.exception("Could not notify player about registration decision")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.answer_callback_query(call.id, "تم حفظ القرار.")
    bot.send_message(call.message.chat.id, f"تم تحديث طلب التسجيل #{registration_id}.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("new:"))
def new_request(call):
    kind = call.data.split(":", 1)[1]
    user_steps[call.from_user.id] = {"kind": kind}
    bot.answer_callback_query(call.id)
    label = "الإيداع" if kind == "deposit" else "السحب"
    if kind == "deposit":
        if SHAM_CASH_WALLET_CODE:
            owner_line = f"\nاسم المستفيد: <b>{safe(SHAM_CASH_WALLET_NAME)}</b>" if SHAM_CASH_WALLET_NAME else ""
            bot.send_message(
                call.message.chat.id,
                "💳 <b>بيانات الإيداع عبر شام كاش</b>\n"
                f"كود المحفظة: <code>{safe(SHAM_CASH_WALLET_CODE)}</code>"
                f"{owner_line}\n\n"
                "يمكنك نسخ الكود بالضغط عليه مطولاً. أرسل التحويل بعد التأكد من صحة بيانات المستفيد، ثم أكمل طلب الإيداع.\n"
                "لا ترسل كلمة مرور أو رمز تحقق.",
                reply_markup=back_menu()
            )
        else:
            bot.send_message(
                call.message.chat.id,
                "💳 لم تُضبط بيانات شام كاش بعد. تواصل مع الإدارة قبل إجراء أي تحويل.",
                reply_markup=back_menu()
            )
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
    data = user_steps[message.from_user.id]
    if data.get("kind") == "deposit":
        bonus = (Decimal(amount_text) * Decimal("0.15")).quantize(Decimal("0.01"))
        total = Decimal(amount_text) + bonus
        bot.send_message(
            message.chat.id,
            "🎁 <b>مكافأة التعبئة</b>\n"
            f"مبلغ التعبئة: <b>{safe(amount_text)} {data['currency']}</b>\n"
            f"مكافأة 15%: <b>{safe(format(bonus, 'f'))} {data['currency']}</b>\n"
            f"الإجمالي بعد المكافأة: <b>{safe(format(total, 'f'))} {data['currency']}</b>\n"
            "لا يوجد حد أدنى. تُراجع العملية أولاً، ولا يُضاف أي رصيد تلقائياً من هذا البوت."
        )
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
    bot.send_message(call.message.chat.id, "القائمة الرئيسية:", reply_markup=main_menu(call.from_user.id))

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

# نشر تلقائي: تفعيل ربط FadeHost مع GitHub بعد تحديث إعدادات النشر.
