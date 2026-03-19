import os
import io
import base64
import requests
import pandas as pd
import json
import random
import time
import asyncio
import urllib.request
import xml.etree.ElementTree as ET
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
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat"
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        trainees_collection = db["trainees"] 
        print("✅ تم الاتصال بقاعدة البيانات السحابية (MongoDB) بنجاح!")
except Exception as e:
    print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            return {}
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {f}: {e}")

try:
    from questions_bank import QUESTIONS
except Exception as e:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

TECH_TIPS = [
    "💡 نصيحة أمنية: استخدم مفتاحي (Win + L) لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ نصيحة تقنية: احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات.",
    "🚀 نصيحة برمجية: التنسيق والمسافات البادئة في لغة بايثون هي أساس عمل الكود.",
    "💾 نصيحة: احرص دائماً على أخذ نسخة احتياطية لملفاتك المهمة.",
    "🌐 نصيحة: تجنب الاتصال بشبكات الواي فاي العامة المفتوحة بدون VPN."
]

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

# ==========================================
# ⚡ نظام التخزين المؤقت (Caching) للإكسل ⚡
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
            print("🔄 تم تحديث الكاش لبيانات الإكسل!")
        except Exception as e:
            print(f"Error caching excel: {e}")
            return None
    return EXCEL_CACHE

# ==========================================
# 2. المهام الخلفية (الخميس وإعادة النقاط) والويب السري
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
                    report_text = f"🗓️ *حصاد الخميس التلقائي*\n{SEP}\nتم إغلاق أسبوع تدريبي جديد. أرسل `/admin` لمراجعة التقارير وسحب كشوفات الغياب.\nنهاية أسبوع سعيدة يا رئيس القسم! ☕"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                    requests.post(url, json={"chat_id": ADMIN_ID, "text": report_text, "parse_mode": "Markdown"}, timeout=10)
                    stats["last_thursday_report"] = today_str
                    save_json(STATS_FILE, stats)
        except Exception as e: 
            print(f"Background Task Error: {e}")
        time.sleep(60)

