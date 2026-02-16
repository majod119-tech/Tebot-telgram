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
TOKEN = os.environ.get("TOKEN", "ضع_التوكن_هنا") 
GROUP_ID = "-5193577198" 

# --- 3. لوحات المفاتيح (Keyboards) ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"],
        ["📅 التقويم التدريبي"]
    ], resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. المهام المنطقية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"مرحباً بك يا {name} في بوت قسم الحاسب 💻✨\n\n"
        "يسعدنا خدمتك، اختر من القائمة أدناه 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # التنقل بين القوائم
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # الأقسام الثابتة
    responses = {
        "📍 موقع القسم": "📍 **موقع قسم الحاسب:**\n[اضغط هنا للوصول](http://maps.google.com/?q=Buraydah)",
        "🔗 منصة تقني ورايات": "🌐 **أهم الروابط:**\n\n🔹 [منصة تقني](https://tvtclms.edu.sa)\n🔹 [بوابة رايات](https://rayat.tvtc.gov.sa)",
        "📅 التقويم التدريبي": "📅 **التقويم التدريبي:**\n[تحميل التقويم من هنا](https://drive.google.com/file/d/1-Mc_IXwVLaye4BlNyCWdrd7twWSsAMez/view)",
        "📊 استعلام الغياب": "🔎 فضلاً أرسل **رقمك التدريبي** الآن للبحث..",
        "📝 رفع الغياب والأعذار": "📝 **تعليمات:** أرسل صورة العذر مع كتابة رقمك التدريبي في الوصف.",
        "👨‍🏫 تواصل مع رئيس القسم": "👨‍🏫 **رئيس القسم:**\n✉️ `aalmoshegh@tvtc.gov.sa`"
    }

    if text in responses:
        await update.message.reply_text(responses[text], reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    # --- معالجة البحث الرقمي (استعلام الغياب) ---
    if text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري فحص السجلات، لحظات...")
        try:
            if not os.path.exists('data.xlsx'):
                await status_msg.edit_text("⚠️ ملف البيانات `data.xlsx` غير متوفر حالياً.")
                return

            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            
            # الأعمدة المعتمدة من ملفك (stu_num, stu_nam, c_nam, parsnt)
            c_id, c_name, c_sub, c_abs = 'stu_num', 'stu_nam', 'c_nam', 'parsnt'
            
            df[c_id] = df[c_id].astype(str).str.strip()
            result = df[df[c_id] == text]

            # حذف رسالة الانتظار
            await status_msg.delete()

            if not result.empty:
                s_name = result.iloc[0][c_name]
                msg = f"✅ **تم استرجاع البيانات بنجاح:**\n\n"
                msg += f"👤 **المتدرب:** `{s_name}`\n"
                msg += f"🆔 **الرقم:** `{text}`\n"
                msg += "━━━━━━━━━━━━━━\n"
                
                for _, row in result.iterrows():
                    try:
                        val = float(row[c_abs])
                    except:
                        val = 0.0

                    # --- منطق الحرمان الجديد ---
                    if val >= 20:
                        icon = "🔴 حرمان"
                    elif 15 <= val < 20:
                        icon = "⚠️ قريب جداً من الحرمان"
                    else:
                        icon = "🟢 منتظم"

                    msg += f"📖 **{row[c_sub]}**\n"
                    msg += f"  └ نسبة الغياب: %{val} ⇦ {icon}\n"
                    msg += "───────────────\n"
                
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ لم يتم العثور على هذا الرقم التدريبي في سجلاتنا.", reply_markup=get_back_menu())
        
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text(f"⚠️ حدث خطأ أثناء المعالجة. تأكد من سلامة ملف الإكسل.", reply_markup=get_back_menu())
            print(f"Error: {e}")

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ خطأ: يجب كتابة الرقم التدريبي في 'وصف الصورة' لضمان توجيه العذر.")
        return
    
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر جديد مستلم:**\n📝 البيانات المرفقة: {update.message.caption}")
    await update.message.copy(chat_id=GROUP_ID)
    await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للمسؤول المختص.", reply_markup=get_main_menu())

# --- 5. التشغيل النهائي ---
def main():
    # تشغيل السيرفر في الخلفية
    Thread(target=run_web_server, daemon=True).start()
    
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))

    print("🚀 البوت يعمل الآن بكفاءة عالية...")
    app.run_polling()

if __name__ == '__main__':
    main()
