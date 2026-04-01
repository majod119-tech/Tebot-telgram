import os
import io
import requests
import pandas as pd
import json
import random
import time
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient

# 🟢 استدعاء خدمات الذكاء الاصطناعي المربوطة بالقاعدة 🟢
from ai_service import extract_text_from_pdf_bytes, save_knowledge_to_db, build_ai_prompt

# ==========================================
# 1. إعدادات النظام والاتصال بقواعد البيانات
# ==========================================
TOKEN = os.environ.get("TOKEN") 
if not TOKEN:
    raise ValueError("❌ خطأ قاتل: TOKEN غير موجود في البيئة!")

MONGO_URI = os.getenv("MONGODB_URI")
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"

# 🛑 تأكد أن هذا هو رقم الآيدي الخاص بك 🛑
ADMIN_ID = "6167816001" 

OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"

try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        users_col = db["users"]          
        excuses_col = db["excuses"]      
        reports_col = db["reports"]      
        print("✅ تم الاتصال بقاعدة البيانات السحابية (MongoDB) بنجاح!")
except Exception as e:
    print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")

# --- دالات النظام ---
def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: pass
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

try:
    from questions_bank import QUESTIONS
except:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

TECH_TIPS = [
    "💡 نصيحة أمنية: استخدم مفتاحي (Win + L) لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ نصيحة تقنية: احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات."
]

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

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
        if col_prep not in df_so09.columns or col_trainer not in df_so09.columns:
            return "⚠️ أعمدة التقرير غير متطابقة مع نموذج نظام رايات."
        df_so09[col_prep] = pd.to_numeric(df_so09[col_prep].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        total_sections = len(df_so09)
        prepared_sections = len(df_so09[df_so09[col_prep] >= 100])
        unprepared_sections = total_sections - prepared_sections
        trainers_df = df_so09.groupby(col_trainer).agg(total_sec=(col_section, 'count'), prep_sec=(col_prep, lambda x: (x >= 100).sum())).reset_index()
        total_trainers = len(trainers_df)
        fully_prepared_trainers = len(trainers_df[trainers_df['total_sec'] == trainers_df['prep_sec']])
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({int(row['total_sec'] - row['prep_sec'])} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "جميع المدربين أتموا الرصد ✅"
        avg_attendance_perc = df_so09[col_prep].mean()
        df_trainees = get_excel_data()
        total_trainees = 0
        if df_trainees is not None: total_trainees = df_trainees['stu_num'].nunique()
        current_week = datetime.now().isocalendar()[1]
        return f"""📑 *تقرير سير العملية التدريبية* 📑\n📅 الأسبوع التدريبي: `{current_week}`\n{SEP}\n📈 نسبة الحضور الأسبوعية: `{avg_attendance_perc:.2f}%`\n✅ الشعب المحضرة: `{prepared_sections}`\n⚠️ الشعب المتأخرة: `{unprepared_sections}`\n{SEP}\n📋 *المدربين المتأخرين بالرصد:*\n{late_list_text}"""
    except Exception as e: return f"⚠️ خطأ في المعالجة: {e}"

def background_tasks():
    while True:
        try:
            now = datetime.now()
            if now.weekday() == 3 and now.hour == 14:
                auto_report = build_weekly_report()
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": ADMIN_ID, "text": auto_report, "parse_mode": "Markdown"}, timeout=10)
        except: pass
        time.sleep(3600)

class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
        self.wfile.write("<html><body><h1> خادم القسم يعمل بنجاح 🚀</h1></body></html>".encode('utf-8'))

def run_web_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), WebDashboardHandler)
    server.serve_forever()

AI_KNOWLEDGE = ("أنت 'المعلم الذكي' لقسم الحاسب ببريدة. تشرح بوضوح وتفصيل.")
user_states = {}
