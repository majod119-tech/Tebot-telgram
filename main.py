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
        pass 

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. إعدادات البوت الأساسية ---
# تأكد من وضع التوكن في إعدادات Render باسم TOKEN أو استبدله هنا مباشرة
TOKEN = os.environ.get("TOKEN", "ضع_التوكن_هنا") 
GROUP_CHAT_ID = "-5193577198" 

# --- 3. دوال البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"],
        ["📅 التقويم التدريبي"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_text = "مرحباً بك في بوت قسم الحاسب! 🏢✨\nالرجاء اختيار الخدمة المطلوبة:"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # الردود النصية الثابتة
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 موقع القسم: http://maps.google.com")
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 منصة تقني: https://tvtclms.edu.sa\n🌐 بوابة رايات: https://tvtc.gov.sa")
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("الرجاء إرسال **رقمك التدريبي** الآن للبحث:")
    
    # منطق البحث في الإكسل (إذا كان النص المدخل أرقاماً)
    elif text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            # البحث عن الرقم التدريبي في عمود id
            result = df[df['id'].astype(str) == text]
            
            if not result.empty:
                student_name = result.iloc[0]['name']
                msg = f"👤 **الاسم:** {student_name}\n\n"
                for _, row in result.iterrows():
                    msg += f"📚 {row['c_nam']}: غياب {row['apsent']}%\n"
                await update.message.reply_text(msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ لم يتم العثور على هذا الرقم.")
        except Exception as e:
            await update.message.reply_text("⚠️ تأكد من وجود ملف data.xlsx وتطابق أسماء الأعمدة.")
            print(f"Error: {e}")

# --- دالة معالجة الملفات (الأعذار) التي كانت مكسورة ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    if not caption:
        await update.message.reply_text("⚠️ يرجى إعادة إرسال الملف مع كتابة **رقمك التدريبي** في الوصف (Caption).")
        return
    
    # إعادة توجيه الملف لمجموعة الأرشيف
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"📥 عذر جديد من المتدرب: {caption}")
    await update.message.copy(chat_id=GROUP_CHAT_ID)
    await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للقسم المختص.")

# --- 4. تشغيل البوت ---
def main():
    # تشغيل السيرفر في الخلفية
    Thread(target=run_web_server, daemon=True).start()

    # إعداد التطبيق
    app = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))

    print("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
