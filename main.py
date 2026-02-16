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
    def log_message(self, format, *args): pass 

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات الأساسية ---
TOKEN = os.environ.get("TOKEN", "ضع_التوكن_هنا")
GROUP_ID = "-5193577198"

# --- 3. لوحات المفاتيح المحسنة ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ], resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. معالجة الرسائل والمنطق ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"مرحباً بك يا {name} في بوت قسم الحاسب الآلي 🤖💻\n\n"
        "نسعد بخدمتك، فضلاً اختر من القائمة أدناه 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # الأقسام الثابتة والروابط
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع قسم الحاسب:**\n[اضغط هنا للوصول عبر الخرائط](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
    
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 **أهم الروابط التدريبية:**\n\n🔹 [منصة تقني (Blackboard)](https://tvtclms.edu.sa)\n🔹 [بوابة رايات](https://rayat.tvtc.gov.sa)", reply_markup=get_back_menu(), parse_mode='Markdown')
    
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 **رابط الحقائب التدريبية:**\nhttps://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL", reply_markup=get_back_menu())

    elif text == "📄 الخطط التدريبية":
        # يمكنك تعديل هذه الروابط لتناسب تخصصات القسم لديك
        plan_text = (
            "📄 **الخطط التدريبية للفصل الحالي:**\n\n"
            "يرجى اختيار التخصص المناسب للاطلاع على الخطة:\n\n"
            "🔹 **تخصص الدعم الفني:** [رابط الخطة]\n"
            "🔹 **تخصص الشبكات:** [رابط الخطة]\n"
            "🔹 **تخصص البرمجيات:** [رابط الخطة]\n\n"
            "⚠️ *ملاحظة: تأكد من مراجعة مرشدك الأكاديمي في حال وجود استفسار.*"
        )
        await update.message.reply_text(plan_text, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
    
    elif text == "📅 التقويم التدريبي":
        photo_path = 'calendar.jpg'
        if os.path.exists(photo_path):
            await update.message.reply_photo(photo=open(photo_path, 'rb'), caption="📅 **التقويم التدريبي للفصل الحالي**", reply_markup=get_back_menu())
        else:
            await update.message.reply_text("⚠️ عذراً، لم يتم العثور على ملف `calendar.jpg`.", reply_markup=get_back_menu())
    
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 فضلاً أرسل **رقمك التدريبي** الآن للبحث..", reply_markup=get_back_menu())
    
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **تعليمات:** أرسل صورة العذر واكتب رقمك التدريبي في الوصف.", reply_markup=get_back_menu())
    
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text("👨‍🏫 **رئيس القسم:**\n✉️ `aalmoshegh@tvtc.gov.sa`", reply_markup=get_back_menu(), parse_mode='Markdown')

    # --- منطق البحث في الإكسل ---
    elif text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري فحص السجلات...")
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            c_id, c_name, c_sub, c_abs = 'stu_num', 'stu_nam', 'c_nam', 'parsnt'
            df[c_id] = df[c_id].astype(str).str.strip()
            result = df[df[c_id] == text]
            await status_msg.delete()

            if not result.empty:
                s_name = result.iloc[0][c_name]
                msg = f"✅ **النتائج لـ:** `{s_name}`\n━━━━━━━━━━━━━━\n"
                for _, row in result.iterrows():
                    val = float(row[c_abs])
                    # منطق النسب الجديد (20% حرمان)
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ تنبيه" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 **{row[c_sub]}**: %{val} {icon}\n"
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ الرقم غير مسجل.", reply_markup=get_back_menu())
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text("⚠️ خطأ فني أثناء قراءة البيانات.")

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ أرسل الرقم التدريبي في الوصف.")
        return
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد: {update.message.caption}")
    await update.message.copy(chat_id=GROUP_ID)
    await update.message.reply_text("✅ تم الاستلام.", reply_markup=get_main_menu())

# --- 5. التشغيل النهائي ---
def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.run_polling()

if __name__ == '__main__':
    main()
