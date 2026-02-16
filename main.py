import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب وهمي لـ Render ---
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

# --- 2. إعدادات البوت ---
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
    welcome_text = "مرحباً بك في بوت قسم الحاسب! 🏢✨\nالرجاء اختيار الخدمة المطلوبة من القائمة:"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # خيارات القائمة
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 موقع القسم: http://maps.google.com")
        return
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 منصة تقني: https://tvtclms.edu.sa\n🌐 بوابة رايات: https://tvtc.gov.sa")
        return
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("الرجاء إرسال **رقمك التدريبي** الآن للبحث:")
        return
    elif text == "📅 التقويم التدريبي":
        await update.message.reply_text("📅 رابط التقويم: https://drive.google.com/file/d/1-Mc_IXwVLaye4BlNyCWdrd7twWSsAMez/view")
        return

    # البحث في الإكسل عند إرسال الرقم التدريبي
    if text.isdigit():
        try:
            if not os.path.exists('data.xlsx'):
                await update.message.reply_text("⚠️ ملف البيانات `data.xlsx` غير موجود.")
                return

            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()

            # التعديل هنا: استخدام المسميات من صورتك
            col_id = 'stu_num'   
            col_name = 'stu_nam' 
            col_subject = 'c_nam' 
            col_abs = 'parsnt'    
            
            # البحث عن المتدرب
            df[col_id] = df[col_id].astype(str).str.strip()
            result = df[df[col_id] == text]
            
            if not result.empty:
                student_name = result.iloc[0][col_name]
                msg = f"👤 **الاسم:** {student_name}\n"
                msg += f"🆔 **الرقم:** {text}\n"
                msg += "━━━━━━━━━━━━\n"
                
                for _, row in result.iterrows():
                    abs_val = row[col_abs]
                    # تنبيه الحرمان (15% فأكثر)
                    status = " 🔴 (حرمان)" if float(abs_val) >= 15 else " ✅"
                    msg += f"📚 {row[col_subject]}: {abs_val}%{status}\n"
                    msg += "───────────────\n"
                
                await update.message.reply_text(msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ لم يتم العثور على هذا الرقم التدريبي.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ خطأ فني: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    if not caption:
        await update.message.reply_text("⚠️ يرجى إعادة إرسال الملف مع كتابة **رقمك التدريبي** في الوصف.")
        return
    
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"📥 عذر جديد: {caption}")
    await update.message.copy(chat_id=GROUP_CHAT_ID)
    await update.message.reply_text("✅ تم استلام عذرك بنجاح.")

# --- 4. تشغيل البوت ---
def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
