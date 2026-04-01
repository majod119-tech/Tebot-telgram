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

# 🟢 استدعاء خدمات الذكاء الاصطناعي 🟢
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

import certifi # 👈 هذي المكتبة هي التصريح الأمني

try:
    if MONGO_URI:
        # 👈 أضفنا tlsCAFile عشان نعطي البوت شهادة الأمان للعبور
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
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
# 5. أوامر التيليجرام المحدثة بالكامل
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # إضافة لوحة المفاتيح السفلية للرئيس
    reply_keyboard = [
        ['📊 حالة قاعدة البيانات', '📑 تقرير سير العملية الأسبوعية'],
        ['💾 سحب نسخة احتياطية']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"مرحباً بك يا {user.first_name} في الخدمة الآلية لقسم الحاسب الآلي 🖥️\nكيف يمكنني مساعدتك اليوم؟",
        reply_markup=markup if str(user.id) == ADMIN_ID else None
    )

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
        await query.edit_message_text("💾 جاري تجهيز النسخة الاحتياطية...")

# المعالجة الحقيقية لرفع ملفات الإكسل للقاعدة
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("🚫 عذراً، غير مصرح لك برفع الملفات.")
        return
        
    msg = await update.message.reply_text("⏳ جاري تحميل الملف وقراءة البيانات...")
    
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_bytes = await file.download_as_bytearray()
        file_name = update.message.document.file_name.lower()
        
        if file_name.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif file_name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            await msg.edit_text("⚠️ المعذرة، يرجى رفع ملفات بصيغة Excel أو CSV فقط لتحديث القاعدة.")
            return

        records = df.to_dict('records')
        
        if len(records) > 0:
            db["trainees_data"].delete_many({}) 
            db["trainees_data"].insert_many(records)
            global EXCEL_CACHE
            EXCEL_CACHE = None 
            await msg.edit_text(f"✅ تمت معالجة الملف بنجاح!\nتم تحديث قاعدة بيانات القسم وإضافة `{len(records)}` سجل.")
        else:
            await msg.edit_text("⚠️ الملف فارغ، لم يتم تحديث القاعدة.")
            
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ أثناء معالجة الملف، يرجى التأكد من صيغة الإكسل.")
        print(f"Error handling document: {e}")

# الاستجابة لرسائل الأزرار أو الذكاء الاصطناعي
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    await update.message.chat.send_action(ChatAction.TYPING)
    
    if user_msg == '📊 حالة قاعدة البيانات' or user_msg == 'حالة قاعدة البيانات':
        try:
            users_count = db["trainees_data"].count_documents({})
            await update.message.reply_text(f"📊 *حالة قاعدة البيانات:*\nعدد المتدربين المسجلين: `{users_count}`", parse_mode='Markdown')
        except:
            await update.message.reply_text("⚠️ لا يمكن الاتصال بقاعدة البيانات حالياً.")
            
    elif user_msg == '📑 تقرير سير العملية الأسبوعية' or user_msg == 'تقرير سير العملية الأسبوعية':
        report = build_weekly_report()
        await update.message.reply_text(report, parse_mode='Markdown')
        
    elif user_msg == '💾 سحب نسخة احتياطية' or user_msg == 'سحب نسخة احتياطية':
        await update.message.reply_text("💾 جاري تجهيز النسخة الاحتياطية...")
        
    else:
        reply = f"وصلت رسالتك: '{user_msg}'. المعلم الذكي قيد التجهيز للرد عليها 🧠."
        await update.message.reply_text(reply)

# ==========================================
# 6. التشغيل الرئيسي
# ==========================================
def main():
    if not TOKEN:
        print("❌ خطأ قاتل: TOKEN غير موجود!")
        return

    keep_alive()
    
    t_bg = Thread(target=background_tasks)
    t_bg.daemon = True
    t_bg.start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 البوت شغال الآن ومستعد لخدمة القسم...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
