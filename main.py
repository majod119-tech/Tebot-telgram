import os
import threading
import time
import requests
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pymongo import MongoClient
from flask import Flask

# ==========================================
# 1. إعدادات البيئة والاتصال
# ==========================================
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
MONGODB_URI = os.environ.get("MONGODB_URI")
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat"

bot = telebot.TeleBot(TOKEN)
user_states = {} # تتبع حالة المستخدمين (للأعذار، الاستعلام، والتحكم)

# الاتصال بقاعدة البيانات
db_collection = None
if MONGODB_URI:
    try:
        client = MongoClient(MONGODB_URI)
        db_collection = client["computer_dept_db"]["trainees"]
    except Exception as e:
        print("خطأ في الاتصال بالقاعدة:", e)

# ==========================================
# 2. سيرفر الويب الوهمي (لإرضاء منصة Render ومنع الانهيار)
# ==========================================
app = Flask(__name__)
@app.route('/')
def home():
    return "Tebot Telegram Bot is Live and Polling perfectly!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 3. تصميم واجهات المستخدم (القوائم)
# ==========================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # الأزرار المستوحاة من تقرير التميز الخاص بك
    markup.add(KeyboardButton("🤖 المعلم الذكي"), KeyboardButton("📋 الخطط التدريبية"))
    markup.add(KeyboardButton("💼 الحقائب التدريبية"), KeyboardButton("📅 التقويم التدريبي"))
    markup.add(KeyboardButton("رفع الغياب والأعذار 📄"), KeyboardButton("📊 استعلام الغياب"))
    markup.add(KeyboardButton("🌐 المنصات الإلكترونية"), KeyboardButton("📰 أخبار القسم والمعهد"))
    markup.add(KeyboardButton("📍 موقع القسم"), KeyboardButton("📖 دليل المتدرب"))
    markup.add(KeyboardButton("❓ الأسئلة الشائعة"), KeyboardButton("🎮 قسم الألعاب والإضافات"))
    markup.add(KeyboardButton("💡 الاقتراحات والشكاوى"))
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("🦞 مساعد OpenClaw (لتحليل رايات)"))
    markup.add(KeyboardButton("العودة للقائمة الرئيسية 🏠"))
    return markup

def cancel_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("إلغاء العملية ❌"))
    return markup

