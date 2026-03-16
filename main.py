import os
import threading
import time
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import requests
from pymongo import MongoClient
from flask import Flask

# --- إعدادات البيئة ---
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
MONGODB_URI = os.environ.get("MONGODB_URI")
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat"

bot = telebot.TeleBot(TOKEN)
user_states = {}

# --- الاتصال بقاعدة البيانات ---
db_collection = None
if MONGODB_URI:
    try:
        client = MongoClient(MONGODB_URI)
        db_collection = client["computer_dept_db"]["trainees"]
    except Exception as e:
        print("خطأ في الاتصال بالقاعدة:", e)

# --- سيرفر ويب وهمي (لإرضاء منصة Render) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Tebot Telegram Bot is Live and Polling!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- لوحات المفاتيح ---
def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🦞 مساعد OpenClaw"))
    markup.add(KeyboardButton("العودة للقائمة الرئيسية 🏠"))
    return markup

def cancel_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("العودة للقائمة الرئيسية 🏠"))
    return markup

# --- الأوامر الأساسية ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    bot.reply_to(message, "مرحباً بك في المساعد الرقمي لقسم الحاسب الآلي.\n(هذه النسخة المحدثة للاتصال بخوادم OpenClaw).")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    chat_id = message.chat.id
    if str(chat_id) == str(ADMIN_ID) or not ADMIN_ID:
        bot.send_message(chat_id, "مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم.", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "عذراً، هذا الأمر مخصص للإدارة فقط.")

# --- المعالج الشامل للرسائل والملفات ---
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text
    state = user_states.get(chat_id)

    if text == "🦞 مساعد OpenClaw":
        user_states[chat_id] = "openclaw_admin"
        bot.send_message(
            chat_id, 
            "🦞 **مرحباً بك في وحدة OpenClaw للتحليل المتقدم!**\n\n"
            "• للتحليل التنبؤي: أرسل ملف (رايات) بصيغة CSV هنا مباشرة.\n"
            "• للأوامر: اكتب (تفريغ رايات) لتنظيف القاعدة.\n"
            "• للاستفسار: اطرح أي سؤال إداري.\n\n"
            "أنا جاهز.", 
            parse_mode="Markdown",
            reply_markup=cancel_menu()
        )
        return

    if state == "openclaw_admin":
        if text == "العودة للقائمة الرئيسية 🏠":
            user_states[chat_id] = None
            bot.send_message(chat_id, "تم إغلاق اتصال OpenClaw.", reply_markup=telebot.types.ReplyKeyboardRemove())
            return
            
        if message.document:
            try:
                msg = bot.send_message(chat_id, "⏳ جاري إرسال الملف لسيرفر OpenClaw...")
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                csv_text = downloaded_file.decode('utf-8')
                
                payload = {"message": "حفظ_بيانات_رايات\n" + csv_text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                
                reply = response.json().get("response", "تم استلام الرد.")
                bot.edit_message_text(reply, chat_id=chat_id, message_id=msg.message_id, parse_mode='Markdown')
                
            except UnicodeDecodeError:
                bot.send_message(chat_id, "⚠️ خطأ: يرجى التأكد أن الملف بتنسيق (UTF-8).")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ خطأ: {str(e)}")
            return

        if text:
            bot.send_chat_action(chat_id, 'typing')
            try:
                payload = {"message": text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                reply = response.json().get("response", "خطأ في الاتصال.")
                bot.reply_to(message, reply, parse_mode='Markdown')
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطأ: {str(e)}")
            return

# --- تشغيل البوت مع درع الحماية ضد الانهيار (409) ---
if __name__ == "__main__":
    # تشغيل السيرفر الوهمي في مسار خلفي لإسكات Render
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    print("جاري تشغيل البوت الأساسي...")
    
    # حلقة لا نهائية تمنع البوت من الانهيار حتى لو حدث تضارب
    while True:
        try:
            bot.remove_webhook() # تنظيف أي اتصالات قديمة أو معلقة
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ حدث تضارب 409 (نسخة أخرى تعمل). سأنتظر 10 ثوانٍ وأحاول مجدداً...\n{e}")
            time.sleep(10) # الانتظار حتى تقوم المنصة بإغلاق النسخة القديمة


