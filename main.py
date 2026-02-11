import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب سريع (لإبقاء البوت متيقظاً على Render) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")
    
    def log_message(self, format, *args):
        pass # إخفاء رسائل السيرفر المزعجة

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. كود البوت ---
TOKEN = os.environ.get("TOKEN") 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إنشاء قائمة الأزرار الجديدة (زرين في كل سطر لشكل أنيق)
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # رسالة الترحيب الجديدة بالقسم
    welcome_text = (
        "مرحباً بك في البوت الرسمي للقسم! 🏢✨\n\n"
        "نحن هنا لخدمتك وتسهيل وصولك للمعلومات.\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇\n\n"
        "*(للاستعلام عن الغياب مباشرة، فقط أرسل رقمك التدريبي/الجامعي)*"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # --- التعامل مع الأزرار ---
    
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع القسم على خرائط جوجل:**\nhttps://maps.app.goo.gl/Y8nQKrovHCfbukVh6?g_st=ic")
        return
        
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 **الحقائب التدريبية:**\n(سيتم إضافة الرابط قريباً)")
        return
        
    elif text == "🔗 منصة تقني ورايات":
        # تم تنسيق الروابط لتكون واضحة وقابلة للضغط بسهولة
        await update.message.reply_text(
            "🔗 **الروابط الهامة للمتدربين:**\n\n"
            "🌐 **منصة تقني:**\n"
            "https://tvtclms.edu.sa/?lang=ar\n\n"
            "🌐 **بوابة رايات:**\n"
            "https://tvtc.gov.sa/ar/Departments/tvtcdepartments/Rayat/pages/E-Services.aspx"
        )
        return
        
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **لرفع الأعذار الطبية والرسمية:**\n(سيتم إضافة الرابط قريباً)")
        return
        
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text("👨‍🏫 **للتواصل مع رئيس القسم:**\n\n📧 البريد الإلكتروني: aalmoshegh@tvtc.gov.sa")
        return

    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("الرجاء إرسال **رقم التعريف (ID)** الخاص بك الآن للبحث في سجلات الغياب:")
        return

    # --- البحث في ملف البيانات بالرقم ---
    try:
        # ⚠️ تم إضافة sep=';' هنا لكي يقرأ ملفك بشكل صحيح
        df = pd.read_csv('data.csv', sep=';', encoding='utf-8-sig')
        
        # أسماء الأعمدة 
        col_id = 'id'    
        col_name = 'name' 
        col_subject = 'c_nam'
        col_subject_num = 'c_number'
        col_absence = 'apsent'
        
        # تحويل عمود id إلى نص وتنظيفه لضمان دقة البحث
        df[col_id] = df[col_id].astype(str).str.strip()
        result = df[df[col_id] == text]
        
        if not result.empty:
            person_name = result.iloc[0][col_name] 
            subject_name = result.iloc[0][col_subject]
            subject_num = result.iloc[0][col_subject_num]
            absence_rate = result.iloc[0][col_absence]
            
            # ترتيب الرسالة التي ستصل للمتدرب
            reply_message = (
                f"👤 **الاسم:** {person_name}\n"
                f"📚 **المادة:** {subject_name} (رقم: {subject_num})\n"
                f"📊 **نسبة الغياب:** {absence_rate}%"
            )
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على هذا الرقم. تأكد من صحة الرقم وحاول مجدداً."
            
    except FileNotFoundError:
        reply_message = "⚠️ النظام تحت الصيانة: ملف البيانات غير موجود."
    except KeyError as e:
        reply_message = f"⚠️ خطأ في قراءة الملف: العمود {e} غير موجود. يرجى مراجعة الإدارة."
    except Exception as e:
        reply_message = f"⚠️ حدث خطأ أثناء البحث.\nالتفاصيل الفنية: {e}"

    await update.message.reply_text(reply_message)

def main():
    # 1. تشغيل السيرفر في الخلفية
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
