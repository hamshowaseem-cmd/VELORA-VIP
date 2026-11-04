import telebot

TOKEN = "ضع_توكن_البوت_هنا"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "أهلاً بك في VELORA VIP 🌟\n\n"
        "مرحباً بك في منصتنا.\n"
        "اختر من القائمة للمتابعة:"
    )

bot.infinity_polling()
