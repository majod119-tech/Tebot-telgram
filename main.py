import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب وهمي (لإبقاء تطبيق Render يعمل) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")
    def log_message(self, format, *args):
        pass # إخفاء سجلات السيرفر لتنظيف واجهة Render

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. إعدادات البوت الأساسية ---
TOKEN = os.environ.get("TOKEN", "ضع_التوكن_هنا") 
GROUP_CHAT_ID = "-5193577198" # ✅ رقم مجموعة الأرشيف

# --- 3. دوال البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"],
        ["📅 التقويم التدريبي"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "مرحباً بك في البوت (التجريبي) للقسم الحاسب في المعهد الصناعي الثانوي ببريدة! 🏢✨\n\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await update.message.reply_text(f"رقم هذه المجموعة (Chat ID) هو:\n`{chat_id}`", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع القسم على خرائط جوجل:**\nhttps://maps.app.goo.gl/Y8nQKrovHCfbukVh6?g_st=ic", parse_mode='Markdown')
        return
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 **الحقائب التدريبية:**\n(سيتم إضافة الرابط قريباً)", parse_mode='Markdown')
        return
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text(
            "🔗 **الروابط الهامة للمتدربين:**\n\n"
            "🌐 **منصة تقني:**\nhttps://tvtclms.edu.sa/?lang=ar\n\n"
            "🌐 **بوابة رايات:**\nhttps://tvtc.gov.sa/ar/Departments/tvtcdepartments/Rayat/pages/E-Services.aspx", 
            parse_mode='Markdown'
        )
        return
    elif text == "📅 التقويم التدريبي":
        await update.message.reply_text(
            "📅 **التقويم التدريبي:**\n\n"
            "يمكنك الاطلاع على التقويم التدريبي من خلال الرابط التالي:\n"
            "https://drive.google.com/file/d/1-Mc_IXwVLaye4BlNyCWdrd7twWSsAMez/view?usp=drivesdk", 
            parse_mode='Markdown'
        )
        return
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text(
            "📝 **لرفع العذر الطبي أو الرسمي:**\n\n"
            "الرجاء إرسال ملف العذر (صورة أو PDF)، **ومن الضروري جداً كتابة رقمك التدريبي في خانة الوصف (Caption)** قبل الضغط على زر الإرسال.", 
            parse_mode='Markdown'
        )
        return
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text("👨‍🏫 **للتواصل مع رئيس القسم:**\n\n📧 البريد الإلكتروني: aalmoshegh@tvtc.gov.sa", parse_mode='Markdown')
        return
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("الرجاء إرسال **رقم التعريف (ID)** الخاص بك الآن للبحث في سجلات الغياب:", parse_mode='Markdown')
        return

    # --- البحث في ملف الإكسل (تم التحديث لدعم data.xlsx) ---
    try:
        # قراءة ملف الإكسل بدلاً من CSV
        df = pd.read_excel('data.xlsx')
        
        # تنظيف أسماء الأعمدة لتجنب الأخطاء
        df.columns = df.columns.astype(str).str.strip() 
        col_id, col_name, col_subject, col_subject_num, col_absence = 'id', 'name', 'c_nam', 'c_number', 'apsent'
        
        # تحويل الرقم لنص للبحث الدقيق
        df[col_id] = df[col_id].astype(str).str.strip()
        
        # جلب كل الصفوف التي تطابق رقم الطالب
        result = df[df[col_id] == text]
        
        if not result.empty:
            student_name = result.iloc[0][col_name]
            reply_message = f"👤 **الاسم:** {student_name}\n\n👇 **تفاصيل الغياب للمواد المسجلة:**\n━━━━━━━━━━━━\n"
            
            for index, row in result.iterrows():
                sub_name = row[col_subject]
                sub_num = row[col_subject_num]
                abs_percent = row[col_absence]
                
                reply_message += (
                    f"📚 **{sub_name}** (رقم: {sub_num})\n"
                    f"⚠️ نسبة الغياب: {abs_percent}%\n"
                    f"───────────────\n"
                )
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على هذا الرقم. تأكد من صحة الرقم وحاول مجدداً."
            
    except Exception as e:
        reply_message = "⚠️ حدث خطأ أثناء البحث. تأكد من رفع ملف `data.xlsx` وأن الأعمدة مكتوبة بشكل صحيح."
        print(f"Error reading Excel: {e}")

    await update.message.reply_text(reply_message, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    caption = message.caption

    if message.chat.type != "private":
        return

    if not caption:
        await message.reply_text("⚠️ **خطأ
