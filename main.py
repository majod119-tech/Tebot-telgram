import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب سريع ---
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

# --- 2. كود البوت ---
TOKEN = os.environ.get("TOKEN") 
# ✅ تم إضافة رقم مجموعة القسم بنجاح!
GROUP_CHAT_ID = "-5193577198" 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "مرحباً بك في البوت الرسمي لقسم الحاسب الالي في المعهد الثانوي الصناعي ببريده! 🏢✨\n\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await update.message.reply_text(f"رقم هذه المجموعة (Chat ID) هو:\n`{chat_id}`")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع قسم الحاسب مبنى 19 على خرائط جوجل:**\nhttps://maps.app.goo.gl/Y8nQKrovHCfbukVh6?g_st=ic")
        return
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 **الحقائب التدريبية:**\n(https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL)")
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
            "الرجاء إرسال ملف العذر (صورة أو PDF)، **ومن الضروري جداً كتابة رقمك التدريبي في خانة الوصف (Caption)** قبل الضغط على زر الإرسال."
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
        col_id, col_name, col_subject, col_subject_num, col_absence = 'id', 'name', 'c_nam', 'c_number', 'apsent'
        df[col_id] = df[col_id].astype(str).str.strip()
        result = df[df[col_id] == text]
        
        if not result.empty:
            reply_message = (f"👤 **الاسم:** {result.iloc[0][col_name]}\n📚 **المادة:** {result.iloc[0][col_subject]} (رقم: {result.iloc[0][col_subject_num]})\n📊 **نسبة الغياب:** {result.iloc[0][col_absence]}%")
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على هذا الرقم. تأكد من صحة الرقم وحاول مجدداً."
    except Exception as e:
        reply_message = "⚠️ حدث خطأ أثناء البحث، يرجى المحاولة لاحقاً."

    await update.message.reply_text(reply_message)

# --- دالة استقبال الملفات ورفعها للمجموعة ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    caption = message.caption

    # إذا كان الملف مرسل داخل مجموعة (نتجاهله لتجنب التكرار)
    if message.chat.type != "private":
        return

    if not caption:
        await message.reply_text("⚠️ **خطأ:** لم تقم بكتابة رقمك التدريبي! الرجاء إعادة إرسال العذر وكتابة رقمك في الوصف.")
        return

    student_id = caption.strip()
    await message.reply_text("⏳ جاري رفع العذر إلى نظام القسم...")

    try:
        # رسالة تذهب للإدارة (مجموعة الأرشيف)
        admin_text = f"📄 **عذر جديد!**\n👤 رقم المتدرب: {student_id}"

        # إرسال العذر للمجموعة
        if message.document:
            await context.bot.send_document(chat_id=GROUP_CHAT_ID, document=message.document.file_id, caption=admin_text)
        elif message.photo:
            await context.bot.send_photo(chat_id=GROUP_CHAT_ID, photo=message.photo[-1].file_id, caption=admin_text)
        
        await message.reply_text("✅ **تم رفع العذر بنجاح!**\nتم تحويله إلى إدارة القسم للمراجعة.")
    except Exception as e:
        await message.reply_text("❌ عذراً، لم أتمكن من رفع الملف، يرجى التأكد من إعدادات البوت في المجموعة.")

def main():
    t = Thread(target=run_web_server)
    t.daemon = True 
    t.start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", get_id))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
