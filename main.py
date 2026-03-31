import os
import io
import requests
import pandas as pd
import json
import random
import time
import asyncio
from datetime import datetime
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient

# ==========================================
# 1. إعدادات النظام والاتصال بقواعد البيانات
# ==========================================
TOKEN = os.environ.get("TOKEN") 
if not TOKEN:
    raise ValueError("❌ خطأ قاتل: TOKEN غير موجود في البيئة! الرجاء إضافته في إعدادات Koyeb.")

MONGO_URI = os.getenv("MONGODB_URI")
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

# 🟢 تهيئة قاعدة البيانات 🟢
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

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except Exception as e: pass
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except Exception as e: pass

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

# ==========================================
# ⚡ نظام التخزين المؤقت (Caching) للإكسل
# ==========================================
EXCEL_CACHE = None
LAST_CACHE_TIME = 0

def get_excel_data():
    global EXCEL_CACHE, LAST_CACHE_TIME
    file_path = 'data.xlsx'
    if not os.path.exists(file_path): 
        return None
    
    current_mtime = os.path.getmtime(file_path)
    if EXCEL_CACHE is None or current_mtime > LAST_CACHE_TIME:
        try:
            df = pd.read_excel(file_path, dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
            EXCEL_CACHE = df
            LAST_CACHE_TIME = current_mtime
        except Exception as e:
            return None
    return EXCEL_CACHE

# ==========================================
# 📊 محرك التقارير الأسبوعية (الشامل)
# ==========================================
def build_weekly_report():
    try:
        if not os.path.exists("so09.csv"): 
            return "⚠️ لم يتم رفع إحصائيات الشعب (SO09) حتى الآن."
        
        df_so09 = pd.read_csv("so09.csv", dtype=str)
        col_prep = 'نسبة التحضير'
        col_trainer = 'اسم المدرب'
        col_section = 'رمز المقرر'

        if col_prep not in df_so09.columns or col_trainer not in df_so09.columns:
            return "⚠️ أعمدة التقرير غير متطابقة مع نموذج نظام رايات المعتمد."

        df_so09[col_prep] = pd.to_numeric(df_so09[col_prep].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        
        total_sections = len(df_so09)
        prepared_sections = len(df_so09[df_so09[col_prep] >= 100])
        unprepared_sections = total_sections - prepared_sections
        
        trainers_df = df_so09.groupby(col_trainer).agg(
            total_sec=(col_section, 'count'),
            prep_sec=(col_prep, lambda x: (x >= 100).sum())
        ).reset_index()
        
        total_trainers = len(trainers_df)
        fully_prepared_trainers = len(trainers_df[trainers_df['total_sec'] == trainers_df['prep_sec']])
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_trainers = len(late_trainers_df)
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({int(row['total_sec'] - row['prep_sec'])} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "لا يوجد تأخير، جميع المدربين أتموا الرصد ✅"
        
        avg_attendance_perc = df_so09[col_prep].mean()
        
        # قراءة بيانات المتدربين لرصد الحرمان وطي القيد
        df_trainees = get_excel_data()
        total_trainees = 0; present_trainees = 0; deprived_count = 0; expelled_count = 0
        
        if df_trainees is not None:
            total_trainees = df_trainees['stu_num'].nunique()
            df_trainees['clean_parsnt'] = pd.to_numeric(df_trainees['parsnt'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            # الفرز حسب نسبة 20% أو وجود حرف "ح" أو "ط"
            deprived_mask = (df_trainees['clean_parsnt'] >= 20) | (df_trainees['parsnt'].str.contains('ح|حرمان', na=False))
            expelled_mask = df_trainees['parsnt'].str.contains('ط|طي', na=False)
            
            deprived_count = df_trainees[deprived_mask]['stu_num'].nunique()
            expelled_count = df_trainees[expelled_mask]['stu_num'].nunique()
            present_trainees = int((avg_attendance_perc / 100) * total_trainees)
            
        current_week = datetime.now().isocalendar()[1]

        report = f"""
📑 *تقرير سير العملية التدريبية الأسبوعية* 📑
📅 الأسبوع التدريبي: `{current_week}`
{SEP}
👥 *إحصائيات المتدربين والحضور:*
▫️ إجمالي المتدربين بالقسم: `{total_trainees}`
▫️ المتدربين الحاضرين: `{present_trainees}`
📈 نسبة الحضور الأسبوعية: `{avg_attendance_perc:.2f}%`

🛑 *مؤشرات الخطر الأكاديمي:*
⚠️ المتدربين المحرومين: `{deprived_count}`
❌ طي القيد / منسحبين: `{expelled_count}`

📝 *إحصائيات الشعب التدريبية:*
▫️ إجمالي عدد الشعب: `{total_sections}`
✅ الشعب المحضرة: `{prepared_sections}`
⚠️ الشعب غير المحضرة: `{unprepared_sections}`

👨‍🏫 *إحصائيات المدربين:*
▫️ إجمالي عدد المدربين: `{total_trainers}`
✅ المدربين المحضرين: `{fully_prepared_trainers}`
⚠️ المدربين المتأخرين: `{late_trainers}`
{SEP}
📋 *المدربين المتأخرين بالرصد:*
{late_list_text}
"""
        return report
    except Exception as e:
        return f"⚠️ خطأ في المعالجة: {e}"

# ==========================================
# 2. المهام الخلفية والويب
# ==========================================
def background_tasks():
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            stats = load_json(STATS_FILE)
            if now.weekday() == 6 and stats.get("last_reset_date") != today_str:
                save_json(SCORES_FILE, {}) 
                stats["last_reset_date"] = today_str 
                save_json(STATS_FILE, stats)
                
            if now.weekday() == 3 and now.hour == 14:
                if stats.get("last_thursday_report") != today_str:
                    auto_report = build_weekly_report()
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": ADMIN_ID, "text": auto_report, "parse_mode": "Markdown"}, timeout=10)
                    stats["last_thursday_report"] = today_str
                    save_json(STATS_FILE, stats)
        except Exception as e: pass
        time.sleep(60)

class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write("<html><body><h1>📊 خادم قسم الحاسب يعمل بنجاح</h1></body></html>".encode('utf-8'))

def run_web_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), WebDashboardHandler)
    server.serve_forever()

# ==========================================
# 3. إعدادات الذكاء الاصطناعي (Gemini RAG)
# ==========================================
AI_KNOWLEDGE = (
    "أنت 'المعلم الذكي' والمستشار الأكاديمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "شخصيتك: مستشار خبير، ودود، متعاون جداً، تشرح بوضوح وتفصيل. "
    "الغياب والحرمان 20%، الإنذار 15%. المكافأة 800 ريال. رفع الأعذار خلال 3 أيام."
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''), generation_config={"temperature": 0.2})
                break
    except Exception as e: pass

user_states = {}

# ==========================================
# 4. القوائم التفاعلية
# ==========================================
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي (مستشار القسم)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 المنصات الإلكترونية", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["❓ الأسئلة الشائعة", "📘 دليل المتدرب"],
        ["📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والتقنية"]
    ], resize_keyboard=True, is_persistent=True)

def get_admin_menu():
    return ReplyKeyboardMarkup([
        ["📑 تقرير سير العملية الأسبوعية", "📊 حالة قاعدة البيانات"],
        ["📢 إرسال تعميم", "📈 تقرير التميز المؤسسي"],
        ["📥 تصدير كشوفات الإكسل", "🧠 تحليل الجودة بالذكاء الاصطناعي"],
        ["💾 سحب نسخة احتياطية", "🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)
def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_pledge_step1_menu(): return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)
def get_pledge_step2_menu(): return ReplyKeyboardMarkup([["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"], ["❌ إلغاء العملية"]], resize_keyboard=True)
def get_pledge_step3_menu(): return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)
def get_plans_menu(): return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_games_menu(): return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# ==========================================
# 5. أوامر البداية
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user = update.effective_user
    user_id = str(user.id)
    
    try: 
        users_col.update_one({"telegram_id": user_id}, {"$set": {"first_name": user.first_name, "username": user.username, "last_active": datetime.now()}}, upsert=True)
    except: pass
    
    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
        
    if user_id in user_states: del user_states[user_id]
    welcome_msg = f"أهلاً بك يا {user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n👇 الرجاء اختيار الخدمة المطلوبة:"
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_
