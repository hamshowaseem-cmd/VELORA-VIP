import os
import sys
import telebot
from telebot import types

TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("TOKEN")
)
TOKEN = TOKEN.strip() if TOKEN else ""

if not TOKEN or ":" not in TOKEN:
    print("خطأ: أضف رمز البوت الكامل في متغير TELEGRAM_BOT_TOKEN داخل إعدادات الاستضافة.")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

WELCOME = (
    "أهلاً بك في <b>VELORA VIP</b> 🌟\n"
    "دليلك العربي للمعلومات والإرشادات المتعلقة بخدمات iChancy.\n\n"
    "اختر ما تريد من القائمة:"
)

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 خدمات iChancy", callback_data="services"),
        types.InlineKeyboardButton("📘 دليل الاستخدام", callback_data="guide"),
    )
    markup.add(
        types.InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq"),
        types.InlineKeyboardButton("🔐 الأمان والحماية", callback_data="safety"),
    )
    markup.add(
        types.InlineKeyboardButton("☎️ التواصل مع الإدارة", callback_data="contact"),
        types.InlineKeyboardButton("ℹ️ حول VELORA VIP", callback_data="about"),
    )
    return markup

def send_home(chat_id):
    bot.send_message(chat_id, WELCOME, reply_markup=main_menu())

@bot.message_handler(commands=["start", "menu"])
def start(message):
    send_home(message.chat.id)

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "لإظهار القائمة الرئيسية أرسل /start. استخدم الأزرار للتنقل بين الأقسام.",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    pages = {
        "services": (
            "🎯 <b>خدمات iChancy</b>\n\n"
            "يوفر VELORA VIP حالياً إرشادات ومعلومات عامة حول استخدام المنصة. "
            "الخدمات المباشرة أو عمليات الشحن والسحب غير مفعّلة في البوت حالياً.\n\n"
            "لا توجد حتى الآن وصلة ربط رسمية أو تفويض مثبت من iChancy."
        ),
        "guide": (
            "📘 <b>دليل الاستخدام</b>\n\n"
            "1. اختر القسم الذي تحتاجه من القائمة.\n"
            "2. اقرأ التعليمات بعناية.\n"
            "3. لا تنفذ أي عملية مالية إلا عبر القنوات الرسمية التي تتحقق منها بنفسك.\n"
            "4. ارجع إلى القائمة الرئيسية للانتقال إلى قسم آخر."
        ),
        "faq": (
            "❓ <b>الأسئلة الشائعة</b>\n\n"
            "• هل البوت تابع رسمياً لـ iChancy؟ لا يوجد حالياً ما يثبت وجود شراكة أو تفويض رسمي.\n"
            "• هل يمكن الشحن أو السحب من البوت؟ هذه الوظائف غير مفعّلة.\n"
            "• كيف أعود للقائمة؟ اضغط زر «القائمة الرئيسية»."
        ),
        "safety": (
            "🔐 <b>الأمان والحماية</b>\n\n"
            "• لا ترسل كلمة المرور لأي شخص.\n"
            "• لا تشارك رمز تسجيل الدخول أو رمز التحقق.\n"
            "• لا تحول الأموال إلى أفراد أو جهات غير موثوقة.\n"
            "• تحقق من عنوان الموقع الرسمي قبل تسجيل الدخول."
        ),
        "contact": (
            "☎️ <b>التواصل مع الإدارة</b>\n\n"
            "لم يتم إعداد حساب دعم إداري داخل البوت بعد. "
            "سيُضاف رابط التواصل بعد تحديد حساب الإدارة."
        ),
        "about": (
            "ℹ️ <b>حول VELORA VIP</b>\n\n"
            "بوت عربي مستقل لتقديم الإرشادات والمعلومات المتعلقة بخدمات iChancy. "
            "ليس ممثلاً رسمياً للمنصة ولا يجمع كلمات المرور أو رموز التحقق."
        ),
    }
    if call.data == "home":
        bot.answer_callback_query(call.id)
        send_home(call.message.chat.id)
        return
    text = pages.get(call.data)
    if text:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "هذا الخيار غير متاح حالياً.")

@bot.message_handler(func=lambda message: True, content_types=["text"])
def fallback(message):
    bot.send_message(
        message.chat.id,
        "لم أفهم طلبك. اختر أحد الأقسام من القائمة أو أرسل /start.",
        reply_markup=main_menu()
    )

if __name__ == "__main__":
    print("VELORA VIP is starting...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
