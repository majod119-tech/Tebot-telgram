import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب وهمي (Keep-Alive لـ Render) ---
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
# تأكد من وضع التوكن الجديد في إعدادات Render باسم TOKEN
TOKEN = os.environ.get("TOKEN", "ضع_التوكن_هنا") 
GROUP_ID = "-5193577198" 
TELEGRAM_CONTACT_LINK = "https://t.me/majod119" # حسابك الشخصي للتواصل

# --- 3. تصميم لوحات المفاتيح (القوائم) ---

def get_main_menu():
    keyboard = [
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)

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
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"مرحباً بك يا {name} في بوت قسم الحاسب 💻✨\n\n"
        "القائمة الرئيسية دائماً متاحة لك بالأسفل 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # نظام التنقل والرجوع
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # الدخول لقسم الخطط التدريبية
    if text == "📄 الخطط التدريبية":
        await update.message.reply_text(
            "📄 **قسم الخطط التدريبية**\n\nاختر التخصص المطلوب لعرض الخطة 👇",
            reply_markup=get_plans_menu(),
            parse_mode='Markdown'
        )
        return

    # استجابات الخطط (روابط افتراضية)
    plans = {
        "🖥️ خطة الدعم الفني": "📍 [رابط خطة الدعم الفني]",
        "🌐 خطة الشبكات": "📍 [رابط خطة الشبكات]",
        "💻 خطة البرمجيات": "📍 [رابط خطة البرمجيات]"
    }
    if text in plans:
        await update.message.reply_text(f"✅ **{text}:**\n\n{plans[text]}", parse_mode='Markdown')
        return

    # الأقسام الأخرى
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 [موقع قسم الحاسب على الخريطة](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
    elif text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 [رابط الحقائب التدريبية](https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL)", reply_markup=get_back_menu())
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 [منصة تقني](https://tvtclms.edu.sa)\n🌐 [بوابة رايات](https://rayat.tvtc.gov.sa)", reply_markup=get_back_menu(), parse_mode='Markdown')
    elif text == "📅 التقويم التدريبي":
        photo_path = 'calendar.jpg' # الاسم الجديد للملف
        if os.path.exists(photo_path):
            await update.message.reply_photo(photo=open(photo_path, 'rb'), caption="📅 التقويم التدريبي المعتمد", reply_markup=get_back_menu())
        else:
            await update.message.reply_text("⚠️ ملف التقويم `calendar.jpg` غير موجود.", reply_markup=get_back_menu())
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل **رقمك التدريبي** الآن للبحث..", reply_markup=get_back_menu())
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 أرسل صورة العذر واكتب رقمك في الوصف.", reply_markup=get_back_menu())
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        contact_text = f"👨‍🏫 **للتواصل المباشر والخاص:**\n\n🔗 {TELEGRAM_CONTACT_LINK}"
        await update.message.reply_text(contact_text, reply_markup=get_back_menu(), parse_mode='Markdown')

    # البحث عن الغياب (رقم تدريبي)
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
                    # توزيع الألوان حسب النسب الجديدة (20% حرمان)
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ قريب من الحرمان" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 **{row[c_sub]}**\n  └ نسبة الغياب: %{val} ⇦ {icon}\n───────────────\n"
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ الرقم غير مسجل.", reply_markup=get_back_menu())
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text("⚠️ خطأ فني في قراءة البيانات.")

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ أرسل الرقم في الوصف.")
        return
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد: {update.message.caption}")
    await update.message.copy(chat_id=GROUP_ID)
    await update.message.reply_text("✅ تم الاستلام.", reply_markup=get_main_menu())

# --- 5. التشغيل النهائي ---
def main():
    # تشغيل سيرفر الويب
    Thread(target=run_web_server, daemon=True).start()
    
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))

    print("🚀 جاري تشغيل البوت ومعالجة التضارب...")
    # الحل السحري لمشكلة Conflict: حذف التحديثات المعلقة عند البدء
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
