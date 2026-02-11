import os
import json 
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 1. سيرفر ويب سريع (لإبقاء البوت متيقظاً على Render) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")
    
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. إعدادات جوجل درايف ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = '1kGXVJboQ5eKYt6UcsL6QT_fLiPjxdlux' # تم إضافة أيدي المجلد بنجاح ✅

def upload_to_drive(file_path, file_name):
    google_creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if not google_creds_json:
        raise Exception("لم يتم العثور على مفتاح جوجل في إعدادات Render!")
        
    creds_dict = json.loads(google_creds_json)
    
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 3. كود البوت ---
TOKEN = os.environ.get("TOKEN") 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "مرحباً بك في البوت الرسمي للقسم! 🏢✨\n\n"
        "نحن هنا لخدمتك وتسهيل وصولك للمعلومات.\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع القسم على خرائط جوجل:**\nhttps://maps.app.goo.gl/Y8nQKrovHCfbukVh6?g_st=ic")
        return
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 **الحقائب التدريبية:**\n(سيتم إضافة الرابط قريباً)")
        return
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text(
            "🔗 **الروابط الهامة للمتدربين:**\n\n"
            "🌐 **منصة تقني:**\nhttps://tvtclms.edu.sa/?lang=ar\n\n"
            "🌐 **بوابة رايات:**\nhttps://tvtc.gov.sa/ar/Departments/tvtcdepartments/Rayat/pages/E-Services.aspx"
        )
        return
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text(
            "📝 **لرفع العذر الطبي أو الرسمي:**\n\n"
            "الرجاء إرسال ملف العذر (صورة أو PDF)، **ومن الضروري جداً كتابة رقمك التدريبي في خانة الوصف (Caption)** قبل الضغط على زر الإرسال، ليتم حفظه باسمك."
        )
        return
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text("👨‍🏫 **للتواصل مع رئيس القسم:**\n\n📧 البريد الإلكتروني: aalmoshegh@tvtc.gov.sa")
        return
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("الرجاء إرسال **رقم التعريف (ID)** الخاص بك الآن للبحث في سجلات الغياب:")
        return

    # --- البحث في الإكسل ---
    try:
        df = pd.read_csv('data.csv', sep=';', encoding='utf-8-sig')
        df.columns = df.columns.str.strip() 
        
        col_id = 'id'    
        col_name = 'name' 
        col_subject = 'c_nam'
        col_subject_num = 'c_number'
        col_absence = 'apsent'
        
        df[col_id] = df[col_id].astype(str).str.strip()
        result = df[df[col_id] == text]
        
        if not result.empty:
            person_name = result.iloc[0][col_name] 
            subject_name = result.iloc[0][col_subject]
            subject_num = result.iloc[0][col_subject_num]
            absence_rate = result.iloc[0][col_absence]
            
            reply_message = (
                f"👤 **الاسم:** {person_name}\n"
                f"📚 **المادة:** {subject_name} (رقم: {subject_num})\n"
                f"📊 **نسبة الغياب:** {absence_rate}%"
            )
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على هذا الرقم. تأكد من صحة الرقم وحاول مجدداً."
    except Exception as e:
        reply_message = f"⚠️ حدث خطأ أثناء البحث. التفاصيل: {e}"

    await update.message.reply_text(reply_message)

# --- 4. دالة استقبال الملفات ورفعها لدرايف ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    caption = message.caption

    # التحقق من وجود رقم المتدرب في الوصف
    if not caption:
        await message.reply_text("⚠️ **خطأ:** لم تقم بكتابة رقمك التدريبي! الرجاء إعادة إرسال الملف أو الصورة وكتابة رقمك في خانة الوصف (Caption).")
        return

    student_id = caption.strip()
    
    # رسالة انتظار
    await message.reply_text("⏳ جاري رفع العذر إلى نظام القسم، يرجى الانتظار...")

    try:
        if message.document:
            file_obj = await message.document.get_file()
            extension = message.document.file_name.split('.')[-1]
            file_name = f"{student_id}_excuse.{extension}"
        elif message.photo:
            file_obj = await message.photo[-1].get_file()
            file_name = f"{student_id}_excuse.jpg"
        else:
            return

        local_path = file_name
        await file_obj.download_to_drive(local_path)

        # رفعه إلى جوجل درايف
        upload_to_drive(local_path, file_name)
        
        # حذف الملف من السيرفر
        os.remove(local_path)
        
        await message.reply_text("✅ **تم رفع العذر بنجاح!**\nتم تحويله إلى إدارة القسم للمراجعة.")
    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ أثناء الرفع: {e}")

def main():
    t = Thread(target=run_web_server)
    t.daemon = True 
    t.start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
