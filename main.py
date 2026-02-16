import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر ويب وهمي (لإبقاء البوت يعمل على Render) ---
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

# --- 3. لوحات المفاتيح (أزرار التحكم) ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "🔗 منصة تقني ورايات"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"],
        ["📅 التقويم التدريبي"]
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

    # زر الرجوع
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # الأقسام الثابتة والروابط
    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 **موقع قسم الحاسب:**\n[اضغط هنا للوصول عبر الخرائط](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
    
    elif text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 **أهم الروابط التدريبية:**\n\n🔹 [منصة تقني (Blackboard)](https://tvtclms.edu.sa)\n🔹 [بوابة رايات](https://rayat.tvtc.gov.sa)", reply_markup=get_back_menu(), parse_mode='Markdown')
    
    elif text == "📅 التقويم التدريبي":
        # قراءة الصورة بالاسم الجديد calendar.jpg
        photo_path = 'calendar.jpg' 
        if os.path.exists(photo_path):
            await update.message.reply_photo(
                photo=open(photo_path, 'rb'),
                caption="📅 **التقويم التدريبي المعتمد للفصل الحالي**",
                reply_markup=get_back_menu()
            )
        else:
            await update.message.reply_text("⚠️ عذراً، لم يتم العثور على ملف الصورة باسم `calendar.jpg` على السيرفر.", reply_markup=get_back_menu())
    
    elif text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 فضلاً أرسل **رقمك التدريبي** الآن وسأقوم بالبحث في السجلات..", reply_markup=get_back_menu())
    
    elif text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **تعليمات رفع العذر:**\nقم بإرفاق صورة العذر الطبي أو الرسمي، واكتب (رقمك التدريبي) في خانة الوصف (Caption).", reply_markup=get_back_menu())
    
    elif text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text("👨‍🏫 **للتواصل مع رئيس قسم الحاسب:**\n\n✉️ البريد الإلكتروني: `aalmoshegh@tvtc.gov.sa`", reply_markup=get_back_menu(), parse_mode='Markdown')

    # --- منطق البحث في الإكسل ---
    elif text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري فحص السجلات، فضلاً انتظر...")
        try:
            if not os.path.exists('data.xlsx'):
                await status_msg.edit_text("⚠️ خطأ: ملف البيانات `data.xlsx` غير موجود.")
                return

            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            
            # الأعمدة المعتمدة
            c_id, c_name, c_sub, c_abs = 'stu_num', 'stu_nam', 'c_nam', 'parsnt'
            
            df[c_id] = df[c_id].astype(str).str.strip()
            result = df[df[c_id] == text]

            await status_msg.delete() # حذف رسالة الانتظار

            if not result.empty:
                s_name = result.iloc[0][c_name]
                msg = f"✅ **تم العثور على البيانات لـ:** `{s_name}`\n"
                msg += f"🆔 **الرقم التدريبي:** `{text}`\n"
                msg += "━━━━━━━━━━━━━━\n"
                
                for _, row in result.iterrows():
                    val = float(row[c_abs])
                    # توزيع الألوان حسب النسب المطلوبة
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
                await update.message.reply_text("❌ عذراً، الرقم التدريبي غير مسجل في النظام.", reply_markup=get_back_menu())
        
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text(f"⚠️ حدث خطأ فني أثناء قراءة البيانات.", reply_markup=get_back_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملفات الأعذار المرفوعة"""
    if not update.message.caption:
        await update.message.reply_text("⚠️ يرجى كتابة الرقم التدريبي في وصف الصورة لضمان أرشفة العذر.")
        return
    
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر جديد مستلم:**\n🆔 البيانات: {update.message.caption}")
    await update.message.copy(chat_id=GROUP_ID)
    await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للجنة المختصة.", reply_markup=get_main_menu())

# --- 5. تشغيل البوت ---
def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))

    print("🚀 البوت يعمل الآن باسم الملف calendar.jpg...")
    app.run_polling()

if __name__ == '__main__':
    main()
