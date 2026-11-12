import os
import sys
import telebot
from telebot import types

# FadeHost may expose the Telegram secret under any of these names.
TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("TOKEN")
)
TOKEN = TOKEN.strip() if TOKEN else ""

if not TOKEN or ":" not in TOKEN:
    print(
        "خطأ في رمز Telegram: أضف الرمز الكامل من BotFather "
        "في متغير TELEGRAM_BOT_TOKEN داخل FadeHost."
    )
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

WELCOME = (
    "أهلاً بك في VELORA VIP 🌟\n"
    "منصتك للخدمات والمعلومات باللغة العربية.\n\n"
    "اختر أحد الخيارات من القائمة:"
)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🛎️ الخدمات", "📖 طريقة الاستخدام")
    markup.row("☎️ التواصل مع الإدارة", "ℹ️ حول VELORA VIP")
    return markup

@bot.message_handler(commands=["start", "menu"])
def start(message):
    bot.send_message(message.chat.id, WELCOME, reply_markup=main_menu())

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "لإظهار القائمة الرئيسية أرسل /start.\n"
        "ثم اختر الخدمة التي تريد معرفة المزيد عنها.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "🛎️ الخدمات")
def services(message):
    bot.send_message(
        message.chat.id,
        "🛎️ الخدمات\n\n"
        "نعمل حالياً على تجهيز الخدمات وإتاحتها تدريجياً.\n"
        "تابع البوت للاطلاع على التحديثات الرسمية.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "📖 طريقة الاستخدام")
def instructions(message):
    bot.send_message(
        message.chat.id,
        "📖 طريقة الاستخدام\n\n"
        "1- اختر الخدمة من القائمة الرئيسية.\n"
        "2- اقرأ تفاصيلها قبل المتابعة.\n"
        "3- عند الحاجة، تواصل مع الإدارة.\n\n"
        "لا ترسل كلمات المرور أو رموز التحقق إلى أي شخص.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "☎️ التواصل مع الإدارة")
def contact(message):
    bot.send_message(
        message.chat.id,
        "☎️ للتواصل مع الإدارة، يرجى متابعة بيانات التواصل "
        "الرسمية التي ستُعلن هنا قريباً.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ حول VELORA VIP")
def about(message):
    bot.send_message(
        message.chat.id,
        "VELORA VIP 🌟\n"
        "بوت عربي لتقديم المعلومات ومتابعة الخدمات.\n"
        "سيتم الإعلان عن أي خدمة جديدة عبر القنوات الرسمية.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: True)
def fallback(message):
    bot.send_message(
        message.chat.id,
        "يرجى اختيار أحد الأزرار الموجودة في القائمة، أو إرسال /start.",
        reply_markup=main_menu()
    )

if __name__ == "__main__":
    print("VELORA VIP is starting...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
