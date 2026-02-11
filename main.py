import os
import telebot
import csv
import time
from telebot import types
from keep_alive import keep_alive

# ---------------------------------------------
# 🔐 إعدادات البوت
# ---------------------------------------------
# يمكنك وضع التوكن هنا مباشرة إذا لم يعمل معك الـ Secrets
# BOT_TOKEN = "ضع_التوكن_هنا"
BOT_TOKEN = os.environ.get('TOKEN')

bot = telebot.TeleBot(BOT_TOKEN)

# اسم الملف (سيبحث عنه تلقائياً)
def get_csv_filename():
    for filename in os.listdir('.'):
        if filename.endswith('.csv'):
            return filename
    return None

# ---------------------------------------------
# 🎨 القوائم والأزرار (التصميم الجديد)
# ---------------------------------------------

def main_menu():
    """القائمة الرئيسية الشاملة"""
    markup = types.InlineKeyboardMarkup(row_width=2)

    # الصف الأول: الخدمات الأساسية
    btn1 = types.InlineKeyboardButton("🔍 استعلام غياب", callback_data='check_absence')
    btn2 = types.InlineKeyboardButton("📅 جدول القسم", callback_data='schedule')

    # الصف الثاني: معلومات القسم
    btn3 = types.InlineKeyboardButton("📍 موقع القسم", callback_data='location')
    btn4 = types.InlineKeyboardButton("📩 رفع عذر طبي", callback_data='medical_excuse')

    # الصف الثالث: تواصل
    btn5 = types.InlineKeyboardButton("👨‍🏫 تواصل مع المشرف", url='https://t.me/username') # ضع معرف المشرف هنا

    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)
    return markup

def back_button():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu'))
    return markup

# ---------------------------------------------
# 🧠 المنطق والبحث (تم تحسين استخراج النسبة)
# ---------------------------------------------

def search_student(user_id):
    csv_file = get_csv_filename()
    if not csv_file:
        return "NO_FILE", []

    results = []
    student_name = "غير معروف"
    found = False

    try:
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # تنظيف أسماء الأعمدة (إزالة المسافات)
            clean_headers = {name.strip(): name for name in reader.fieldnames}

            # البحث الذكي عن عمود النسبة (أي عمود فيه كلمة "نسبة" أو "غياب")
            absence_col = None
            subject_col = None

            for header in clean_headers.keys():
                if "نسبة" in header or "غياب" in header:
                    absence_col = clean_headers[header]
                if "مقرر" in header or "مادة" in header:
                    subject_col = clean_headers[header]

            for row in reader:
                # تنظيف ID الطالب
                row_id = str(row.get('id', '')).strip().replace('.0', '')

                if row_id == user_id:
                    found = True
                    student_name = row.get('name', 'متدرب')

                    # جلب البيانات بالأعمدة التي اكتشفناها
                    subj = row.get(subject_col, 'مادة عامة') if subject_col else "مادة"
                    abs_val = row.get(absence_col, '0') if absence_col else "0"

                    # تنظيف النسبة من الرموز %
                    abs_val = str(abs_val).replace('%', '').strip()

                    try:
                        danger = float(abs_val) >= 20
                    except:
                        danger = False

                    results.append({'subject': subj, 'absence': abs_val, 'danger': danger})

        if found:
            return student_name, results
        else:
            return "NOT_FOUND", []

    except Exception as e:
        print(f"Error: {e}")
        return "ERROR", []

# ---------------------------------------------
# 🤖 استجابة البوت
# ---------------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = (
        "👋 **حياك الله في بوت قسم الحاسب الآلي**\n\n"
        "أنا هنا لمساعدتك في معرفة غيابك وجدولك وموقعنا.\n"
        "👇 **تفضل باختيار الخدمة:**"
    )
    bot.reply_to(message, welcome_msg, parse_mode='Markdown', reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if call.data == "main_menu":
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="👇 **القائمة الرئيسية:**", reply_markup=main_menu())

    # --- 1. استعلام الغياب ---
    elif call.data == "check_absence":
        msg = bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="🔢 **أرسل رقمك التدريبي الآن:**")
        bot.register_next_step_handler(msg, process_id)

    # --- 2. جدول القسم ---
    elif call.data == "schedule":
        # يمكنك هنا إرسال صورة الجدول إذا كانت لديك
        # bot.send_photo(chat_id, open('schedule.jpg', 'rb')) 
        schedule_text = (
            "📅 **جدول قسم الحاسب الآلي**\n\n"
            "يمكنك الاطلاع على الجدول المعلق في لوحة الإعلانات بالقسم.\n"
            "أو زيارة نظام رايات لمعرفة جدولك الشخصي."
        )
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=schedule_text, reply_markup=back_button())

    # --- 3. موقع القسم ---
    elif call.data == "location":
        location_text = (
            "📍 **موقع قسم الحاسب الآلي**\n\n"
            "🏢 **المبنى:** رقم 19\n"
            "🧭 **الجهة:** الشمالية\n"
            "📍 **الدور:** الثاني\n\n"
            "[اضغط هنا لفتح خرائط جوجل](https://maps.google.com/?q=College+of+Technology)"
        )
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=location_text, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=back_button())

    # --- 4. رفع عذر طبي ---
    elif call.data == "medical_excuse":
        excuse_text = (
            "📩 **طريقة رفع العذر الطبي:**\n\n"
            "1. تأكد أن العذر مصدق من 'منصة صحتي'.\n"
            "2. قم بتسليم النسخة الورقية لمشرف القسم.\n"
            "3. أو أرسل صورة العذر عبر الواتساب للمشرف.\n\n"
            "⚠️ **ملاحظة:** يجب تقديم العذر خلال 3 أيام من الغياب."
        )
        bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=excuse_text, reply_markup=back_button())

def process_id(message):
    user_id = message.text.strip()

    # زر الرجوع السريع في حال غير رأيه
    if not user_id.isdigit():
        bot.reply_to(message, "🔢 الرجاء إرسال أرقام فقط.", reply_markup=back_button())
        return

    name, data = search_student(user_id)

    if name == "NO_FILE":
        bot.reply_to(message, "⚠️ النظام تحت الصيانة (الملف غير موجود).", reply_markup=back_button())
    elif name == "NOT_FOUND":
        bot.reply_to(message, "❌ الرقم غير مسجل لدينا.", reply_markup=back_button())
    elif data:
        report = f"👤 **المتدرب:** {name}\n"
        report += "📊 **كشف الغياب:**\n"
        report += "ــــــــــــــــــــــــــــــ\n"
        for item in data:
            icon = "🚨" if item['danger'] else "✅"
            report += f"📚 {item['subject']}\n"
            report += f"   └ نسبة الغياب: {item['absence']}% {icon}\n"
        report += "ــــــــــــــــــــــــــــــ\n"
        report += "🚨 **تجاوز 20% يعني الحرمان**"

        bot.reply_to(message, report, reply_markup=back_button())
    else:
         bot.reply_to(message, "⚠️ حدث خطأ غير متوقع.", reply_markup=back_button())

# ---------------------------------------------
# تشغيل البوت
# ---------------------------------------------
print("✅ البوت يعمل بنجاح...")
keep_alive()
bot.infinity_polling()
