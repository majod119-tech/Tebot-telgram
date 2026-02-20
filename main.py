import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر الويب (يمنع توقف البوت) ---
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
TOKEN = os.environ.get("TOKEN") # يجلب التوكن من Render
GROUP_ID = "-5193577198"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"

# --- 3. تصميم القوائم ---
def get_main_menu():
    keyboard = [
        ["📰 أخبار القسم والمعهد"], 
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

    # --- 1. أزرار التنقل ---
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 قسم الخطط:\nاختر التخصص المطلوب 👇", reply_markup=get_plans_menu())
        return

    # --- 2. قسم الأخبار المحدث ---
    if text == "📰 أخبار القسم والمعهد":
        news_msg = (
            "📰 **أحدث إعلانات القسم والمعهد:**\n\n"
            "🔔 **إعلان هام:**\n"
            "🔸 *الأسبوع القادم (الأسبوع 6 و 7) سيكون موعداً لاختبارات الفترة الأولى. نتمنى لجميع المتدربين التوفيق والنجاح.*\n\n"
            "📱 **حساب المعهد الصناعي الثانوي ببريدة على منصة X:**\n"
            "🔗 [اضغط هنا لزيارة حساب المعهد](https://x.com/tvtc_m_buraidah?s=21)\n\n"
            "*(تنبيه: سيتم تحديث الأخبار هنا بشكل دوري)*"
        )
        await update.message.reply_text(news_msg, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    # --- 3. الخطط الفرعية ---
    plans = {
        "🖥️ خطة الدعم الفني": "📍 [رابط خطة الدعم الفني هنا]",
        "🌐 خطة الشبكات": "📍 [رابط خطة الشبكات هنا]",
        "💻 خطة البرمجيات": "📍 [رابط خطة البرمجيات هنا]"
    }
    if text in plans:
        await update.message.reply_text(f"✅ **{text}:**\n\n{plans[text]}", parse_mode='Markdown')
        return

    # --- 4. الروابط والأقسام الثابتة ---
    if text == "🔗 منصة تقني ورايات":
        msg = "🌐 **أهم الروابط التدريبية:**\n\n🔹 منصة تقني:\nhttps://tvtclms.edu.sa\n\n🔹 بوابة رايات:\nhttps://rayat.tvtc.gov.sa"
        await update.message.reply_text(msg, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 [موقع القسم على الخريطة](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
        return
    
    if text == "📚 الحقائب التدريبية":
        await update.message.reply_text("📚 [رابط الحقائب التدريبية المعتمدة](https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL)", reply_markup=get_back_menu(), parse_mode='Markdown')
        return
    
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'):
            await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption="📅 التقويم المعتمد", reply_markup=get_back_menu())
        else:
            await update.message.reply_text("⚠️ ملف التقويم `calendar.jpg` مفقود من السيرفر.", reply_markup=get_back_menu())
        return
    
    if text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text(f"👨‍🏫 للتواصل المباشر والخاص:\n🔗 {TELEGRAM_CONTACT_LINK}", reply_markup=get_back_menu())
        return

    # --- 5. خدمات الغياب والأعذار ---
    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل **رقمك التدريبي** الآن للبحث في السجلات..", reply_markup=get_back_menu())
        return

    if text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **تعليمات هامة:**\nأرسل صورة العذر واكتب رقمك التدريبي في خانة (الوصف / Caption).", reply_markup=get_back_menu())
        return

    # --- 6. منطق البحث في الإكسل ---
    if text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري البحث...")
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            await status_msg.delete()
            
            if not result.empty:
                name = result.iloc[0]['stu_nam']
                msg = f"✅ <b>النتائج لـ:</b> <code>{name}</code>\n━━━━━━━━━━━━━━\n"
                for _, row in result.iterrows():
                    val = float(row['parsnt'])
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ تنبيه" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 {row['c_nam']}: %{val} {icon}\n"
                await update.message.reply_text(msg, parse_mode='HTML', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ عذراً، الرقم التدريبي غير مسجل لدينا.", reply_markup=get_back_menu())
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            print(f"Excel Error: {e}")
            await update.message.reply_text("⚠️ حدث خطأ أثناء قراءة ملف `data.xlsx`. تأكد من سلامة الملف.", reply_markup=get_back_menu())
        return

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ عذراً، يجب كتابة (رقمك التدريبي) في وصف الصورة قبل الإرسال.", reply_markup=get_back_menu())
        return
    
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد:\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للمسؤول.", reply_markup=get_main_menu())
    except Exception as e:
        print(f"Group Error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ. تأكد أن البوت مضاف كمشرف (Admin) في مجموعة الأرشيف.", reply_markup=get_main_menu())

# --- 7. التشغيل ---
def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تم تشغيل البوت بكل ميزاته بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
