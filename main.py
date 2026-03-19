import os
import io
import base64
import requests
import pandas as pd
import json
import random
import time
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
# 1. الإعدادات والاتصال بقواعد البيانات
# ==========================================
MONGO_URI = os.getenv("MONGODB_URI")
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat"
TOKEN = os.environ.get("TOKEN") 
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
        print("✅ تم الاتصال بعقل البوت السحابي (MongoDB) بنجاح!")
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
        except: return {}
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

try:
    from questions_bank import QUESTIONS
except Exception as e:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

TECH_TIPS = ["💡 احرص دائماً على تحديث نظامك.", "🛡️ استخدم كلمات مرور معقدة."]

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

# ==========================================
# 2. المهام التي تعمل بالخلفية (الخميس وإعادة النقاط)
# ==========================================
def background_tasks():
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            stats = load_json(STATS_FILE)
            
            # 1. تصفير نقاط الأسبوع كل أحد
            if now.weekday() == 6 and stats.get("last_reset_date") != today_str:
                save_json(SCORES_FILE, {}) 
                stats["last_reset_date"] = today_str 
                save_json(STATS_FILE, stats)
                
            # 2. حصاد الخميس التلقائي (كل يوم خميس الساعة 14:00 بتوقيت السيرفر)
            # الخميس في بايثون هو 3 (الاثنين 0)
            if now.weekday() == 3 and now.hour == 14:
                if stats.get("last_thursday_report") != today_str:
                    report_text = f"🗓️ *حصاد الخميس التلقائي*\n{SEP}\nتم إغلاق أسبوع تدريبي جديد. استخدم أوامر الإدارة لمراجعة التقارير والمحرومين.\nنهاية أسبوع سعيدة يا رئيس القسم! ☕"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                    requests.post(url, json={"chat_id": ADMIN_ID, "text": report_text, "parse_mode": "Markdown"})
                    stats["last_thursday_report"] = today_str
                    save_json(STATS_FILE, stats)
                    
        except Exception as e: pass
        time.sleep(60) # فحص كل دقيقة

