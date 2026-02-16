import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# --- 3. لوحات المفاتيح (Keyboards) ---
def main_menu_keyboard():
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"],
        ["📅 التقويم التدريبي"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. دوال البوت المحسنة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"مرحباً بك يا {user_name} في نظام الرد الآلي 🤖\n"
        "الخاص بـ **قسم الحاسب الآلي** 🏢\n\n"
        "الرجاء اختيار الخدمة المطلوبة من القائمة أدناه 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # التعامل مع زر الرجوع
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("تمت العودة للقائمة الرئيسية 🏠", reply_markup=main_menu_keyboard())
        return

    # الردود الثابتة مع إضافة زر الرجوع
    if text == "📍 موقع القسم":
        await update.message.reply_text(
            "📍 **موقع القسم (المبنى الرئيسي):**\n"
            "يمكنك الوصول إلينا عبر الرابط:\n"
            "http://googleusercontent.com/maps.google.com/4",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text(
            "🌐 **روابط تهمك:**\n\n"
            "🔹 منصة تقني (Blackboard):\nhttps://tvtclms.edu.sa\n\n"
            "🔹 بوابة رايات (الخدمات الذاتية):\nhttps://rayat.tvtc.gov.sa",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text(
            "🔎 **خدمة استعلام الغياب:**\n"
            "فضلاً، أرسل (الرقم التدريبي) الخاص بك الآن.",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )
    elif text == "📅 التقويم التدريبي":
        await update.message.reply_text(
            "📅 **التقويم التدريبي العام:**\n"
            "اضغط على الرابط للمشاهدة أو التحميل:\n"
            "https://drive.google.com/file/d/1-Mc_IXwVLaye4BlNyCWdrd7twWSsAMez/view",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text(
            "📝 **تعليمات رفع الأعذار:**\n\n"
            "1️⃣ قم بإرفاق صورة العذر الطبي أو الرسمي.\n"
            "2️⃣ اكتب (رقمك التدريبي) في 'وصف الصورة'.\n"
            "3️⃣ سيتم مراجعة طلبك وإفادتك قريباً.",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text(
            "👨‍🏫 **رئيس قسم الحاسب:**\n\n"
            "✉️ البريد الإلكتروني:\n`aalmoshegh@tvtc.gov.sa`",
            reply_markup=back_keyboard(), parse_mode='Markdown'
        )

    # منطق البحث في الإكسل (عند إرسال الرقم التدريبي)
    elif text.isdigit():
        searching_msg = await update.message.reply_text("⏳ جاري البحث في السجلات...")
        try:
            if not os.path.exists('data.xlsx'):
                await searching_msg.edit_text("⚠️ خطأ: ملف البيانات مفقود.")
                return

            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()

            # الأعمدة حسب صورتك
            col_id, col_name, col_subject, col_abs = 'stu_num', 'stu_nam', 'c_nam', 'parsnt'
            
            df[col_id] = df[col_id].astype(str).str.strip()
            result = df[df[col_id] == text]
            
            if not result.empty:
                student_name = result.iloc[0][col_name]
                msg = f"✅ **تم العثور على البيانات:**\n\n"
                msg += f"👤 **المتدرب:** `{student_name}`\n"
                msg += f"🆔 **الرقم:** `{text}`\n"
                msg += "━━━━━━━━━━━━━━\n"
                
                for _, row in result.iterrows():
                    abs_val = row[col_abs]
                    status = "🔴 حرمان" if float(abs_val) >= 15 else "🟢 منتظم"
                    msg += f"📖 **{row[col_subject]}**\n"
                    msg += f"  └ نسبة الغياب: %{abs_val} ⇦ {status}\n"
                    msg += "───────────────\n"
                
                await searching_msg.edit_text(msg, parse_mode='Markdown', reply_markup=back_keyboard())
            else:
                await searching_msg.edit_text("❌ عذراً، الرقم التدريبي غير مسجل لدينا.", reply_markup=back_keyboard())
        except Exception as e:
            await searching_msg.edit_text(f"⚠️ خطأ أثناء المعالجة: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    if not caption:
        await update.message.reply_text("⚠️ يرجى إرسال الصورة مع كتابة رقمك التدريبي في الوصف.")
        return
    
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"📥 **عذر جديد مستلم:**\n🆔 الرقم المرفق: {caption}")
    await update.message.copy(chat_id=GROUP_CHAT_ID)
    await update.message.reply_text("✅ تم استلام ملفك بنجاح وسيتم إشعارك بالنتيجة.", reply_markup=main_menu_keyboard())

# --- 5. تشغيل البوت ---
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
