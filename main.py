import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب سريع جداً (لإرضاء منصة Render فوراً) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")
    
    # إخفاء رسائل السيرفر المزعجة من السجلات
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"✅ Web server instantly started on port {port}")
    server.serve_forever()

# --- 2. كود بوت المعهد ---
# يتم سحب التوكن من إعدادات Render تلقائياً
TOKEN = os.environ.get("TOKEN") 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إنشاء قائمة الأزرار
    keyboard = [
        ["📍 موقع المعهد"],
        ["📊 استعلام عن نسبة الغياب"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "مرحباً بك في بوت المعهد! 🏢\nاختر من القائمة أدناه، أو أرسل **الرقم (ID)** مباشرة للبحث:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "📍 موقع المعهد":
        await update.message.reply_text(
            "📍 **موقع المعهد على خرائط جوجل:**\nhttps://maps.app.goo.gl/SgBNPgmNHKXager36"
        )
        return
        
    elif text == "📊 استعلام عن نسبة الغياب":
        await update.message.reply_text("الرجاء إرسال **الرقم (ID)** الآن للبحث:")
        return

    # البحث برقم المتدرب/المدرب
    try:
        df = pd.read_csv('data.csv', encoding='utf-8-sig')
        
        col_id = 'id'    
        col_absence = 'إجمالي نسبة الغياب ' # تنبيه: يوجد مسافة في نهاية الاسم هنا، تأكد أنها موجودة في ملف الإكسل
        col_name = 'name' 
        col_subject = 'اسم المقرر'
        
        df[col_id] = df[col_id].astype(str).str.strip()
        result = df[df[col_id] == text]
        
        if not result.empty:
            absence_rate = result.iloc[0][col_absence]
            person_name = result.iloc[0][col_name] 
            subject_name = result.iloc[0][col_subject]
            
            reply_message = f"👤 الاسم: {person_name}\n📚 المقرر: {subject_name}\n📊 إجمالي نسبة الغياب: {absence_rate}%"
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على هذا الرقم. تأكد من الرقم وحاول مجدداً."
            
    except FileNotFoundError:
        reply_message = "⚠️ النظام تحت الصيانة: ملف البيانات (data.csv) غير موجود."
    except Exception as e:
        reply_message = f"⚠️ حدث خطأ أثناء البحث، يرجى مراجعة الإدارة.\nالتفاصيل الفنية: {e}"

    await update.message.reply_text(reply_message)

def main():
    # 1. تشغيل السيرفر السريع في الخلفية أولاً (مهم جداً لـ Render)
    t = Thread(target=run_web_server)
    t.daemon = True 
    t.start()

    # 2. تشغيل البوت
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
