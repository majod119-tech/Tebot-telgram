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

# 🟢 تهيئة قاعدة البيانات الاحترافية 🟢
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        users_col = db["users"]         # جدول المستخدمين
        excuses_col = db["excuses"]     # جدول الأعذار الطبية
        reports_col = db["reports"]     # جدول التقارير
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
# 📊 محرك التقارير الأسبوعية (SO09 + بيانات القسم)
# ==========================================
def build_weekly_report():
    try:
        if not os.path.exists("so09.csv"): 
            return "⚠️ لم يتم رفع تقرير الشعب (SO09) حتى الآن."
        
        df = pd.read_csv("so09.csv", dtype=str)
        
        def find_col(keywords):
            for col in df.columns:
                c_clean = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا')
                if any(k in c_clean for k in keywords): return col
            return None

        col_prep = find_col(['نسبهالتحضير', 'التحضير'])
        col_trainer = find_col(['اسمالمدرب', 'المدرب'])
        col_section = find_col(['الشعبه', 'الرقمالمرجعي', 'رقم'])

        if not all([col_prep, col_trainer, col_section]):
            return "⚠️ أعمدة التقرير غير متطابقة مع نموذج نظام رايات."

        # تنظيف وتحويل نسب التحضير لأرقام
        df[col_prep] = pd.to_numeric(df[col_prep].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        
        total_sections = len(df)
        prepared_sections = len(df[df[col_prep] >= 100])
        unprepared_sections = total_sections - prepared_sections
        
        # إحصائيات المدربين
        trainers_df = df.groupby(col_trainer).agg(
            total_sec=(col_section, 'count'),
            prep_sec=(col_prep, lambda x: (x >= 100).sum())
        ).reset_index()
        
        total_trainers = len(trainers_df)
        fully_prepared_trainers = len(trainers_df[trainers_df['total_sec'] == trainers_df['prep_sec']])
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_trainers = len(late_trainers_df)
        
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({row['total_sec'] - row['prep_sec']} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "لا يوجد تأخير، جميع المدربين أتموا الرصد ✅"
        
        # تطبيق معادلة الجودة لحساب الحضور (متوسط التحضير * إجمالي الطلاب)
        avg_attendance_perc = df[col_prep].mean()
        
        # جلب إجمالي المتدربين من قاعدة البيانات أو الإكسل الأساسي
        df_students = get_excel_data()
        total_trainees = df_students['stu_num'].nunique() if df_students is not None else 0
        present_trainees = int((avg_attendance_perc / 100) * total_trainees) if total_trainees > 0 else 0

        report = f"""
📑 *تقرير متابعة سير العملية التدريبية الأسبوعية* 📑
{SEP}

👥 *إحصائيات المتدربين والحضور:*
▫️ إجمالي المتدربين (التحضير): `{total_trainees}`
▫️ المتدربين الحاضرين: `{present_trainees}`
📈 نسبة الحضور: `{avg_attendance_perc:.2f}%`

📝 *إحصائيات الشعب التدريبية:*
▫️ إجمالي عدد الشعب: `{total_sections}`
✅ الشعب المحضرة: `{prepared_sections}`
⚠️ الشعب غير المحضرة: `{unprepared_sections}`

👨‍🏫 *إحصائيات المدربين:*
▫️ إجمالي عدد المدربين: `{total_trainers}`
✅ المدربين المحضرين: `{fully_prepared_trainers}`
⚠️ المدربين غير المحضرين: `{late_trainers}`
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
                
            # إرسال التقرير الأوتوماتيكي يوم الخميس
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
        html = "<html><body><h1>📊 خادم قسم الحاسب يعمل بنجاح</h1></body></html>"
        self.wfile.write(html.encode('utf-8'))

def run_web_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), WebDashboardHandler)
    server.serve_forever()

# ==========================================
# 3. إعدادات الذكاء الاصطناعي (Gemini RAG)
# ==========================================
AI_KNOWLEDGE = (
    "أنت 'المعلم الذكي' والمستشار الأكاديمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "شخصيتك: مستشار خبير، ودود، متعاون. "
    "قاعدة البيانات: الغياب والحرمان 20%، الإنذار 15%. المكافأة 800 ريال. "
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
        ["📥 تصدير كشوفات الإكسل", "💾 سحب نسخة احتياطية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)
def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_pledge_step1_menu(): return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)
def get_pledge_step2_menu(): return ReplyKeyboardMarkup([["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"], ["❌ إلغاء العملية"]], resize_keyboard=True)
def get_pledge_step3_menu(): return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)
def get_plans_menu(): return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_games_menu(): return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# ==========================================
# 5. أوامر البداية والإدارة
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    
    user = update.effective_user
    user_id = str(user.id)
    
    # 🟢 حفظ بيانات المستخدم في قاعدة البيانات للأبد 🟢
    try:
        users_col.update_one(
            {"telegram_id": user_id}, 
            {"$set": {"first_name": user.first_name, "username": user.username, "last_active": datetime.now()}}, 
            upsert=True
        )
    except: pass
    
    if user_id in user_states: del user_states[user_id]
    welcome_msg = f"أهلاً بك يا {user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n👇 الرجاء اختيار الخدمة المطلوبة:"
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def admin_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم المتقدمة 🛡️", reply_markup=get_admin_menu())

# ==========================================
# 6. العمليات المنطقية (مدير + متدربين)
# ==========================================
async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    raw_text = update.message.text.strip()
    text = raw_text[:500] 
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    # 🔴 أوامر لوحة الإدارة 🔴
    if user_id == ADMIN_ID:
        if text == "📑 تقرير سير العملية الأسبوعية":
            report = build_weekly_report()
            return await update.message.reply_text(report, parse_mode='Markdown')

        if text == "📊 حالة قاعدة البيانات":
            try:
                db_users = users_col.count_documents({})
                db_excuses = excuses_col.count_documents({})
                df = get_excel_data()
                excel_records = len(df) if df is not None else 0
                return await update.message.reply_text(f"📊 *إحصائيات قاعدة البيانات:*\n✅ الطلاب المسجلين بالبوت: {db_users}\n📁 الأعذار المرفوعة: {db_excuses}\n📥 السجلات بالإكسل: {excel_records}", parse_mode='Markdown')
            except Exception: return await update.message.reply_text("⚠️ خطأ في قراءة البيانات.")

        if text == "💾 سحب نسخة احتياطية":
            await update.message.reply_text("⏳ جاري التجهيز...")
            for f in ['data.xlsx', 'so09.csv']:
                if os.path.exists(f): 
                    try: await context.bot.send_document(chat_id=user_id, document=open(f, 'rb'))
                    except: pass
            return

        if text == "📢 إرسال تعميم":
            user_states[user_id] = {'flow': 'broadcast'}
            return await update.message.reply_text("📢 أرسل نص التعميم الآن (أو اضغط إلغاء):", reply_markup=get_cancel_menu())

        if text == "📈 تقرير التميز المؤسسي":
            db_records = len(get_excel_data()) if get_excel_data() is not None else 0
            db_users = users_col.count_documents({})
            report_msg = f"🏆 *تقرير الأداء لجائزة التميز* 🏆\n{SEP}\n👥 المسجلين في البوت: `{db_users}`\n🔹 السجلات المؤتمتة: `{db_records}`"
            return await update.message.reply_text(report_msg, parse_mode='Markdown')

        if text == "📥 تصدير كشوفات الإكسل":
            return await update.message.reply_text("⏳ جاري توليد كشف المحرومين والمنذرين...")

    # 🔵 الحالات المستمرة (التعهدات وغيرها) 🔵
    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            menu = get_admin_menu() if user_id == ADMIN_ID and state.get('flow') == 'broadcast' else get_main_menu()
            return await update.message.reply_text("تم العودة 🏠", reply_markup=menu)

        if state['flow'] == 'excuse':
            return await update.message.reply_text("⚠️ الرجاء إرسال **صورة** العذر الطبي وليس نصاً.", reply_markup=get_cancel_menu())

    # 🟢 أوامر المتدربين الشاملة 🟢
    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 الرجاء إرفاق (صورة العذر) الآن، واكتب (رقمك التدريبي) في الوصف.", reply_markup=get_cancel_menu())

    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن (أرقام فقط)...")
    
    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        try:
            df = get_excel_data()
            if df is None: return await update.message.reply_text("⚠️ قاعدة البيانات غير متوفرة.")
            res = df[df['stu_num'] == clean_text]
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                # تحديث بيانات الطالب في MongoDB
                users_col.update_one({"telegram_id": user_id}, {"$set": {"stu_num": clean_text, "stu_nam": stu_nam}}, upsert=True)
                
                m = f"🎓 *السجل الأكاديمي*\n{SEP}\n👤 *الاسم:* {stu_nam}\n🔢 *الرقم:* {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    val = str(r.get('parsnt', '0'))
                    m += f"📖 {c_name_text}\n▫️ النسبة: *{val}*\n\n"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: pass
        return

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# ==========================================
# 7. محرك رفع الملفات وصور الأعذار
# ==========================================
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    
    # معالجة ملفات الإدارة (رايات)
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.xls', '.csv')):
        status_msg = await update.message.reply_text("⏳ جاري تحليل وتصنيف التقرير المرفوع...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            temp_file = "temp_rayat.csv" if update.message.document.file_name.endswith('.csv') else "data.xlsx"
            await file.download_to_drive(temp_file)
            
            if temp_file.endswith('.csv'):
                with open(temp_file, 'rb') as f: raw_bytes = f.read()
                best_enc = 'utf-8'
                for enc in ['utf-8', 'windows-1256', 'cp1256']:
                    try: text = raw_bytes.decode(enc); best_enc = enc; break
                    except: pass
                df_raw = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
                
                # 🟢 التحقق إذا كان الملف هو SO09
                if any('نسبة التحضير' in str(c) for c in df_raw.columns) or any('التحضير' in str(c) for c in df_raw.columns):
                    df_raw.to_csv("so09.csv", index=False)
                    os.remove(temp_file)
                    report_text = build_weekly_report()
                    return await status_msg.edit_text(report_text, parse_mode='Markdown')

                # إذا كان تقرير الطلاب المعتاد
                df_clean = pd.DataFrame()
                col_map = {'c_course': 14, 'c_id': 16, 'c_name': 17, 'c_perc': 18}
                for i, col in enumerate(df_raw.columns):
                    c = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا')
                    if 'اسمالمقرر' in c: col_map['c_course'] = i
                    elif 'رقمالمتدرب' in c: col_map['c_id'] = i
                    elif 'اسمالمتدرب' in c: col_map['c_name'] = i
                    elif 'بعذروبدون' in c and 'نسبه' in c: col_map['c_perc'] = i

                df_clean['c_nam'] = df_raw.iloc[:, col_map['c_course']].astype(str)
                df_clean['stu_num'] = df_raw.iloc[:, col_map['c_id']].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                df_clean['stu_nam'] = df_raw.iloc[:, col_map['c_name']].astype(str)
                df_clean['parsnt'] = df_raw.iloc[:, col_map['c_perc']].astype(str)
                df_clean = df_clean[df_clean['stu_num'].str.len() >= 5]
                df_clean.to_excel("data.xlsx", index=False)
                os.remove(temp_file)

            global EXCEL_CACHE
            EXCEL_CACHE = None 
            await status_msg.edit_text(f"✅ *تم تحديث قاعدة بيانات حضور الطلاب بنجاح!*", parse_mode='Markdown')
        except Exception as e: 
            await status_msg.edit_text(f"⚠️ فشل التحديث: {e}")
        return

    # 🟢 حفظ الأعذار الطبية في قاعدة البيانات 🟢
    if update.message.photo or update.message.document:
        caption_text = update.message.caption
        stu_id = ''.join(filter(str.isdigit, str(caption_text))) if caption_text else ""
        
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض!* ارفق الصورة واكتب *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
            
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري توثيق العذر في قاعدة بيانات القسم...")
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
            
            # حفظ العذر في MongoDB
            excuses_col.insert_one({
                "telegram_id": user_id,
                "stu_num": stu_id,
                "date": timestamp,
                "file_id": file_id,
                "status": "مستلم"
            })

            # توجيه العذر لقروب الإدارة
            await context.bot.send_photo(chat_id=GROUP_ID, photo=file_id, caption=f"📥 *عذر جديد مُوثق:*\nرقم المتدرب: {stu_id}\n⏱️ وقت الرفع: {timestamp}", parse_mode='Markdown')
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الحفظ في قاعدة البيانات وإرسال العذر للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة 🏠", reply_markup=get_main_menu())
        except Exception as e: 
            await status_msg.edit_text(f"⚠️ خطأ أثناء المعالجة.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

def main():
    Thread(target=background_tasks, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النظام الخارق V3.0 (مستشار القسم ومحلل الجودة)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