# ==========================================
# 3. لوحة القيادة السرية (الويب)
# ==========================================
class WebDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        db_records = 0
        active_students = 0
        if os.path.exists('data.xlsx'):
            try:
                df = pd.read_excel('data.xlsx', dtype=str)
                db_records = len(df)
                active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
                active_students = active_rows['stu_num'].nunique()
            except: pass
            
        stats = load_json(STATS_FILE)
        ai_q = stats.get("ai_questions", 0)
        
        html = f"""
        <html>
        <head>
            <title>لوحة القيادة - قسم الحاسب</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background: #f0f2f5; padding: 20px; direction: rtl; }}
                .header {{ color: #1e3a8a; margin-bottom: 30px; }}
                .card-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }}
                .card {{ background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); width: 250px; border-top: 5px solid #10b981; }}
                .card h3 {{ color: #6b7280; margin: 0 0 10px 0; font-size: 1.2rem; }}
                .card h2 {{ color: #111827; margin: 0; font-size: 2.5rem; }}
                .footer {{ margin-top: 40px; color: #9ca3af; font-size: 0.9rem; }}
            </style>
        </head>
        <body>
            <h1 class="header">📊 لوحة القيادة الحية | قسم الحاسب</h1>
            <div class="card-container">
                <div class="card" style="border-top-color: #3b82f6;"><h3>إجمالي السجلات المؤتمتة</h3><h2>{db_records}</h2></div>
                <div class="card" style="border-top-color: #10b981;"><h3>المتدربين المنتظمين</h3><h2>{active_students}</h2></div>
                <div class="card" style="border-top-color: #8b5cf6;"><h3>استشارات الذكاء الاصطناعي</h3><h2>{ai_q}</h2></div>
            </div>
            <div class="footer">تم إنشاء هذه اللوحة آلياً بواسطة بوت المعهد الصناعي الثانوي © 2026</div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebDashboardHandler)
    server.serve_forever()

# ==========================================
# 4. إعدادات الذكاء الاصطناعي (Gemini)
# ==========================================
AI_KNOWLEDGE = (
    "أنت 'المساعد الرقمي'، مساعد ذكي ورسمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "مهمتك الإجابة بشكل مبسط ومختصر جداً.\n"
    "الإنذار عند غياب 15%، الحرمان 20%. المكافأة 800 ريال وتتوقف للـ 2.00. درجة الاجتياز 50.\n"
    "🚨 اختم الإجابات عن الأنظمة بعبارة:\n💡 *للمزيد من التفاصيل، يرجى تحميل (دليل المتدرب) من القائمة الرئيسية.*"
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
    except: pass

user_states = {}
active_challenges = {}

# ==========================================
# 5. القوائم التفاعلية
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
def get_pledge_step2_menu(): return ReplyKeyboardMarkup([["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], ["🚗 مشكلة مواصلات", "⚙️ أخرى"], ["❌ إلغاء العملية"]], resize_keyboard=True)
def get_pledge_step3_menu(): return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)
def get_games_menu(): return ReplyKeyboardMarkup([["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], ["💡 نصيحة تقنية", "🌐 أخبار التقنية"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_plans_menu(): return ReplyKeyboardMarkup([["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"], ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"], ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"], ["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# ==========================================
# 6. أوامر البداية والإدارة الموحدة
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user = update.effective_user
    user_id = str(user.id)
    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_msg = f"أهلاً بك يا {user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n👇 الرجاء اختيار الخدمة المطلوبة:"
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def admin_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم المتقدمة 🛡️", reply_markup=get_admin_menu())

# ==========================================
# 7. المعالجة المنطقية للنصوص (المتدربين + الإدارة)
# ==========================================
async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    # ------------------------------------------
    # 🛡️ أوامر لوحة الإدارة (للمدير فقط)
    # ------------------------------------------
    if user_id == ADMIN_ID:
        if text == "📊 حالة قاعدة البيانات":
            try:
                if not os.path.exists('data.xlsx'): return await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
                df = pd.read_excel('data.xlsx', dtype=str)
                sample = df['stu_num'].dropna().unique()[:5]
                return await update.message.reply_text(f"📊 *كشاف البيانات:*\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام:\n`{', '.join(sample)}`", parse_mode='Markdown')
            except: return

        if text == "💾 سحب نسخة احتياطية":
            await update.message.reply_text("⏳ جاري التجهيز...")
            for f in ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json']:
                if os.path.exists(f): await context.bot.send_document(chat_id=user_id, document=open(f, 'rb'))
            return

        if text == "📢 إرسال تعميم":
            user_states[user_id] = {'flow': 'broadcast'}
            return await update.message.reply_text("📢 أرسل نص التعميم الآن (أو اضغط إلغاء):", reply_markup=get_cancel_menu())

        if text == "📈 تقرير التميز المؤسسي":
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            stats, interrogations = load_json(STATS_FILE), load_json(INTERROGATIONS_FILE)
            active_students = 0
            if os.path.exists('data.xlsx'):
                try: 
                    df = pd.read_excel('data.xlsx', dtype=str)
                    active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
                    active_students = active_rows['stu_num'].nunique()
                except: pass
            
            report_msg = f"🏆 *تقرير الأداء*\n{SEP}\n👥 إجمالي المتدربين النشطين: `{active_students}`\n📱 المسجلين بالبوت: `{len(stats.get('users_list', []))}`\n🤖 استشارات الذكاء الاصطناعي: `{stats.get('ai_questions', 0)}`"
            return await update.message.reply_text(report_msg, parse_mode='Markdown')

        if text == "📥 تصدير كشوفات الإكسل":
            await update.message.reply_text("⏳ جاري توليد كشف المحرومين والمنذرين...")
            try:
                if not os.path.exists('data.xlsx'): return await update.message.reply_text("⚠️ لا توجد بيانات.")
                df = pd.read_excel('data.xlsx', dtype=str)
                df['clean_parsnt'] = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce')
                warnings_df = df[(df['clean_parsnt'] >= 15) | (df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False))]
                if warnings_df.empty: return await update.message.reply_text("✅ القسم سليم، لا يوجد متدرب تجاوز 15%.")
                export_df = warnings_df[['stu_num', 'stu_nam', 'c_nam', 'parsnt']]
                export_df.columns = ['الرقم التدريبي', 'اسم المتدرب', 'المقرر', 'نسبة الغياب']
                export_df.to_excel("Warnings.xlsx", index=False)
                await context.bot.send_document(chat_id=user_id, document=open("Warnings.xlsx", 'rb'), caption=f"📊 *كشف الإنذارات والحرمان*\nعدد الحالات: {len(export_df)}", parse_mode='Markdown')
                os.remove("Warnings.xlsx")
            except Exception as e: await update.message.reply_text(f"⚠️ خطأ: {e}")
            return

        if text == "🦞 مساعد OpenClaw":
            user_states[user_id] = {'flow': 'openclaw'}
            return await update.message.reply_text("🦞 **وحدة OpenClaw:**\nأرسل ملف CSV أو اسأل عن البيانات.", parse_mode='Markdown', reply_markup=get_back_menu())

    # ------------------------------------------
    # 🔄 الحالات المستمرة (States)
    # ------------------------------------------
    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            menu = get_admin_menu() if user_id == ADMIN_ID and text == "🔙 الرجوع للقائمة الرئيسية" and state.get('flow') in ['openclaw', 'broadcast'] else get_main_menu()
            return await update.message.reply_text("تم العودة 🏠", reply_markup=menu)

        if state['flow'] == 'broadcast':
            users = load_json(STATS_FILE).get("users_list", [])
            await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)} متدرب...")
            for u in users:
                try: await context.bot.send_message(chat_id=u, text=f"📢 *إعلان إداري هام:*\n{SEP}\n{text}", parse_mode='Markdown')
                except: pass
            del user_states[user_id]
            return await update.message.reply_text("✅ تم إرسال التعميم بنجاح.", reply_markup=get_admin_menu())

        if state['flow'] == 'openclaw':
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            try:
                response = requests.post(OPENCLAW_URL, json={"message": text}, timeout=60)
                await update.message.reply_text(response.json().get("response", "حدث خطأ."), parse_mode='Markdown')
            except Exception as e: await update.message.reply_text(f"⚠️ خطأ: {str(e)}")
            return

        if state['flow'] == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم:\n\n{response.text}", reply_markup=get_back_menu())
            except: return await update.message.reply_text("⚠️ خطأ تقني.", reply_markup=get_back_menu())

    # ------------------------------------------
    # 📋 أوامر المتدربين
    # ------------------------------------------
    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        return await update.message.reply_text("🤖 اكتب أي سؤال تقني أو إداري وسأجيبك فوراً...", reply_markup=get_back_menu())

    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 الرجاء إرفاق (صورة العذر) الآن، وكتابة (رقمك التدريبي) في الوصف.", reply_markup=get_cancel_menu())

    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن (أرقام فقط)...")
    if text == "📚 الحقائب التدريبية": return await update.message.reply_text(f"📚 *مستودع الحقائب:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "📍 موقع القسم": return await update.message.reply_text("📍 *موقع القسم:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *حساب المعهد:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "🕹️ قسم الألعاب والإضافات": return await update.message.reply_text("🕹️ *اختر النشاط المطلوب:*", reply_markup=get_games_menu(), parse_mode='Markdown')
    if text == "💡 نصيحة تقنية": return await update.message.reply_text(random.choice(TECH_TIPS))

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'): return await update.message.reply_text("⚠️ لا يوجد بيانات.")
            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            if not res.empty:
                m = f"👤 *المتدرب:* {res.iloc[0]['stu_nam']}\n🔢 *الرقم:* {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    m += f"📖 {str(r.get('c_nam', ''))}\n▫️ النتيجة: *{str(r.get('parsnt', '0'))}*\n\n"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: pass
        return

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# ==========================================
# 8. معالجة الملفات والصور (الرصد، الأعذار، وذكاء Gemini)
# ==========================================
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id, {})
    
    # -- رفع رايات لـ OpenClaw --
    if state.get('flow') == 'openclaw' and update.message.document:
        if update.message.document.file_name.endswith('.csv'):
            status_msg = await update.message.reply_text("⏳ جاري الإرسال لـ OpenClaw...")
            try:
                file = await context.bot.get_file(update.message.document.file_id)
                in_memory = io.BytesIO()
                await file.download_to_memory(in_memory)
                response = requests.post(OPENCLAW_URL, json={"message": "حفظ_بيانات_رايات\n" + in_memory.getvalue().decode('utf-8')}, timeout=60)
                await status_msg.edit_text(response.json().get("response", "تم."), parse_mode='Markdown')
            except Exception as e: await status_msg.edit_text(f"⚠️ خطأ: {str(e)}")
        return

    # -- المفتش الذكي للأعذار الطبية (AI Vision) + الختم --
    if update.message.photo or update.message.document:
        caption_text = update.message.caption
        stu_id = ''.join(filter(str.isdigit, str(caption_text)))
        
        # السماح للمدير برفع ملفات الجودة والإكسل بدون تعقيد
        if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.csv')):
            status_msg = await update.message.reply_text("⏳ تم استلام ملف الإدارة، جاري التحديث...")
            try:
                file = await context.bot.get_file(update.message.document.file_id)
                await file.download_to_drive("data.xlsx")
                df_clean = pd.read_excel('data.xlsx')
                await status_msg.edit_text(f"✅ *تم التحديث السريع بنجاح.*\nتم حفظ `{len(df_clean)}` سجل.", parse_mode='Markdown')
            except Exception as e: await status_msg.edit_text(f"⚠️ فشل التحديث: {e}")
            return

        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض!* يجب إرفاق الصورة وكتابة *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
            
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري الفحص والختم الآلي...")
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ai_vision_summary = "لم يتم تحليل الصورة بالذكاء الاصطناعي."
            
            if update.message.photo and HAS_PIL:
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                in_memory_img = io.BytesIO()
                await file.download_to_memory(in_memory_img)
                in_memory_img.seek(0)
                
                img = Image.open(in_memory_img)
                
                # 👁️ تشغيل ذكاء Gemini لقرائة العذر (المفتش الذكي)
                if ai_model:
                    try:
                        vision_prompt = "أنت مساعد إداري صارم. استخرج من هذا العذر الطبي فقط: 1- اسم المستشفى 2- مدة الإجازة بالأيام 3- تاريخ البداية. إذا لم يكن عذراً طبياً اكتب 'مرفوض: ليس عذراً طبياً'."
                        response = await ai_model.generate_content_async([vision_prompt, img])
                        ai_vision_summary = response.text
                    except: pass

                # 🖨️ الختم الآلي
                width, height = img.size
                txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
                ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id} | DATE: {timestamp}", fill="white")
                txt_img = txt_img.resize((width, int(width * 50 / 1000)))
                img.paste(txt_img, (0, height - txt_img.height)) 
                
                output = io.BytesIO()
                img.save(output, format='JPEG')
                output.seek(0)
                
                admin_caption = f"📥 *عذر مختوم:*\nرقم المتدرب: {stu_id}\n⏱️ {timestamp}\n{SEP}\n🤖 *فحص الذكاء الاصطناعي:*\n{ai_vision_summary}"
                await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=admin_caption, parse_mode='Markdown')
            else:
                await update.message.copy(chat_id=GROUP_ID)
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الاعتماد والإرسال للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
        except Exception as e:
            await status_msg.edit_text("⚠️ حدث خطأ فني أثناء الرفع.", parse_mode='Markdown')

def main():
    Thread(target=background_tasks, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تشغيل الإصدار الماسي (الويب + الذكاء الشامل + لوحة الإدارة الموحدة)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
