import os
import sys
import telebot

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("خطأ: لم يتم ضبط متغير البيئة BOT_TOKEN في إعدادات الاستضافة.")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "أهلاً بك في VELORA VIP 🌟\n\n"
        "مرحباً بك في منصتنا.\n"
        "اختر من القائمة للمتابعة:"
    )

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    bot.send_message(
        message.chat.id,
        "أهلاً بك في VELORA VIP 🌟\n"
        "سيتم تفعيل الخدمات قريباً."
    )

if __name__ == "__main__":
    print("تم تشغيل VELORA VIP.")
    bot.infinity_polling(skip_pending=True)
