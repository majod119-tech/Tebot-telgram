import os
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
import google.generativeai as genai
from flask import Flask
from threading import Thread

# ==========================================
# 1. إعدادات السيرفر والمتغيرات السرية (من Koyeb)
# ==========================================
TOKEN = os.environ.get("TOKEN")
MONGODB_URI = os.environ.get("MONGODB_URI")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# رقمك السري لإدارة قسم الحاسب
ADMIN_ID = 10073498 

# ==========================================
# 2. ربط قواعد البيانات والذكاء الاصطناعي
# ==========================================
# الاتصال بقاعدة MongoDB
client = MongoClient(MONGODB_URI)
db = client["ComputerDeptDB"]      # اسم قاعدة البيانات
collection = db["RayatRecords"]    # اسم جدول المتدربين والمدربين

# إعداد نموذج Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# ==========================================
# 3. خادم الويب المصغر (لمنع نوم السيرفر في Koyeb)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake and running smoothly!"

def run_server():
    # هذا السطر الذكي يقرأ المنفذ الذي يطلبه Koyeb (10000) تلقائياً
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# ==========================================
# 4. أوامر المتدربين والمدربين (العامة)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك {user_name} في البوت الآلي لقسم الحاسب وتقنية المعلومات! 💻\n"
        "أنا هنا لخدمتك وتسهيل استعلاماتك."
    )

# يمكنك لاحقاً إضافة أي دوال أخرى للمتدربين هنا...

# ==========================================
# 5. أوامر رئيس القسم السرية (تحليل الملفات)
# ==========================================
async def handle_admin_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # حارس البوابة: طرد صامت لأي شخص غيرك يحاول رفع ملفات
    if user_id != ADMIN_ID:
        return

    document = update.message.document
    file_name = document.file_name
    
    processing_msg = await update.message.reply_text("📥 تم استلام كشف رايات السري.. جاري التحليل والأرشفة ⏱️...")

    try:
        # تحميل الملف مؤقتاً في سيرفر ألمانيا
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{file_name}"
        await file.download_to_drive(file_path)

        # قراءة الملف حسب صيغته
        if file_name.endswith('.csv') or file_name.endswith('.txt'):
            df = pd.read_csv(file_path, sep=',') 
        elif file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            await processing_msg.edit_text("⚠️ يرجى رفع الكشف بصيغة CSV أو Excel لضمان الدقة.")
            os.remove(file_path)
            return

        # --- قسم الذكاء الاصطناعي (Gemini) ---
        data_text = df.to_string()
        prompt = f"""
        أنت المساعد التنفيذي الذكي لقسم الحاسب. قام المدير برفع ملف من نظام رايات.
        المطلوب:
        - أعطني إحصائية سريعة لعدد المتدربين أو المدربين.
        - استخرج الأسماء التي لديها ملاحظات أو غياب مرتفع.
        - لخص لي وضع القسم.
        
        بيانات الملف:
        {data_text[:10000]} 
        """
        response = model.generate_content(prompt)
        ai_summary = response.text

        # --- قسم قاعدة البيانات (MongoDB) ---
        records = df.to_dict('records')
        if records:
            collection.insert_many(records) 
            db_status = "✅ تم أرشفة بيانات المتدربين/المدربين في قاعدة البيانات بنجاح."
        else:
            db_status = "⚠️ الملف فارغ، لم يتم الحفظ."

        # --- إرسال التقرير النهائي ---
        final_message = f"📊 **تقرير الذكاء الاصطناعي:**\n\n{ai_summary}\n\n---\n{db_status}"
        await processing_msg.edit_text(final_message, parse_mode='Markdown')

    except Exception as e:
        await processing_msg.edit_text(f"❌ حدث خطأ أثناء المعالجة: {e}")
    finally:
        # التخلص من الملف فوراً لحماية السجلات
        if os.path.exists(file_path):
            os.remove(file_path)

# ==========================================
# 6. محرك التشغيل الرئيسي
# ==========================================
def main():
    # تشغيل السيرفر الداعم للمنفذ 10000 لمنع إيقاف Koyeb
    keep_alive()

    # بناء التطبيق وربطه بتوكن التليجرام
    application = Application.builder().token(TOKEN).build()

    # تفعيل الأوامر العامة
    application.add_handler(CommandHandler("start", start))
    
    # تفعيل حساس الملفات السري للإدارة
    application.add_handler(MessageHandler(filters.Document.ALL, handle_admin_files))

    # إقلاع البوت
    print("🚀 السيرفر يعمل الآن... البوت جاهز لاستقبال الرسائل والملفات!")
    application.run_polling()

if __name__ == '__main__':
    main()