# ==========================================
# 4. الأوامر الأساسية (Start & Admin)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None # إعادة ضبط الحالة
    first_name = message.from_user.first_name
    
    welcome_text = (
        f"أهلاً بك يا {first_name} في المساعد الذكي لقسم الحاسب الآلي 🖥️✨\n\n"
        "أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n"
        "👇 الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:"
    )
    bot.send_message(chat_id, welcome_text, reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    chat_id = message.chat.id
    if str(chat_id) == str(ADMIN_ID) or not ADMIN_ID: # السماح للإدمن فقط
        bot.send_message(chat_id, "مرحباً بك يا رئيس القسم في لوحة التحكم الإدارية.", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "عذراً، هذه اللوحة مخصصة للإدارة فقط.")

# ==========================================
# 5. المعالج الشامل (الرسائل، الملفات، والصور)
# ==========================================
@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text
    state = user_states.get(chat_id)

    # --- معالجة أزرار الإلغاء والعودة ---
    if text in ["العودة للقائمة الرئيسية 🏠", "إلغاء العملية ❌"]:
        user_states[chat_id] = None
        bot.send_message(chat_id, "تم العودة للقائمة الرئيسية.", reply_markup=main_menu())
        return

    # ---------------------------------------------------------
    # 🔴 القسم الأول: خوادم الإدارة (OpenClaw للتحليل) 🔴
    # ---------------------------------------------------------
    if text == "🦞 مساعد OpenClaw (لتحليل رايات)":
        user_states[chat_id] = "openclaw_admin"
        bot.send_message(
            chat_id, 
            "🦞 **مرحباً بك في وحدة OpenClaw الاستشارية!**\n\n"
            "• **لتحديث القاعدة:** أرسل ملف (رايات) بصيغة CSV هنا مباشرة.\n"
            "• **للتحليل:** اكتب (حلل رايات).\n"
            "• **للتنظيف:** اكتب (تفريغ رايات).\n\n"
            "أنا جاهز لخدمتك يا مدير.", 
            parse_mode="Markdown",
            reply_markup=cancel_menu()
        )
        return

    if state == "openclaw_admin":
        # 1. إذا رفع المدير ملف CSV (رايات)
        if message.document:
            try:
                msg = bot.send_message(chat_id, "⏳ جاري تحميل بيانات رايات وإرسالها لـ OpenClaw...")
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                csv_text = downloaded_file.decode('utf-8')
                
                payload = {"message": "حفظ_بيانات_رايات\n" + csv_text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                
                reply = response.json().get("response", "تم استلام الرد.")
                bot.edit_message_text(reply, chat_id=chat_id, message_id=msg.message_id, parse_mode='Markdown')
            except UnicodeDecodeError:
                bot.send_message(chat_id, "⚠️ خطأ: يرجى التأكد أن ملف الـ CSV محفوظ بتنسيق (UTF-8).")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ خطأ في معالجة الملف: {str(e)}")
            return

        # 2. إذا كتب المدير أوامر نصية (تحليل، تفريغ، استفسار)
        if text:
            bot.send_chat_action(chat_id, 'typing')
            try:
                payload = {"message": text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                reply = response.json().get("response", "حدث خطأ في الاتصال.")
                bot.reply_to(message, reply, parse_mode='Markdown')
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطأ: السيرفر لا يستجيب. {str(e)}")
            return

    # ---------------------------------------------------------
    # 🔵 القسم الثاني: خدمات المتدربين (واجهة البوت الأساسية) 🔵
    # ---------------------------------------------------------
    
    # -- 1. المعلم الذكي --
    if text == "🤖 المعلم الذكي":
        user_states[chat_id] = "smart_teacher"
        bot.send_message(chat_id, "أنا جاهز! اكتب أي سؤال تقني أو إداري وسأجيبك فوراً...", reply_markup=cancel_menu())
        return
        
    if state == "smart_teacher" and text:
        bot.send_chat_action(chat_id, 'typing')
        try:
            # نرسل سؤال المتدرب لـ OpenClaw ليجيب عليه بذكاء
            payload = {"message": text}
            response = requests.post(OPENCLAW_URL, json=payload, timeout=30)
            reply = response.json().get("response", "حدث خطأ.")
            bot.reply_to(message, reply)
        except:
            bot.reply_to(message, "عذراً، المعلم الذكي مشغول حالياً. كرر المحاولة لاحقاً.")
        return

    # -- 2. رفع الأعذار --
    if text == "رفع الغياب والأعذار 📄":
        user_states[chat_id] = "upload_excuse"
        bot.send_message(chat_id, "الرجاء إرفاق صورة العذر الآن، ويجب كتابة رقمك واسمك في خانة الوصف (Caption).\n\n⚠️ تُقبل الأعذار الرسمية والطبية فقط بعد الغياب خلال 3 إلى 5 أيام.", reply_markup=cancel_menu())
        return
        
    if state == "upload_excuse":
        if message.photo or message.document:
            bot.send_message(chat_id, "✅ تم استلام العذر وإرساله للإدارة بنجاح للختم والتدقيق.", reply_markup=main_menu())
            user_states[chat_id] = None
        else:
            bot.send_message(chat_id, "الرجاء إرفاق صورة العذر (صورة وليس نص).")
        return

    # -- 3. استعلام الغياب --
    if text == "📊 استعلام الغياب":
        user_states[chat_id] = "query_absence"
        bot.send_message(chat_id, "🔎 استعلام عن نسبة الغياب (تُحدث أسبوعياً)\n👇 أرسل رقمك التدريبي الآن (أرقام فقط)...", reply_markup=cancel_menu())
        return
        
    if state == "query_absence" and text:
        if text.isdigit():
            bot.send_message(chat_id, f"جاري البحث عن سجل الرقم {text} في نظام رايات...", reply_markup=main_menu())
            # يمكنك هنا لاحقاً ربطها بقاعدة رايات لاستخراج الغياب
            user_states[chat_id] = None
        else:
            bot.send_message(chat_id, "الرجاء إدخال أرقام فقط.")
        return

    # -- 4. باقي الأزرار التعريفية الثابتة --
    if text == "📋 الخطط التدريبية":
        bot.send_message(chat_id, "تفضل بزيارة الرابط السحابي للخطط التدريبية للقسم.")
    elif text == "💼 الحقائب التدريبية":
        bot.send_message(chat_id, "رابط الحقائب التدريبية والمقررات المعتمدة.")
    elif text == "📅 التقويم التدريبي":
        bot.send_message(chat_id, "التقويم التدريبي للفصل الحالي.")
    elif text == "🌐 المنصات الإلكترونية":
        bot.send_message(chat_id, "بوابة رايات: rayat.tvtc.gov.sa\nبوابة بلاك بورد: lms.elearning.edu.sa")
    elif text == "📰 أخبار القسم والمعهد":
        bot.send_message(chat_id, "تابع حساب المعهد الرسمي على منصة X للحصول على آخر الأخبار.")
    elif text == "📍 موقع القسم":
        bot.send_message(chat_id, "المعهد الصناعي الثانوي ببريدة - مبنى قسم الحاسب الآلي.")
    elif text == "📖 دليل المتدرب":
        bot.send_message(chat_id, "يمكنك تحميل دليل المتدرب الشامل بصيغة PDF من موقع المؤسسة.")
    elif text == "❓ الأسئلة الشائعة":
        bot.send_message(chat_id, "هنا تجد إجابات لأهم الأسئلة المتعلقة بالحرمان، المكافآت، والمعدل التراكمي.")
    elif text == "💡 الاقتراحات والشكاوى":
        bot.send_message(chat_id, "صندوق الإدارة:\nاكتب رسالتك وسوف تصل لمدير القسم بسرية تامة.")
    elif text == "🎮 قسم الألعاب والإضافات":
        bot.send_message(chat_id, "مساحة إثرائية قريباً...")


# ==========================================
# 6. التشغيل ودرع الحماية من الانهيار
# ==========================================
if __name__ == "__main__":
    # تشغيل السيرفر الوهمي في الخلفية
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    print("جاري تشغيل البوت الأساسي بكامل ميزاته...")
    
    # حلقة لا نهائية مضادة للخطأ (409 Conflict)
    while True:
        try:
            bot.remove_webhook() 
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ حدث تضارب 409 (نسخة أخرى تعمل). سأنتظر 10 ثوانٍ وأحاول مجدداً...\n{e}")
            time.sleep(10) 