class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        db_records = 0
        active_students = 0
        df = get_excel_data()
        if df is not None:
            try:
                db_records = len(df)
                active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
                active_students = active_rows['stu_num'].nunique()
            except Exception as e: print(f"Dashboard Error: {e}")
            
        stats = load_json(STATS_FILE)
        ai_q = stats.get("ai_questions", 0)
        html = f"""
        <html>
        <head>
            <title>لوحة القيادة - قسم الحاسب</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; text-align: center; background: #f0f2f5; padding: 20px; direction: rtl; }}
                .header {{ color: #1e3a8a; margin-bottom: 30px; }}
                .card-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }}
                .card {{ background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); width: 250px; border-top: 5px solid #10b981; }}
                .card h3 {{ color: #6b7280; margin: 0 0 10px 0; font-size: 1.2rem; }}
                .card h2 {{ color: #111827; margin: 0; font-size: 2.5rem; }}
            </style>
        </head>
        <body>
            <h1 class="header">📊 لوحة القيادة الحية | قسم الحاسب</h1>
            <div class="card-container">
                <div class="card" style="border-top-color: #3b82f6;"><h3>السجلات المؤتمتة</h3><h2>{db_records}</h2></div>
                <div class="card" style="border-top-color: #10b981;"><h3>المتدربين المنتظمين</h3><h2>{active_students}</h2></div>
                <div class="card" style="border-top-color: #8b5cf6;"><h3>استشارات الذكاء الاصطناعي</h3><h2>{ai_q}</h2></div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebDashboardHandler)
    server.serve_forever()

def backup_to_github(file_path="data.xlsx"):
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    if not github_token or not github_repo: return "⚠️ (حفظ محلي مؤقت، السحابة غير مربوطة)."
    
    url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    try:
        sha = None
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200: sha = resp.json().get("sha")
        with open(file_path, "rb") as f: content = base64.b64encode(f.read()).decode("utf-8")
        data = {"message": f"تحديث قاعدة البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content}
        if sha: data["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=data, timeout=15)
        if put_resp.status_code in [200, 201]: return "✅ **تم التثبيت الدائم في GitHub!**"
        else: return "⚠️ فشل الرفع لـ GitHub."
    except Exception as e: 
        print(f"GitHub Error: {e}")
        return "⚠️ خطأ بالاتصال بـ GitHub."

# ==========================================
# 3. إعدادات الذكاء الاصطناعي (Gemini)
# ==========================================
AI_KNOWLEDGE = (
    "أنت 'المساعد الرقمي'، مساعد ذكي ورسمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "مهمتك الإجابة على جميع استفسارات المستخدمين بشكل مبسط، ودي، ومختصر جداً.\n"
    "1. إذا كان السؤال (عام أو تقني أو ثقافي): أجب عليه بأسلوب مبسط ومفيد وبدون تعقيد.\n"
    "2. إذا كان السؤال يخص (المتدربين، اللوائح، الغياب، الحرمان، المكافآت، أو أنظمة التدريب التقني): "
    "استخدم معلوماتك بالإضافة لهذه الثوابت: (الإنذار عند غياب 15%، الحرمان وطي القيد عند 20%. المكافأة 800 ريال وتتوقف إذا نزل المعدل عن 2.00. درجة الاجتياز 50 للمعاهد. "
    f"رابط الحقائب التدريبية: {DRIVE_LINK}).\n"
    "🚨 تعليمات هامة جداً عند الإجابة على أي سؤال يخص (أنظمة المتدربين): "
    "يجب عليك دائماً وبدون استثناء أن تختم إجابتك بهذه العبارة حرفياً:\n"
    "\n💡 *للمزيد من التفاصيل، يمكنك تحميل (دليل المتدرب الشامل) من خلال الضغط على زر 📘 دليل المتدرب في القائمة الرئيسية بالأسفل.*"
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
    except Exception as e: print(f"Gemini Init Error: {e}")

user_states = {}

# ==========================================
# 4. القوائم التفاعلية 
# ==========================================
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 المنصات الإلكترونية", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["❓ الأسئلة الشائعة", "📘 دليل المتدرب"],
        ["📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]
    ], resize_keyboard=True, is_persistent=True)

def get_admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 حالة قاعدة البيانات", "💾 سحب نسخة احتياطية"],
        ["📢 إرسال تعميم", "📈 تقرير التميز المؤسسي"],
        ["📥 تصدير كشوفات الإكسل", "🦞 مساعد OpenClaw"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)
def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_pledge_step1_menu(): return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)
def get_pledge_step2_menu(): return ReplyKeyboardMarkup([["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"], ["❌ إلغاء العملية"]], resize_keyboard=True)
def get_pledge_step3_menu(): return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)
def get_plans_menu(): return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🖥️ برامج فصلية", "🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_games_menu(): return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# ==========================================
# 5. أوامر البداية والإدارة
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    
    user = update.effective_user
    user_id = str(user.id)
    first_name = user.first_name
    username = user.username

    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_prefix = f"أهلاً بك يا {first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
    try:
        if 'trainees_collection' in globals():
            existing_user = trainees_collection.find_one({"telegram_id": user_id})
            if not existing_user:
                new_trainee = { "telegram_id": user_id, "name": first_name, "username": username, "role": "student", "absence_percentage": 0, "pledges_count": 0, "join_date": datetime.now() }
                trainees_collection.insert_one(new_trainee)
                welcome_prefix = f"🎉 أهلاً بك يا {first_name}! تم فتح ملف إلكتروني لك بنجاح في النظام.\n{SEP}\n"
            else:
                pledges = existing_user.get("pledges_count", 0)
                welcome_prefix = f"أهلاً بعودتك يا {first_name}! (سجلك يحتوي على {pledges} تعهد).\n{SEP}\n"
    except Exception as e: print(f"MongoDB Error in start: {e}")

    welcome_msg = welcome_prefix + "أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n👇 الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:"
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    except Exception as e: 
        print(f"Start Error: {e}")
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
    text = raw_text[:500] # حماية من النصوص الطويلة جداً
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    # 🔴 أوامر لوحة الإدارة 🔴
    if user_id == ADMIN_ID:
        if text == "📊 حالة قاعدة البيانات":
            try:
                df = get_excel_data()
                if df is None: return await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
                sample = df['stu_num'].dropna().unique()[:5]
                return await update.message.reply_text(f"📊 *كشاف البيانات:*\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام:\n`{', '.join(sample)}`", parse_mode='Markdown')
            except Exception as e: 
                print(f"DB Status Error: {e}")
                return await update.message.reply_text("⚠️ حدث خطأ في قراءة البيانات.")

        if text == "💾 سحب نسخة احتياطية":
            await update.message.reply_text("⏳ جاري التجهيز...")
            for f in ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json', 'plans.json']:
                if os.path.exists(f): 
                    try: await context.bot.send_document(chat_id=user_id, document=open(f, 'rb'))
                    except Exception as e: print(f"Backup Error for {f}: {e}")
            return

        if text == "📢 إرسال تعميم":
            user_states[user_id] = {'flow': 'broadcast'}
            return await update.message.reply_text("📢 أرسل نص التعميم الآن (أو اضغط إلغاء):", reply_markup=get_cancel_menu())

        if text == "📈 تقرير التميز المؤسسي":
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            stats = load_json(STATS_FILE)
            interrogations = load_json(INTERROGATIONS_FILE)
            users_count = len(stats.get("users_list", []))
            ai_queries = stats.get("ai_questions", 0)
            pledges_count = sum(len(subjects) for subjects in interrogations.values())
            
            db_records = 0; active_students_count = 0; weekly_attendance_rate = 100.0
            try: 
                df = get_excel_data()
                if df is not None:
                    db_records = len(df)
                    active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
                    active_students_count = active_rows['stu_num'].nunique()
                    valid_absence = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce').dropna()
                    if not valid_absence.empty: weekly_attendance_rate = round(100 - valid_absence.mean(), 2)
            except Exception as e: print(f"Report Excel Error: {e}")
            
            total_hours_saved = round(((ai_queries * 3) + (pledges_count * 15)) / 60, 1)
            report_msg = f"🏆 *تقرير الأداء لجائزة التميز بمنطقة القصيم* 🏆\n{SEP}\n👥 *المؤشرات الأكاديمية:*\n🔹 المتدربين المنتظمين: `{active_students_count}`\n🔹 نسبة الحضور: `{weekly_attendance_rate}%`\n\n📱 *التحول الرقمي:*\n🔹 المسجلين: `{users_count}`\n🔹 السجلات المؤتمتة: `{db_records}`\n\n📊 *الأثر الفعلي:*\n🔹 استشارات الذكاء الاصطناعي: `{ai_queries}`\n🔹 تعهدات نُفذت آلياً: `{pledges_count}`\n\n⏳ *توفير وقت الإدارة:* *{total_hours_saved} ساعة عمل!*"
            return await update.message.reply_text(report_msg, parse_mode='Markdown')

        if text == "📥 تصدير كشوفات الإكسل":
            await update.message.reply_text("⏳ جاري توليد كشف المحرومين والمنذرين...")
            try:
                df = get_excel_data()
                if df is None: return await update.message.reply_text("⚠️ لا توجد بيانات.")
                df['clean_parsnt'] = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce')
                warnings_df = df[(df['clean_parsnt'] >= 15) | (df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False))]
                if warnings_df.empty: return await update.message.reply_text("✅ القسم سليم، لا يوجد متدرب تجاوز 15%.")
                export_df = warnings_df[['stu_num', 'stu_nam', 'c_nam', 'parsnt']]
                export_df.columns = ['الرقم التدريبي', 'اسم المتدرب', 'المقرر', 'نسبة الغياب']
                export_df.to_excel("Warnings.xlsx", index=False)
                await context.bot.send_document(chat_id=user_id, document=open("Warnings.xlsx", 'rb'), caption=f"📊 *كشف الإنذارات والحرمان*\nالعدد: {len(export_df)}", parse_mode='Markdown')
                os.remove("Warnings.xlsx")
            except Exception as e: 
                print(f"Export Error: {e}")
                await update.message.reply_text(f"⚠️ حدث خطأ أثناء التصدير.")
            return

        if text == "🦞 مساعد OpenClaw":
            user_states[user_id] = {'flow': 'openclaw'}
            return await update.message.reply_text("🦞 **مرحباً بك في وحدة OpenClaw!**\nأرسل ملف CSV أو اسأل عن البيانات.", parse_mode='Markdown', reply_markup=get_back_menu())

    # 🔵 الحالات المستمرة (التعهدات وغيرها) 🔵
    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            menu = get_admin_menu() if user_id == ADMIN_ID and state.get('flow') in ['openclaw', 'broadcast'] else get_main_menu()
            return await update.message.reply_text("تم العودة 🏠", reply_markup=menu)

        if state['flow'] == 'broadcast':
            users = load_json(STATS_FILE).get("users_list", [])
            await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)}...")
            for u in users:
                try: 
                    await context.bot.send_message(chat_id=u, text=f"📢 *إعلان إداري هام:*\n{SEP}\n{text}", parse_mode='Markdown')
                    await asyncio.sleep(0.05) # حماية من الحظر
                except Exception as e: print(f"Broadcast failed for {u}: {e}")
            del user_states[user_id]
            return await update.message.reply_text("✅ تم إرسال التعميم.", reply_markup=get_admin_menu())

        if state['flow'] == 'openclaw':
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            try:
                response = requests.post(OPENCLAW_URL, json={"message": text}, timeout=20)
                await update.message.reply_text(response.json().get("response", "تم الاستلام."), parse_mode='Markdown')
            except Exception as e: 
                print(f"OpenClaw Chat Error: {e}")
                await update.message.reply_text(f"⚠️ تعذر الاتصال بخادم OpenClaw.")
            return

        if state['flow'] == 'pledge':
            step = state['step']
            if step == 1:
                user_states[user_id]['step'] = 2
                return await update.message.reply_text("2️⃣ *فضلاً، اختر العذر الرئيسي لكثرة غياباتك:*", parse_mode='Markdown', reply_markup=get_pledge_step2_menu())
            elif step == 2:
                if len(text) < 4: return await update.message.reply_text("⚠️ العذر غير واضح، اختر من الأزرار أو اكتبه:", reply_markup=get_pledge_step2_menu())
                user_states[user_id]['excuse'] = text
                user_states[user_id]['step'] = 3
                return await update.message.reply_text("3️⃣ *الإقرار النهائي:*\nهل تتعهد بالانضباط لتفادي الحرمان (20%) وطي القيد؟", parse_mode='Markdown', reply_markup=get_pledge_step3_menu())
            elif step == 3:
                if "تعهد" not in text and "أقر" not in text and "نعم" not in text:
                    return await update.message.reply_text("⚠️ الرجاء الضغط على زر الإقرار للموافقة:", reply_markup=get_pledge_step3_menu())
                completed = load_json(INTERROGATIONS_FILE)
                completed.setdefault(state['stu_num'], []).append(state['subject'])
                save_json(INTERROGATIONS_FILE, completed)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                official_document = f"🏛️ **المعهد الصناعي الثانوي ببريدة**\n{SEP}\n📄 **وثيقة تعهد إلكتروني بالانضباط**\nأقر المتدرب / **{state['stu_nam']}**\nالرقم / **{state['stu_num']}**\nالمقرر / **{state['subject']}**\nالعذر: {state['excuse']}\n✅ مُعتمد ومُوقع إلكترونياً | ⏱️ {timestamp}"
                try: await context.bot.send_message(chat_id=GROUP_ID, text=official_document, parse_mode='Markdown')
                except Exception as e: print(f"Pledge Admin Send Error: {e}")
                del user_states[user_id]
                await update.message.reply_text(official_document, parse_mode='Markdown')
                return await update.message.reply_text("✅ *تم توثيق إقرارك.*", parse_mode='Markdown', reply_markup=get_main_menu())

        if state['flow'] == 'feedback':
            if len(text) < 15: return await update.message.reply_text("⚠️ الرسالة قصيرة جداً!", reply_markup=get_cancel_menu())
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 *شكوى/مقترح:*\nالمرسل: {update.effective_user.first_name}\nالنص: {text}", parse_mode='Markdown')
                del user_states[user_id]
                return await update.message.reply_text("✅ تم إرسال رسالتك للإدارة بسرية تامة.", reply_markup=get_main_menu())
            except Exception as e: 
                print(f"Feedback Error: {e}")
                del user_states[user_id]
                return await update.message.reply_text("⚠️ خطأ، حاول لاحقاً.", reply_markup=get_main_menu())

        if state['flow'] == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل حالياً.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم:\n\n{response.text}", reply_markup=get_back_menu())
            except Exception as e: 
                print(f"Gemini Chat Error: {e}")
                return await update.message.reply_text("⚠️ خطأ تقني، الخدمة مشغولة.", reply_markup=get_back_menu())

        if state['flow'] == 'excuse':
            return await update.message.reply_text("⚠️ هذا نص! الرجاء إرسال صورة العذر الطبي.", reply_markup=get_cancel_menu())

    # 🟢 أوامر المتدربين الشاملة 🟢
    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 الرجاء إرفاق (صورة العذر) الآن، واكتب (رقمك التدريبي) في الوصف.", reply_markup=get_cancel_menu())

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        return await update.message.reply_text("📬 اكتب رسالتك أو شكواك الآن وسوف تصل للإدارة بسرية...", reply_markup=get_cancel_menu())

    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        return await update.message.reply_text("🤖 اكتب أي سؤال تقني أو إداري وسأجيبك...", reply_markup=get_back_menu())

    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن (أرقام فقط)...")
    if text == "📚 الحقائب التدريبية": return await update.message.reply_text("📚 *الحقائب:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🔗 المنصات الإلكترونية": return await update.message.reply_text("🌐 *المنصات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")]]), parse_mode='Markdown')
    if text == "📍 موقع القسم": return await update.message.reply_text("📍 *الموقع:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *الأخبار:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📅 التقويم التدريبي": return await update.message.reply_photo(photo=open('calendar.jpg', 'rb')) if os.path.exists('calendar.jpg') else await update.message.reply_text("📅 جاري التحديث.")
    if text == "📘 دليل المتدرب": return await update.message.reply_document(document=open("trainee_guide.pdf", 'rb')) if os.path.exists("trainee_guide.pdf") else await update.message.reply_text("📘 جاري التحديث.")
    if text == "📄 الخطط التدريبية": return await update.message.reply_text("📄 *اختر الفصل:*", reply_markup=get_plans_menu(), parse_mode='Markdown')
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]: return await update.message.reply_text(f"{load_json('plans.json').get(text, 'جاري التحديث')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 تحميل", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🕹️ قسم الألعاب والإضافات": return await update.message.reply_text("🕹️ *اختر النشاط:*", reply_markup=get_games_menu(), parse_mode='Markdown')
    if text == "❓ الأسئلة الشائعة": return await update.message.reply_text("📌 الحرمان عند (20%).\n💳 المكافأة تتوقف إذا نزل المعدل عن (2.00).\n🎓 الاجتياز (50).")
    if text == "💡 نصيحة تقنية": return await update.message.reply_text(random.choice(TECH_TIPS))
    if text == "🌐 أخبار التقنية": return await update.message.reply_text("🌐 يمكنك تصفح التقنية عبر منصة X.")
    
    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        return await update.message.reply_text(f"❓ *تحدي الأسبوع:*\n{q['q']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: return await update.message.reply_text("📉 لا يوجد نقاط.")
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        return await update.message.reply_text(f"🏆 *البطل:* {top['name']}\n🌟 *النقاط:* {top['score']}", parse_mode='Markdown')

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        try:
            df = get_excel_data()
            if df is None: return await update.message.reply_text("⚠️ قاعدة البيانات غير متوفرة.")
            res = df[df['stu_num'] == clean_text]
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None; has_deprivation = False
                m = f"🎓 *السجل الأكاديمي*\n{SEP}\n👤 *الاسم:* {stu_nam}\n🔢 *الرقم:* {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    if raw_val in ['ح', 'ط'] or 'حرمان' in raw_val or 'طي' in raw_val:
                        display_val = "*حرمان/طي قيد* 🔴"
                        has_deprivation = True
                    else:
                        try:
                            val = float(raw_val)
                            if val >= 20: display_val = f"*{val}%* 🔴"; has_deprivation = True
                            elif val >= 15: display_val = f"*{val}%* ⚠️"; subject_to_interrogate = c_name_text if c_name_text not in completed_interrogations else None
                            else: display_val = f"*{val}%* 🟢"
                        except: display_val = f"*{raw_val}* ⚠️"
                    m += f"📖 {c_name_text}\n▫️ النتيجة: {display_val}\n\n"
                m += f"{SEP}\n💡 *الإنذار عند 15%، والحرمان 20%.*"
                await update.message.reply_text(m, parse_mode='Markdown')

                if subject_to_interrogate:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    return await update.message.reply_text(f"⚠️ *تنبيه!*\nتجاوزت الخطر (15%) في: *{subject_to_interrogate}*\n🛑 *النظام مغلق لإكمال الإقرار!*\nهل تعلم أنك اقتربت من الحرمان؟", parse_mode='Markdown', reply_markup=get_pledge_step1_menu())
                if has_deprivation: await update.message.reply_text("🛑 *تنبيه:* أنت محروم في مقرر أو أكثر.", parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except Exception as e:
            print(f"Query Error: {e}")
        return

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# ==========================================
# 7. محرك رفع الملفات (ذكاء الاصطناعي، رايات، أعذار)
# ==========================================
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id, {})
    
    if state.get('flow') == 'openclaw' and update.message.document and update.message.document.file_name.endswith('.csv'):
        status_msg = await update.message.reply_text("⏳ جاري تحميل البيانات لـ OpenClaw...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            in_memory = io.BytesIO()
            await file.download_to_memory(in_memory)
            res = requests.post(OPENCLAW_URL, json={"message": "حفظ_بيانات_رايات\n" + in_memory.getvalue().decode('utf-8')}, timeout=25)
            await status_msg.edit_text(res.json().get("response", "تم."), parse_mode='Markdown')
        except Exception as e: 
            print(f"OpenClaw Upload Error: {e}")
            await status_msg.edit_text(f"⚠️ خطأ أثناء المعالجة.")
        return

    # معالجة ملفات الإدارة (رايات)
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.xls', '.csv')):
        status_msg = await update.message.reply_text("⏳ جاري تحليل ملف رايات...")
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
                
                # تقرير الجودة
                if any('نسبة التحضير' in str(c) for c in df_raw.columns):
                    total_sections = len(df_raw)
                    col_prep = [c for c in df_raw.columns if 'نسبة التحضير' in str(c)][0]
                    unrecorded = df_raw[pd.to_numeric(df_raw[col_prep].astype(str).str.replace('%', ''), errors='coerce') < 100]
                    os.remove(temp_file)
                    return await status_msg.edit_text(f"📑 *تقرير الجودة*\nالشعب المحضرة: {total_sections - len(unrecorded)}\n⚠️ غير المحضرة: {len(unrecorded)}", parse_mode='Markdown')

                # تنظيف كشف الغياب
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
                df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
                df_clean.to_excel("data.xlsx", index=False)
                os.remove(temp_file)

            # إعادة تعيين الكاش فوراً بعد تحديث الملف
            global EXCEL_CACHE
            EXCEL_CACHE = None 
            
            github_status = backup_to_github("data.xlsx")
            await status_msg.edit_text(f"✅ *تم التحديث بنجاح!*\n🌐 {github_status}", parse_mode='Markdown')
        except Exception as e: 
            print(f"Admin File Upload Error: {e}")
            await status_msg.edit_text(f"⚠️ فشل التحديث.")
        return

    # ختم وصور الأعذار والمفتش الذكي
    if update.message.photo or update.message.document:
        caption_text = update.message.caption
        stu_id = ''.join(filter(str.isdigit, str(caption_text)))
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض!* ارفق الصورة واكتب *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
            
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري الفحص والختم...")
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ai_vision = "لم يتم تحليل الصورة بالذكاء الاصطناعي."
            if update.message.photo and HAS_PIL:
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                in_memory_img = io.BytesIO()
                await file.download_to_memory(in_memory_img)
                in_memory_img.seek(0)
                img = Image.open(in_memory_img)
                
                # فحص Gemini
                if ai_model:
                    try:
                        res = await ai_model.generate_content_async(["استخرج: اسم المستشفى، ومدة الإجازة بالأيام فقط.", img])
                        ai_vision = res.text
                    except Exception as e: print(f"Vision Error: {e}")

                # الختم
                width, height = img.size
                txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
                ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id} | DATE: {timestamp}", fill="white")
                txt_img = txt_img.resize((width, int(width * 50 / 1000)))
                img.paste(txt_img, (0, height - txt_img.height)) 
                
                output = io.BytesIO()
                img.save(output, format='JPEG')
                output.seek(0)
                await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 *عذر مختوم:*\nرقم: {stu_id}\n⏱️ {timestamp}\n🤖 *فحص الذكاء:* {ai_vision}", parse_mode='Markdown')
            else:
                await update.message.copy(chat_id=GROUP_ID)
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الإرسال للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة 🏠", reply_markup=get_main_menu())
        except Exception as e: 
            print(f"Excuse Processing Error: {e}")
            await status_msg.edit_text(f"⚠️ خطأ أثناء المعالجة.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ans_"):
        parts = query.data.split("_")
        q_idx, sel = int(parts[1]), int(parts[2])
        try:
            actual_question = QUESTIONS[q_idx]
            m = "🎉 *إجابة صحيحة!*" if sel == actual_question["answer"] else f"❌ *خاطئة!*"
            await query.edit_message_text(f"❓ *تحدي الأسبوع:*\n{actual_question['q']}\n{SEP}\n{m}", parse_mode='Markdown')
        except Exception as e: print(f"Callback Error: {e}")

def main():
    Thread(target=background_tasks, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النظام المدرع V2.1 (جاهز للعمل بكفاءة)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
