import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب وهمي لـ Render (لمنع إغلاق البوت) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running perfectly!")
    def log_message(self, format, *args): pass 

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات ---
TOKEN = os.environ.get("TOKEN") # يتم جلبه من إعدادات Render
GROUP_ID = "-5193577198"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"

# --- 3. تصميم القوائم (لوحات المفاتيح) ---
def get_main_menu():
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_plans_menu():
    keyboard = [
        ["🖥️ خطة الدعم الفني", "🌐 خطة الشبكات"],
        ["💻 خطة البرمجيات"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"أهلاً بك {update.effective_user.first_name} في بوت قسم الحاسب 💻✨\nاختر من القائمة أدناه 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 قسم الخطط:\nاختر التخصص المطلوب 👇", reply_markup=get_plans_menu())
        return

    # الروابط والأقسام الأخرى
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 [موقع القسم](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 [الحقائب التدريبية](https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL)", reply_markup=get_back_menu())
    elif text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'):
            await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption="📅 التقويم المعتمد", reply_markup=get_back_menu())
        else:
            await update.message.reply_text("⚠️ ملف التقويم مفقود.", reply_markup=get_back_menu())
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text(f"👨‍🏫 للتواصل المباشر:\n🔗 {TELEGRAM_CONTACT_LINK}", reply_markup=get_back_menu())

    # استعلام الغياب (20% حرمان / 15% تنبيه)
    elif text.isdigit():
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            if not result.empty:
                name = result.iloc[0]['stu_nam']
                msg = f"✅ النتائج لـ: `{name}`\n━━━━━━━━━━━━━━\n"
                for _, row in result.iterrows():
                    val = float(row['parsnt'])
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ تنبيه" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 {row['c_nam']}: %{val} {icon}\n"
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ الرقم غير موجود في السجلات.", reply_markup=get_back_menu())
        except Exception as e:
            print(f"Error reading excel: {e}")
            await update.message.reply_text("⚠️ خطأ في قراءة ملف السجلات `data.xlsx`.")

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ الرجاء كتابة الرقم التدريبي في الوصف (Caption) عند إرفاق الصورة.")
        return
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد من: {update.message.caption}")
    await update.message.copy(chat_id=GROUP_ID)
    await update.message.reply_text("✅ تم استلام العذر.", reply_markup=get_main_menu())

# --- 5. التشغيل القياسي الآمن ---
def main():
    # 1. تشغيل السيرفر الوهمي في مسار جانبي
    Thread(target=run_web_server, daemon=True).start()
    
    # 2. بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # 3. ربط المهام
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    # 4. تشغيل البوت مع طرد أي تحديثات قديمة
    print("🚀 جاري بدء تشغيل البوت...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
