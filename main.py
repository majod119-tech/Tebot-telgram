import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import requests
import datetime
from pymongo import MongoClient

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

# --- المعالج الشامل للرسائل (نصوص + ملفات) ---
# لاحظ أننا أضفنا 'document' لكي يستطيع البوت استقبال ملفات الـ CSV
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text
    state = user_states.get(chat_id)

    # 1️⃣ زر الدخول لمساعد OpenClaw
    if text == "🦞 مساعد OpenClaw":
        user_states[chat_id] = "openclaw_admin"
        bot.send_message(
            chat_id, 
            "🦞 **مرحباً بك في وحدة OpenClaw للتحليل المتقدم!**\n\n"
            "• للتحليل التنبؤي: أرسل ملف (رايات) بصيغة CSV هنا مباشرة.\n"
            "• للبحث: اكتب (ابحث عن اسم الطالب).\n"
            "• للأوامر: اكتب (امر ls) أو أي سؤال إداري.\n\n"
            "أنا جاهز لاستقبال بياناتك وأوامرك.", 
            parse_mode="Markdown",
            reply_markup=cancel_menu()
        )
        return

    # 2️⃣ حالة المستخدم داخل OpenClaw
    if state == "openclaw_admin":
        if text == "العودة للقائمة الرئيسية 🏠":
            user_states[chat_id] = None
            bot.send_message(chat_id, "تم إغلاق اتصال OpenClaw.", reply_markup=telebot.types.ReplyKeyboardRemove())
            return
            
        # 🟢 الميزة الجديدة: إذا أرسل المدير ملفاً (Document)
        if message.document:
            try:
                msg = bot.send_message(chat_id, "⏳ جاري تحميل الملف من التلجرام وإرساله لسيرفر OpenClaw...")
                
                # تحميل الملف من التلجرام
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                # تحويل الملف إلى نص (UTF-8)
                csv_text = downloaded_file.decode('utf-8')
                
                # تجهيز الرسالة السحرية وإرسالها للسيرفر الجديد
                payload = {"message": "حفظ_بيانات_رايات\n" + csv_text}
                
                # الاتصال بسيرفر OpenClaw
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                
                # عرض النتيجة للمدير
                reply = response.json().get("response", "تم استلام الرد.")
                bot.edit_message_text(reply, chat_id=chat_id, message_id=msg.message_id, parse_mode='Markdown')
                
            except UnicodeDecodeError:
                bot.send_message(chat_id, "⚠️ خطأ: يرجى التأكد أن ملف الـ CSV محفوظ بتنسيق (UTF-8) لكي يدعم اللغة العربية.")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ حدث خطأ أثناء معالجة الملف: {str(e)}")
            return

        # 🔵 إذا أرسل المدير نصاً عادياً (أوامر أو استفسارات)
        if text:
            bot.send_chat_action(chat_id, 'typing')
            try:
                payload = {"message": text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                reply = response.json().get("response", "لم يتم استلام رد من السيرفر.")
                bot.reply_to(message, reply, parse_mode='Markdown')
            except requests.exceptions.Timeout:
                bot.reply_to(message, "⚠️ سيرفر OpenClaw يستغرق وقتاً طويلاً للرد (Timeout). يرجى المحاولة بعد قليل.")
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطأ في الاتصال بسيرفر OpenClaw المستقل: {str(e)}")
            return

# --- تشغيل البوت ---
if __name__ == "__main__":
    print("البوت الأساسي يعمل الآن ومستعد للاتصال بـ OpenClaw...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

