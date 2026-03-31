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

# 🟢 استدعاء خدمات الذكاء الاصطناعي المربوطة بالقاعدة 🟢
from ai_service import extract_text_from_pdf_bytes, save_knowledge_to_db, build_ai_prompt

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
        except: return None
    return EXCEL_CACHE

def build_weekly_report():
    try:
        if not os.path.exists("so09.csv"): return "⚠️ لم يتم رفع إحصائيات الشعب (SO09) حتى الآن."
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
        
        trainers_df = df_so09.groupby(col_trainer).agg(total_sec=(col_section, 'count'), prep_sec=(col_prep, lambda x: (x >= 100).sum())).reset_index()
        total_trainers = len(trainers_df)
        fully_prepared_trainers = len(trainers_df[trainers_df['total_sec'] == trainers_df['prep_sec']])
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_trainers = len(late_trainers_df)
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({int(row['total_sec'] - row['prep_sec'])} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "لا يوجد تأخير، جميع المدربين أتموا الرصد ✅"
        
        avg_attendance_perc = df_so09[col_prep].mean()
        
        df_trainees = get_excel_data()
        total_trainees = 0; present_trainees = 0; deprived_count = 0; expelled_count = 0
        if df_trainees is not None:
            total_trainees = df_trainees['stu_num'].nunique()
            df_trainees['clean_parsnt'] = pd.to_numeric(df_trainees['parsnt'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            deprived_mask = (df_trainees['clean_parsnt'] >= 20) | (df_trainees['parsnt'].str.contains('ح|حرمان', na=False))
            expelled_mask = df_trainees['parsnt'].str.contains('ط|طي', na=False)
            deprived_count = df_trainees[deprived_mask]['stu_num'].nunique()
            expelled_count = df_trainees[expelled_mask]['stu_num'].nunique()
            present_trainees = int((avg_attendance_perc / 100) * total_trainees)
            
        current_week = datetime.now().isocalendar()[1]

        report = f"""📑 *تقرير سير العملية التدريبية الأسبوعية* 📑\n📅 الأسبوع التدريبي: `{current_week}`\n{SEP}\n👥 *إحصائيات المتدربين والحضور:*\n▫️ إجمالي المتدربين بالقسم: `{total_trainees}`\n▫️ المتدربين الحاضرين: `{present_trainees}`\n📈 نسبة الحضور الأسبوعية: `{avg_attendance_perc:.2f}%`\n\n🛑 *مؤشرات الخطر الأكاديمي:*\n⚠️ المتدربين المحرومين: `{deprived_count}`\n❌ طي القيد / منسحبين: `{expelled_count}`\n\n📝 *إحصائيات الشعب التدريبية:*\n▫️ إجمالي عدد الشعب: `{total_sections}`\n✅ الشعب المحضرة: `{prepared_sections}`\n⚠️ الشعب غير المحضرة: `{unprepared_sections}`\n\n👨‍🏫 *إحصائيات المدربين:*\n▫️ إجمالي عدد المدربين: `{total_trainers}`\n✅ المدربين المحضرين: `{fully_prepared_trainers}`\n⚠️ المدربين المتأخرين: `{late_trainers}`\n{SEP}\n📋 *المدربين المتأخرين بالرصد:*\n{late_list_text}"""
        return report
    except Exception as e: return f"⚠️ خطأ في المعالجة: {e}"

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
def get_plans_menu(): return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_games_menu(): return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user = update.effective_user
    user_id = str(user.id)
    try: users_col.update_one({"telegram_id": user_id}, {"$set": {"first_name": user.first_name, "username": user.username, "last_active": datetime.now()}}, upsert=True)
    except: pass
    
    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
        
    if user_id in user_states: del user_states[user_id]
    welcome_msg = f"أهلاً بك يا {user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n👇 الرجاء اختيار الخدمة المطلوبة:"
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def admin_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم المتقدمة 🛡️", reply_markup=get_admin_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    raw_text = update.message.text.strip()
    text = raw_text[:500] 
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    if user_id == ADMIN_ID:
        if text == "📑 تقرير سير العملية الأسبوعية":
            return await update.message.reply_text(build_weekly_report(), parse_mode='Markdown')
        if text == "📊 حالة قاعدة البيانات":
            try:
                df = get_excel_data()
                db_users = users_col.count_documents({})
                excel_records = len(df) if df is not None else 0
                kb_docs = db["knowledge_base"].count_documents({})
                return await update.message.reply_text(f"📊 *كشاف البيانات:*\n✅ عدد الطلاب بالبوت: {db_users}\n📥 سجلات الإكسل: {excel_records}\n🧠 ملفات الذكاء الاصطناعي: {kb_docs}", parse_mode='Markdown')
            except Exception as e: return await update.message.reply_text("⚠️ خطأ في القراءة.")
        if text == "💾 سحب نسخة احتياطية":
            await update.message.reply_text("⏳ جاري التجهيز...")
            for f in ['data.xlsx', 'so09.csv', 'scores.json', 'stats.json']:
                if os.path.exists(f): 
                    try: await context.bot.send_document(chat_id=user_id, document=open(f, 'rb'))
                    except: pass
            return
        if text == "📢 إرسال تعميم":
            user_states[user_id] = {'flow': 'broadcast'}
            return await update.message.reply_text("📢 أرسل نص التعميم الآن:", reply_markup=get_cancel_menu())
        if text == "📈 تقرير التميز المؤسسي":
            db_records = len(get_excel_data()) if get_excel_data() is not None else 0
            db_users = users_col.count_documents({})
            report_msg = f"🏆 *تقرير الأداء لجائزة التميز* 🏆\n{SEP}\n👥 المسجلين في البوت: `{db_users}`\n🔹 السجلات المؤتمتة: `{db_records}`"
            return await update.message.reply_text(report_msg, parse_mode='Markdown')
        if text == "📥 تصدير كشوفات الإكسل":
            await update.message.reply_text("⏳ جاري التصدير...")
            try:
                df = get_excel_data()
                if df is None: return await update.message.reply_text("⚠️ لا توجد بيانات.")
                df['clean_parsnt'] = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
                warnings_df = df[(df['clean_parsnt'] >= 15) | (df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False))]
                if warnings_df.empty: return await update.message.reply_text("✅ القسم سليم، لا يوجد متدرب تجاوز 15%.")
                export_df = warnings_df[['stu_num', 'stu_nam', 'c_nam', 'parsnt']]
                export_df.columns = ['الرقم التدريبي', 'اسم المتدرب', 'المقرر', 'نسبة الغياب']
                export_df.to_excel("Warnings.xlsx", index=False)
                await context.bot.send_document(chat_id=user_id, document=open("Warnings.xlsx", 'rb'), caption=f"📊 *كشف الإنذارات والحرمان*\nالعدد: {len(export_df)}", parse_mode='Markdown')
                os.remove("Warnings.xlsx")
            except Exception as e: await update.message.reply_text(f"⚠️ حدث خطأ أثناء التصدير.")
            return
        if text == "🧠 تحليل الجودة بالذكاء الاصطناعي":
            if not ai_model: return await update.message.reply_text("⚠️ الذكاء الاصطناعي غير مفعل.")
            await update.message.reply_text("⏳ جاري تحليل تقارير الجودة...")
            try:
                res = await ai_model.generate_content_async("بناءً على تقارير رضا المتدربين، لخص لي نقاط القوة والضعف في قسم الحاسب في 3 نقاط إدارية للتميز المؤسسي.")
                return await update.message.reply_text(f"🧠 *تحليل الجودة:*\n\n{res.text}", parse_mode='Markdown')
            except Exception as e: return await update.message.reply_text(f"⚠️ فشل التحليل.")

    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            menu = get_admin_menu() if user_id == ADMIN_ID and state.get('flow') == 'broadcast' else get_main_menu()
            return await update.message.reply_text("تم العودة 🏠", reply_markup=menu)

        if state['flow'] == 'broadcast':
            users = load_json(STATS_FILE).get("users_list", [])
            await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)}...")
            for u in users:
                try: await context.bot.send_message(chat_id=u, text=f"📢 *إعلان إداري هام:*\n{SEP}\n{text}", parse_mode='Markdown'); await asyncio.sleep(0.05) 
                except: pass
            del user_states[user_id]
            return await update.message.reply_text("✅ تم إرسال التعميم.", reply_markup=get_admin_menu())

        if state['flow'] == 'feedback':
            if len(text) < 15: return await update.message.reply_text("⚠️ الرسالة قصيرة جداً!", reply_markup=get_cancel_menu())
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 *شكوى/مقترح:*\nالمرسل: {update.effective_user.first_name}\nالنص: {text}", parse_mode='Markdown')
                del user_states[user_id]
                return await update.message.reply_text("✅ تم إرسال رسالتك للإدارة بسرية تامة.", reply_markup=get_main_menu())
            except: 
                del user_states[user_id]
                return await update.message.reply_text("⚠️ خطأ، حاول لاحقاً.", reply_markup=get_main_menu())

        # 🟢 محادثة الذكاء الاصطناعي المرتبطة بـ MongoDB 🟢
        if state['flow'] == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل حالياً بسبب نقص المفتاح.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            try:
            
            
                    # 🟢 محادثة الذكاء الاصطناعي المرتبطة بـ MongoDB 🟢
        if state['flow'] == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل حالياً بسبب نقص المفتاح.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            try:
                final_prompt = build_ai_prompt(db, AI_KNOWLEDGE, text)
                response = await ai_model.generate_content_async(final_prompt)
                return await update.message.reply_text(f"📝 المستشار الأكاديمي:\n\n{response.text}", reply_markup=get_back_menu())
            except Exception as e: 
                # 🟢 التعديل هنا: خلينا البوت ينطق بالخطأ الحقيقي عشان نصيده
                error_msg = str(e)[:250] # نأخذ أول 250 حرف من الخطأ
                return await update.message.reply_text(f"⚠️ تفاصيل الخطأ التقني:\n{error_msg}", reply_markup=get_back_menu())

            
        if state['flow'] == 'excuse':
            return await update.message.reply_text("⚠️ هذا نص! الرجاء إرسال صورة العذر الطبي.", reply_markup=get_cancel_menu())

    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 الرجاء إرفاق (صورة العذر) الآن، واكتب (رقمك التدريبي) في الوصف.", reply_markup=get_cancel_menu())

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        return await update.message.reply_text("📬 اكتب رسالتك أو شكواك الآن وسوف تصل للإدارة بسرية...", reply_markup=get_cancel_menu())

    if text == "🤖 المعلم الذكي (مستشار القسم)":
        user_states[user_id] = {'flow': 'ai'}
        return await update.message.reply_text("🤖 أنا المستشار الأكاديمي.. اسألني عن أي استفسار يخص اللوائح والأدلة الرسمية!", reply_markup=get_back_menu())

    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن (أرقام فقط)...")
    if text == "📚 الحقائب التدريبية": return await update.message.reply_text("📚 *الحقائب:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🔗 المنصات الإلكترونية": return await update.message.reply_text("🌐 *المنصات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")]]), parse_mode='Markdown')
    if text == "📍 موقع القسم": return await update.message.reply_text("📍 *الموقع:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *الأخبار:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📅 التقويم التدريبي": return await update.message.reply_photo(photo=open('calendar.pdf', 'rb')) if os.path.exists('calendar.jpg') else await update.message.reply_text("📅 جاري التحديث.")
    
    if text == "📘 دليل المتدرب": 
        if os.path.exists("trainee_guide.pdf"): return await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 *دليل المتدرب الرسمي*", parse_mode='Markdown')
        else: return await update.message.reply_text("📘 *دليل المتدرب*\nالرجاء التأكد من رفع ملف الدليل.", parse_mode='Markdown')

    if text == "📄 الخطط التدريبية": return await update.message.reply_text("📄 *اختر الفصل:*", reply_markup=get_plans_menu(), parse_mode='Markdown')
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"]: return await update.message.reply_text(f"{load_json('plans.json').get(text, 'جاري التحديث')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 تحميل", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🕹️ قسم الألعاب والتقنية": return await update.message.reply_text("🕹️ *اختر النشاط:*", reply_markup=get_games_menu(), parse_mode='Markdown')
    if text == "❓ الأسئلة الشائعة": return await update.message.reply_text("📌 الحرمان عند (20%).\n💳 المكافأة تتوقف إذا نزل المعدل عن (2.00).\n🎓 الاجتياز (50).\n\n💡 *اسأل (المعلم الذكي) لتفاصيل أكثر!*", parse_mode='Markdown')
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
                try: users_col.update_one({"telegram_id": user_id}, {"$set": {"stu_num": clean_text, "stu_nam": stu_nam}}, upsert=True)
                except: pass
                
                m = f"🎓 *السجل الأكاديمي*\n{SEP}\n👤 *الاسم:* {stu_nam}\n🔢 *الرقم:* {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    if raw_val in ['ح', 'ط'] or 'حرمان' in raw_val or 'طي' in raw_val:
                        display_val = "*حرمان/طي قيد* 🔴"
                    else:
                        try:
                            val = float(raw_val)
                            if val >= 20: display_val = f"*{val}%* 🔴"
                            elif val >= 15: display_val = f"*{val}%* ⚠️"
                            else: display_val = f"*{val}%* 🟢"
                        except: display_val = f"*{raw_val}* ⚠️"
                    m += f"📖 {c_name_text}\n▫️ النتيجة: {display_val}\n\n"
                m += f"{SEP}\n💡 *الإنذار عند 15%، والحرمان 20%.*"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: pass
        return

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    doc = update.message.document
    
    # 🟢 1. رفع ملفات PDF للذكاء الاصطناعي (خاص بالأدمن) 🟢
    if user_id == ADMIN_ID and doc and doc.file_name.lower().endswith('.pdf'):
        status_msg = await update.message.reply_text(f"⏳ جاري قراءة ملف `{doc.file_name}` لاستخراج النصوص وتلقين الذكاء الاصطناعي...")
        try:
            file = await context.bot.get_file(doc.file_id)
            pdf_bytes = await file.download_as_bytearray()
            
            # استخراج النص وحفظه في MongoDB
            text = extract_text_from_pdf_bytes(pdf_bytes)
            if text.strip():
                save_knowledge_to_db(db, doc.file_name, text)
                await status_msg.edit_text(f"✅ تم استخراج النصوص من `{doc.file_name}` وحفظها في قاعدة البيانات بنجاح!\n🧠 البوت الآن صار أذكى ويقدر يجاوب من هذا الملف للأبد.", parse_mode='Markdown')
            else:
                await status_msg.edit_text("⚠️ لم يتم العثور على نصوص قابلة للقراءة في هذا الملف (الصور داخل الـ PDF لا تُقرأ).")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ فشل في معالجة ملف PDF: {e}")
        return

    # 🟢 2. معالجة ملفات الإكسل (رايات) 🟢
    if user_id == ADMIN_ID and doc and doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
        status_msg = await update.message.reply_text("⏳ جاري تحليل وتصنيف التقرير المرفوع تلقائياً...")
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
                current_week = datetime.now().isocalendar()[1]
                
                if 'اسم المدرب' in df_raw.columns and 'نسبة التحضير' in df_raw.columns:
                    df_raw.to_csv("so09.csv", index=False)
                    os.remove(temp_file)
                    report_text = build_weekly_report()
                    try: reports_col.insert_one({"type": "SO09", "week_number": current_week, "date": datetime.now(), "total_sections": len(df_raw)})
                    except: pass
                    return await status_msg.edit_text(report_text, parse_mode='Markdown')

                elif 'اسم المتدرب' in df_raw.columns and 'إجمالي نسبة الغياب بعذر وبدون عذر' in df_raw.columns:
                    df_clean = pd.DataFrame()
                    df_clean['c_nam'] = df_raw['اسم المقرر'].astype(str)
                    df_clean['stu_num'] = df_raw['رقم المتدرب'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                    df_clean['stu_nam'] = df_raw['اسم المتدرب'].astype(str)
                    df_clean['parsnt'] = df_raw['إجمالي نسبة الغياب بعذر وبدون عذر'].astype(str)
                    
                    df_clean = df_clean[df_clean['stu_num'].str.len() >= 5]
                    df_clean.to_excel("data.xlsx", index=False)
                    os.remove(temp_file)
                    
                    global EXCEL_CACHE
                    EXCEL_CACHE = None 
                    try: reports_col.insert_one({"type": "Trainees_Absence", "week_number": current_week, "date": datetime.now(), "total_records": len(df_clean)})
                    except: pass
                    return await status_msg.edit_text(f"✅ *تم تحديث بيانات الطلاب بنجاح!*\nتم رفع وتوثيق {len(df_clean)} سجل في الأرشيف (أسبوع {current_week}).", parse_mode='Markdown')
                
                else:
                    os.remove(temp_file)
                    return await status_msg.edit_text("⚠️ لم يتعرف النظام على نوع الملف، يرجى سحب التقرير الصحيح من رايات.")

        except Exception as e: 
            await status_msg.edit_text(f"⚠️ فشل التحديث: {e}")
        return

    # 🟢 3. حفظ الأعذار الطبية 🟢
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
            try: excuses_col.insert_one({"telegram_id": user_id, "stu_num": stu_id, "date": timestamp, "file_id": file_id, "status": "مستلم"})
            except: pass
            await context.bot.send_photo(chat_id=GROUP_ID, photo=file_id, caption=f"📥 *عذر جديد مُوثق:*\nرقم المتدرب: {stu_id}\n⏱️ وقت الرفع: {timestamp}", parse_mode='Markdown')
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الحفظ وإرسال العذر للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة 🏠", reply_markup=get_main_menu())
        except Exception as e: 
            await status_msg.edit_text(f"⚠️ خطأ أثناء المعالجة.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ans_"):
        parts = query.data.split("_")
        q_idx, sel = int(parts[1]), int(parts[2])
        try:
            actual_question = QUESTIONS[q_idx]
            m = "🎉 *إجابة صحيحة!*" if sel == actual_question["answer"] else f"❌ *خاطئة!*"
            await query.edit_message_text(f"❓ *تحدي الأسبوع:*\n{actual_question['q']}\n{SEP}\n{m}", parse_mode='Markdown')
        except Exception as e: pass

def main():
    Thread(target=background_tasks, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النظام الخارق V4.1 (مع ربط الذكاء الاصطناعي بقاعدة MongoDB)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
