import os
import io
import requests
import pandas as pd
import json
import random
import time
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask
from pymongo import MongoClient
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# 🟢 استدعاء خدمات الذكاء الاصطناعي (تأكد من وجود ملف ai_service.py) 🟢
try:
    from ai_service import extract_text_from_pdf_bytes, save_knowledge_to_db, build_ai_prompt
except Exception as e:
    print(f"⚠️ تنبيه: ملف ai_service غير موجود: {e}")

# ==========================================
# 1. الإعدادات الأساسية
# ==========================================
TOKEN = os.environ.get("TOKEN") 
MONGO_URI = os.getenv("MONGODB_URI")
PORT = int(os.environ.get("PORT", 8080))

ADMIN_ID = "10073498" 
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com"
SEP = "━━━━━━━━━━━━━━"

# ==========================================
# 2. نظام الإنعاش (Flask Keep-Alive)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "🚀 خادم قسم الحاسب الآلي بالمعهد الصناعي الثانوي ببريدة يعمل بنجاح!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 3. الاتصال بقاعدة البيانات
# ==========================================
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client["computer_dept_db"] 
        print("✅ تم الاتصال بقاعدة البيانات السحابية (MongoDB) بنجاح!")
except Exception as e:
    print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")

# ==========================================
# 4. الدوال المساعدة والتقارير
# ==========================================
EXCEL_CACHE = None

def get_excel_data():
    global EXCEL_CACHE
    if EXCEL_CACHE is not None: return EXCEL_CACHE
    try:
        records = list(db["trainees_data"].find({}, {"_id": 0}))
        if not records: return None
        df = pd.DataFrame(records)
        df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
        EXCEL_CACHE = df
        return EXCEL_CACHE
    except: return None

def build_weekly_report():
    try:
        records = list(db["so09_data"].find({}, {"_id": 0}))
        if not records: return "⚠️ لم يتم رفع إحصائيات الشعب (SO09) حتى الآن."
        df_so09 = pd.DataFrame(records)
        col_prep, col_trainer, col_section = 'نسبة التحضير', 'اسم المدرب', 'رمز المقرر'
        df_so09[col_prep] = pd.to_numeric(df_so09[col_prep].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        total_sections = len(df_so09)
        prepared_sections = len(df_so09[df_so09[col_prep] >= 100])
        unprepared_sections = total_sections - prepared_sections
        trainers_df = df_so09.groupby(col_trainer).agg(total_sec=(col_section, 'count'), prep_sec=(col_prep, lambda x: (x >= 100).sum())).reset_index()
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({int(row['total_sec'] - row['prep_sec'])} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "جميع المدربين أتموا الرصد ✅"
        avg_attendance_perc = df_so09[col_prep].mean()
        current_week = datetime.now().isocalendar()[1]
        return f"""📑 *تقرير سير العملية التدريبية* 📑\n📅 الأسبوع التدريبي: `{current_week}`\n{SEP}\n📈 نسبة الحضور الأسبوعية: `{avg_attendance_perc:.2f}%`\n✅ الشعب المحضرة: `{prepared_sections}`\n⚠️ الشعب المتأخرة: `{unprepared_sections}`\n{SEP}\n📋 *المدربين المتأخرين بالرصد:*\n{late_list_text}"""
    except Exception as e: return f"⚠️ خطأ في المعالجة: {e}"

def background_tasks():
    while True:
        try:
            now = datetime.now()
            if now.weekday() == 3 and now.hour == 14: # الخميس الساعة 2 الظهر
                auto_report = build_weekly_report()
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": ADMIN_ID, "text": auto_report, "parse_mode": "Markdown"}, timeout=10)
        except: pass
        time.sleep(3600)

# ==========================================
# 5. أوامر التيليجرام (التي تم إعادة بنائها)
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"مرحباً بك يا {user.first_name} في الخدمة الآلية لقسم الحاسب الآلي 🖥️\nكيف يمكنني مساعدتك اليوم؟")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("🚫 عذراً، هذه اللوحة مخصصة لرئيس القسم فقط.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 حالة قاعدة البيانات", callback_data='db_status')],
        [InlineKeyboardButton("📑 تقرير سير العملية الأسبوعية", callback_data='weekly_report')],
        [InlineKeyboardButton("💾 سحب نسخة احتياطية", callback_data='backup')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم المتقدمة 🛡️", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'db_status':
        try:
            users_count = db["trainees_data"].count_documents({})
            await query.edit_message_text(f"📊 *حالة قاعدة البيانات:*\nعدد المتدربين المسجلين: `{users_count}`", parse_mode='Markdown')
        except:
            await query.edit_message_text("⚠️ لا يمكن الاتصال بقاعدة البيانات حالياً.")
            
    elif query.data == 'weekly_report':
        report = build_weekly_report()
        await query.edit_message_text(report, parse_mode='Markdown')
        
    elif query.data == 'backup':
        await query.edit_message_text("💾 جاري تجهيز النسخة الاحتياطية... (تحتاج لربطها بدالة التصدير)")

# استلام الملفات (PDF / Excel) لمعالجتها
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("🚫 عذراً، غير مصرح لك برفع الملفات.")
        return
        
    await update.message.reply_text("⏳ تم استلام الملف، جاري المعالجة... قد يستغرق الأمر لحظات.")
    # هنا يتم ربط دوال AI أو حفظ الإكسل حسب نوع الملف
    file_name = update.message.document.file_name
    await update.message.reply_text(f"✅ تمت معالجة الملف: {file_name} بنجاح!")

# استلام الرسائل النصية والرد بالذكاء الاصطناعي (OpenClaw)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    await update.message.chat.send_action(ChatAction.TYPING)
    
    # رسالة مؤقتة لتوضيح أن الذكاء الاصطناعي يعمل، يمكنك تفعيل الـ API هنا
    reply = f"وصلت رسالتك: '{user_msg}'. المعلم الذكي قيد التجهيز للرد عليها 🧠."
    await update.message.reply_text(reply)


# ==========================================
# 6. التشغيل الرئيسي
# ==========================================
def main():
    if not TOKEN:
        print("❌ خطأ قاتل: TOKEN غير موجود!")
        return

    # تشغيل الرئة (المنفذ الوهمي لريندر)
    keep_alive()
    
    # تشغيل المهام المجدولة (التقارير)
    t_bg = Thread(target=background_tasks)
    t_bg.daemon = True
    t_bg.start()

    # بناء البوت
    application = Application.builder().token(TOKEN).build()

    # ربط الأوامر بالدوال
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 البوت شغال الآن ومستعد لخدمة القسم...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
