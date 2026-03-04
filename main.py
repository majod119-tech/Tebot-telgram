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
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 🌟 استدعاء مكتبة الصور للختم الآلي ---
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

TECH_TIPS = [
    "💡 نصيحة أمنية: استخدم مفتاحي (Win + L) لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ نصيحة تقنية: احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات.",
    "🚀 نصيحة برمجية: التنسيق والمسافات البادئة في لغة بايثون هي أساس عمل الكود.",
    "💾 نصيحة: احرص دائماً على أخذ نسخة احتياطية لملفاتك المهمة.",
    "🌐 نصيحة: تجنب الاتصال بشبكات الواي فاي العامة المفتوحة بدون VPN."
]

# --- 🌟 إعدادات النظام ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

def auto_reset_scores():
    while True:
        try:
            now = datetime.now()
            if now.weekday() == 6: 
                today_str = now.strftime("%Y-%m-%d")
                stats = load_json(STATS_FILE)
                if stats.get("last_reset_date") != today_str:
                    save_json(SCORES_FILE, {}) 
                    stats["last_reset_date"] = today_str 
                    save_json(STATS_FILE, stats)
        except: pass
        time.sleep(3600)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Server Online.")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def backup_to_github(file_path="data.xlsx"):
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    if not github_token or not github_repo: return "⚠️ (حفظ محلي مؤقت، السحابة غير مربوطة)."
    
    url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    try:
        sha = None
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200: sha = resp.json().get("sha")
        with open(file_path, "rb") as f: content = base64.b64encode(f.read()).decode("utf-8")
        data = {"message": f"تحديث قاعدة البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content}
        if sha: data["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=data)
        if put_resp.status_code in [200, 201]: return "✅ **تم التثبيت الدائم في GitHub!**"
        else: return "⚠️ فشل الرفع لـ GitHub."
    except: return "⚠️ خطأ بالاتصال بـ GitHub."

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
    except: pass

user_states = {}
active_challenges = {}

# --- 🌟 القوائم التفاعلية 🌟 ---
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

def get_cancel_menu():
    return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)

def get_plans_menu():
    return ReplyKeyboardMarkup([
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"],
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"],
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"],
        ["🖥️ برامج فصلية", "🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_games_menu():
    return ReplyKeyboardMarkup([
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"],
        ["💡 نصيحة تقنية", "🌐 أخبار التقنية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_back_menu(): 
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

def get_pledge_step1_menu():
    return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)

def get_pledge_step2_menu():
    return ReplyKeyboardMarkup([
        ["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"],
        ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"],
        ["❌ إلغاء العملية"]
    ], resize_keyboard=True)

def get_pledge_step3_menu():
    return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)

# --- 🌟 أوامر الإدارة 🌟 ---
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    msg = f"""
🏆 **نبذة عن المبادرة (جائزة التميز بمنطقة القصيم)** 🏆
{SEP}
ابتكار تقني يخدم منظومة التدريب التقني والمهني، مصمم خصيصاً لتحقيق معايير التميز المؤسسي من خلال:

1️⃣ **التحول الرقمي:** أتمتة كاملة للاستعلامات الإدارية ورفع الأعذار إلكترونياً.
2️⃣ **الكفاءة التشغيلية:** تقليص وقت معالجة طلبات المتدربين من ساعات إلى ثوانٍ، وأتمتة تقارير الجودة الأسبوعية.
3️⃣ **الاستدامة:** نظام سحابي يعمل 24/7 دون أعباء تشغيلية، مع أخذ إقرارات الحرمان آلياً.

💡 *صُنع خصيصاً لدعم مسيرة التميز والإبداع في المعهد الصناعي الثانوي ببريدة.*
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def db_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    try:
        if not os.path.exists('data.xlsx'):
            await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
            return
        df = pd.read_excel('data.xlsx', dtype=str)
        sample = df['stu_num'].dropna().unique()[:5]
        msg = f"📊 *كشاف البيانات:*\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام:\n`{', '.join(sample)}`"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except: pass

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("⏳ جاري التجهيز...")
    for f in ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json', 'plans.json']:
        if os.path.exists(f): await context.bot.send_document(chat_id=update.effective_chat.id, document=open(f, 'rb'))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    text = update.message.text.replace('/broadcast', '').strip()
    if not text: return await update.message.reply_text("⚠️ الطريقة: `/broadcast التعميم هنا`", parse_mode='Markdown')
    users = load_json(STATS_FILE).get("users_list", [])
    await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        try: await context.bot.send_message(chat_id=u, text=f"📢 *إعلان إداري هام:*\n{SEP}\n{text}", parse_mode='Markdown')
        except: pass
    await update.message.reply_text("✅ تم إرسال التعميم.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    stats = load_json(STATS_FILE)
    interrogations = load_json(INTERROGATIONS_FILE)
    
    users_count = len(stats.get("users_list", []))
    ai_queries = stats.get("ai_questions", 0)
    quiz_attempts = stats.get("quiz_attempts", 0)
    pledges_count = sum(len(subjects) for subjects in interrogations.values())
    
    db_records = 0
    active_students_count = 0
    weekly_attendance_rate = 100.0
    
    if os.path.exists('data.xlsx'):
        try: 
            df = pd.read_excel('data.xlsx', dtype=str)
            db_records = len(df)
            active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
            active_students_count = active_rows['stu_num'].nunique()
            valid_absence = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce')
            valid_absence = valid_absence.dropna()
            if not valid_absence.empty:
                avg_absence = valid_absence.mean()
                weekly_attendance_rate = round(100 - avg_absence, 2)
        except: pass
        
    saved_minutes_ai = ai_queries * 3
    saved_minutes_pledges = pledges_count * 15
    total_hours_saved = round((saved_minutes_ai + saved_minutes_pledges) / 60, 1)
    
    report_msg = f"""
🏆 *تقرير الأداء لجائزة التميز بمنطقة القصيم* 🏆
{SEP}
👥 *المؤشرات الأكاديمية (محدثة آلياً):*
🔹 المتدربين المنتظمين بالقسم: `{active_students_count}` متدرب
🔹 نسبة الحضور الأسبوعية العامة: `{weekly_attendance_rate}%` 📈

📱 *معيار التحول الرقمي:*
🔹 المتدربين المسجلين بالبوت: `{users_count}` متدرب
🔹 السجلات المؤتمتة بالنظام: `{db_records}` سجل

📊 *معيار الأثر الفعلي:*
🔹 استفسارات عولجت بالذكاء الاصطناعي: `{ai_queries}` استفسار
🔹 إقرارات وتعهدات غياب نُفذت آلياً: `{pledges_count}` تعهد

⏳ *معيار الكفاءة التشغيلية:*
✅ توفير وقت الإدارة بمقدار: *{total_hours_saved} ساعة عمل!*

♻️ *معيار الاستدامة:*
✅ ربط سحابي وتحديث دائم (24/7).
"""
    await update.message.reply_text(report_msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_msg = (f"أهلاً بك يا {update.effective_user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
                   f"أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n"
                   f"👇 الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:")
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            await update.message.reply_text("تم إلغاء العملية، والعودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
            return

        if state['flow'] == 'pledge':
            step = state['step']
            if step == 1:
                user_states[user_id]['aware'] = text
                user_states[user_id]['step'] = 2
                return await update.message.reply_text("2️⃣ *فضلاً، اختر العذر الرئيسي لكثرة غياباتك من القائمة بالأسفل:*\n(أو يمكنك كتابة عذرك يدوياً)", parse_mode='Markdown', reply_markup=get_pledge_step2_menu())
            
            elif step == 2:
                if len(text) < 4: return await update.message.reply_text("⚠️ العذر غير واضح، اختر من الأزرار بالأسفل أو اكتب عذراً مفصلاً:", reply_markup=get_pledge_step2_menu())
                user_states[user_id]['excuse'] = text
                user_states[user_id]['step'] = 3
                return await update.message.reply_text("3️⃣ *الإقرار النهائي:*\nهل تتعهد بالانضباط والالتزام لتفادي الحرمان النهائي (20%) وطي القيد؟\n*(اضغط على زر التعهد بالأسفل)*", parse_mode='Markdown', reply_markup=get_pledge_step3_menu())
            
            elif step == 3:
                if "تعهد" not in text and "أقر" not in text and "نعم" not in text:
                    return await update.message.reply_text("⚠️ لم يتم قبول إقرارك!\nيرجى الضغط على زر الإقرار بالأسفل للموافقة:", reply_markup=get_pledge_step3_menu())
                
                completed = load_json(INTERROGATIONS_FILE)
                completed.setdefault(state['stu_num'], []).append(state['subject'])
                save_json(INTERROGATIONS_FILE, completed)
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                official_document = f"""
🏛️ **المؤسسة العامة للتدريب التقني والمهني**
📍 **المعهد الصناعي الثانوي ببريدة - قسم الحاسب**
{SEP}
📄 **وثيقة تعهد إلكتروني بالانضباط الأكاديمي**

أقر وأتعهد أنا المتدرب / **{state['stu_nam']}**
الرقم التدريبي / **{state['stu_num']}**
بشأن المقرر التدريبي / **{state['subject']}**

بأنني اطلعت على نسبة غيابي التي بلغت حد (الإنذار)، وأتعهد بالانضباط التام وعدم تكرار الغياب، حرصاً على مستقبلي التدريبي.
كما أقر بتحملي لكامل المسؤولية النظامية في حال وصول نسبة الغياب إلى حد الحرمان (20%) وطي قيدي من المعهد.

📝 **العذر المُسجل للمتدرب:** {state['excuse']}

✅ **حالة الاعتماد:** (مُعتمد ومُوقع إلكترونياً من قبل المتدرب)
⏱️ **تاريخ وتوثيق الاعتماد:** {timestamp}
{SEP}
*(نسخة إلكترونية معتمدة - قسم شؤون المتدربين)*
"""
                try: 
                    await context.bot.send_message(chat_id=GROUP_ID, text=official_document, parse_mode='Markdown')
                except Exception as e: 
                    pass 
                
                del user_states[user_id]
                await update.message.reply_text(official_document, parse_mode='Markdown')
                await update.message.reply_text("✅ *تم توثيق إقرارك رسمياً ورفع نسخة للإدارة.*\nاحرص على الحضور لتفادي طي القيد.", parse_mode='Markdown', reply_markup=get_main_menu())
                return

        if state['flow'] == 'feedback':
            if len(text) < 15:
                return await update.message.reply_text("⚠️ الرسالة قصيرة جداً!\nالرجاء كتابة رسالتك بالتفصيل (أكثر من 15 حرف) لكي نأخذها بجدية.", reply_markup=get_cancel_menu())
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 *شكوى/مقترح:*\nالمرسل: {update.effective_user.first_name}\nالنص: {text}", parse_mode='Markdown')
                del user_states[user_id]
                return await update.message.reply_text("✅ تم إرسال رسالتك للإدارة بسرية تامة.", reply_markup=get_main_menu())
            except Exception as e: 
                del user_states[user_id]
                return await update.message.reply_text("⚠️ حدث خطأ أثناء إرسال الشكوى. يرجى المحاولة لاحقاً.", reply_markup=get_main_menu())

        if state['flow'] == 'ai':
            if not ai_model:
                del user_states[user_id]
                return await update.message.reply_text("⚠️ المعلم غير متصل حالياً.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم الذكي:\n\n{response.text}", reply_markup=get_back_menu())
            except: return await update.message.reply_text("⚠️ خطأ تقني بالذكاء الاصطناعي.", reply_markup=get_back_menu())

        if state['flow'] == 'excuse':
            return await update.message.reply_text("⚠️ هذا نص! الرجاء إرسال (صورة أو ملف PDF) للعذر الطبي مع كتابة رقمك في الوصف الخاص بالصورة.", reply_markup=get_cancel_menu())

    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        msg = "📝 *نظام رفع الأعذار:*\nالرجاء إرفاق (صورة العذر) الآن، ويجب كتابة (رقمك واسمك) في خانة الوصف (Caption).\n\n⚠️ *تُقبل الأعذار الرسمية والطبية فقط بعد الغياب خلال 3 إلى 5 أيام.*"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        msg = "📬 *صندوق الإدارة:*\nاكتب رسالتك، اقتراحك، أو شكواك الآن بالتفصيل وسوف تصل للإدارة بسرية تامة...\n\n*(نرجو إرفاق اسم المتدرب والرقم التدريبي إذا لزم الأمر للتواصل معك)*"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        await update.message.reply_text("🤖 *المعلم الذكي!*\n💬 أنا جاهز، اكتب أي سؤال تقني أو إداري وسأجيبك فوراً...", parse_mode='Markdown', reply_markup=get_back_menu())
        return

    if text == "📊 استعلام الغياب":
        msg = "🔎 *استعلام عن نسبة الغياب (تُحدث أسبوعياً)*\n👇 أرسل رقمك التدريبي الآن (أرقام فقط)..."
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text == "📚 الحقائب التدريبية": 
        msg = "📚 *هذا رابط المقررات التدريبية لقسم الحاسب الآلي في المعهد الصناعي الثانوي:*"
        return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول للمستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
        
    if text == "🔗 المنصات الإلكترونية": 
        kb = [
            [InlineKeyboardButton("رايات (الجداول والغياب والنتائج)", url="https://rayat.tvtc.gov.sa")], 
            [InlineKeyboardButton("تقني (التعلم الإلكتروني والواجبات)", url="https://tvtclms.edu.sa")], 
            [InlineKeyboardButton("بلاك بورد (التعلم الإلكتروني والواجبات)", url="https://lms.elearning.edu.sa/")]
        ]
        return await update.message.reply_text("🌐 *المنصات الإلكترونية للتدريب:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
    if text == "📍 موقع القسم": 
        msg = "📍 *هذا موقع المعهد الصناعي الثانوي ببريدة - مبنى قسم الحاسب رقم 19:*"
        return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
        
    if text == "📰 أخبار القسم والمعهد": 
        msg = "📰 *جميع أخبار القسم والمعهد وحساب المعهد في موقع X (تويتر سابقاً):*"
        return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 حساب منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
        
    if text == "📅 التقويم التدريبي":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        caption_msg = "📅 *هذا التقويم للفصل الحالي 1447 الفصل الثاني.*"
        if os.path.exists('calendar.jpg'): return await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption=caption_msg, parse_mode='Markdown')
        else: return await update.message.reply_text(caption_msg + "\n⚠️ *(جاري تحديث صورة التقويم)*", parse_mode='Markdown')
        
    if text == "📘 دليل المتدرب":
        caption_msg = "📘 *دليل المتدرب لعام 1447*"
        if os.path.exists("trainee_guide.pdf"): return await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption=caption_msg, parse_mode='Markdown')
        else: return await update.message.reply_text(caption_msg + "\n⚠️ *(جاري رفع ملف الدليل)*", parse_mode='Markdown')

    if text == "📄 الخطط التدريبية":
        return await update.message.reply_text("📄 *اختر الفصل لمعرفة المقررات:*", reply_markup=get_plans_menu(), parse_mode='Markdown')

    if text == "🕹️ قسم الألعاب والإضافات":
        msg = (
            "🕹️ *قسم الترفيه والإضافات:*\n\n"
            "🎮 *تحدي الأسبوع:* أسئلة تقنية سريعة لاختبار معلوماتك.\n"
            "🏆 *بطل الأسبوع:* لوحة شرف لأعلى المتدربين نقاطاً.\n"
            "💡 *نصيحة تقنية:* معلومات أمنية وبرمجية سريعة.\n"
            "🌐 *أخبار التقنية:* آخر التطورات في عالم التكنولوجيا.\n\n"
            "👇 *اختر النشاط المطلوب:*"
        )
        return await update.message.reply_text(msg, reply_markup=get_games_menu(), parse_mode='Markdown')

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'):
                return await update.message.reply_text("⚠️ قاعدة البيانات فارغة.")

            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None
                has_deprivation = False
                
                m = f"🎓 *السجل الأكاديمي للغياب*\n{SEP}\n👤 *المتدرب:* {stu_nam}\n🔢 *الرقم التدريبي:* {clean_text}\n{SEP}\n📊 *تفاصيل المقررات:*\n\n"
                
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    parsnt_no = str(r.get('parsnt_no', '0')).replace('%', '').strip()
                    hrs = str(r.get('hrs', '0')).replace('.0', '').strip()
                    if raw_val == 'nan' or raw_val == '': raw_val = '0'
                    
                    if raw_val == 'ح' or 'حرمان' in raw_val:
                        display_val = "*حرمان (ح)* 🔴"
                        has_deprivation = True
                        extras = []
                        if parsnt_no and parsnt_no.lower() not in ['nan', 'none', '', '0']: extras.append(f"بدون عذر: {parsnt_no}%")
                        if hrs and hrs.lower() not in ['nan', 'none', '', '0']: extras.append(f"الغياب: {hrs} ساعة")
                        if extras: display_val += f"\n   ↳ 🔍 التفاصيل: {' | '.join(extras)}"
                    elif raw_val == 'ط' or 'طي' in raw_val:
                        display_val = "*طي قيد (ط)* ⚫"
                        has_deprivation = True
                    else:
                        try:
                            val = float(raw_val)
                            if val >= 20:
                                icon = "🔴 حرمان"
                                has_deprivation = True
                            elif val >= 15:
                                icon = "⚠️ إنذار"
                                if c_name_text not in completed_interrogations: subject_to_interrogate = c_name_text
                            else: icon = "🟢 منتظم"
                            display_val = f"*{val}%* {icon}"
                            extras = []
                            if hrs and hrs.lower() not in ['nan', 'none', '', '0']: extras.append(f"الغياب: {hrs} ساعة")
                            if extras: display_val += f" ({', '.join(extras)})"
                        except: display_val = f"*{raw_val}* ⚠️"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    m += f"📖 *{c_name_text}*\n▫️ النتيجة: {display_val}\n📅 التحديث: {day_val}\n\n"
                
                m += f"{SEP}\n💡 *الإنذار يبدأ عند 15%، والحرمان عند 20%.*"

                await update.message.reply_text(m, parse_mode='Markdown')

                if subject_to_interrogate:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    warning_msg = f"⚠️ *تنبيه إداري عاجل!*\nلقد وصلت غياباتك إلى مرحلة الخطر (15% فأكثر) في مقرر:\n*{subject_to_interrogate}*\n\n🛑 *النظام مغلق حتى تُكمل الإقرار!*\n1️⃣ هل تعلم أنك اقتربت من الحرمان؟"
                    return await update.message.reply_text(warning_msg, parse_mode='Markdown', reply_markup=get_pledge_step1_menu())
                
                if has_deprivation: 
                    await update.message.reply_text("🛑 *تنبيه إداري:* أنت محروم في مقرر أو أكثر. راجع الإدارة.", parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ الرقم التدريبي غير مسجل أو لا توجد غيابات.")
        except Exception as e:
            pass
        return

    if text == "❓ الأسئلة الشائعة":
        faq_msg = (
            "🏛️ *اللوائح والأنظمة التدريبية الشائعة*\n"
            f"{SEP}\n"
            "📌 *لائحة الحرمان وطي القيد:*\n"
            "يُحرم المتدرب من المقرر ويُطوى قيده نظامياً في حال بلوغ نسبة الغياب حد (20%).\n\n"
            "💳 *المكافأة الشهرية:*\n"
            "تُصرف مكافأة قدرها (800 ريال)، ويُعلق صرفها في حال انخفاض المعدل عن (2.00).\n\n"
            "🎓 *درجة الاجتياز الأكاديمي:*\n"
            "الحد الأدنى لاجتياز المقررات في نظام المعاهد هو الحصول على (50) درجة.\n"
            f"{SEP}\n"
            "💡 *للاطلاع على اللوائح كاملة، يرجى تصفح (دليل المتدرب) من القائمة.*"
        )
        return await update.message.reply_text(faq_msg, parse_mode='Markdown')
        
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]:
        plans = load_json("plans.json")
        return await update.message.reply_text(f"{plans.get(text, 'جاري التحديث')}\n{SEP}\n🔗 *لتحميل المنهج:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 تحميل", url=DRIVE_LINK)]]), parse_mode='Markdown')
        
    if text == "💡 نصيحة تقنية":
        return await update.message.reply_text(random.choice(TECH_TIPS))
        
    if text == "🌐 أخبار التقنية":
        try:
            req = urllib.request.Request("https://www.tech-wd.com/wd/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 *الأخبار التقنية*\n{SEP}\n"
            for i, item in enumerate(root.findall('.//item')):
                if i >= 3: break
                news_msg += f"🔹 [{item.find('title').text}]({item.find('link').text})\n\n"
            return await update.message.reply_text(news_msg, parse_mode='Markdown', disable_web_page_preview=True)
        except: pass
        
    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        active_challenges[user_id] = time.time()
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        return await update.message.reply_text(f"❓ *تحدي الأسبوع:*\n\n{q['q']}\n\n⚠️ أمامك 15 ثانية:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: return await update.message.reply_text("📉 لا يوجد نقاط مسجلة.")
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        return await update.message.reply_text(f"🏆 *بطل الأسبوع:* {top['name']}\n🌟 *النقاط:* {top['score']}", parse_mode='Markdown')

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# --- 🌟 محرك الإدارة (المحرك المزدوج لرفع الملفات وتقارير الجودة) 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ جاري تحليل الملف وفك التشفير...")
            
            try:
                file = await context.bot.get_file(doc.file_id)
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    with open(temp_file, 'rb') as f: raw_bytes = f.read()
                    best_enc = 'utf-8' 
                    for enc in ['utf-8', 'utf-8-sig', 'windows-1256', 'cp1256', 'iso-8859-6']:
                        try:
                            text = raw_bytes.decode(enc)
                            if 'المتدرب' in text or 'المقرر' in text or 'الغياب' in text or 'رقم' in text or 'نسبة التحضير' in text:
                                best_enc = enc; break 
                        except: pass
                            
                    df_raw = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
                    
                    is_quality_report = any('نسبة التحضير' in str(c) for c in df_raw.columns) and any('اسم المدرب' in str(c) for c in df_raw.columns)

                    if is_quality_report:
                        col_prep_percent = [c for c in df_raw.columns if 'نسبة التحضير' in str(c)][0]
                        col_trainer_name = [c for c in df_raw.columns if 'اسم المدرب' in str(c)][0]
                        col_total_prep = [c for c in df_raw.columns if 'إجمالي التحضير' in str(c)][0]
                        col_present = [c for c in df_raw.columns if 'تحضير مسجل' in str(c)][0]

                        df_raw[col_prep_percent] = pd.to_numeric(df_raw[col_prep_percent].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
                        df_raw[col_total_prep] = pd.to_numeric(df_raw[col_total_prep], errors='coerce').fillna(0)
                        df_raw[col_present] = pd.to_numeric(df_raw[col_present], errors='coerce').fillna(0)

                        total_sections = len(df_raw)
                        unrecorded_df = df_raw[df_raw[col_prep_percent] < 100]
                        unrecorded_sections_count = len(unrecorded_df)
                        recorded_sections_count = total_sections - unrecorded_sections_count

                        total_trainers = df_raw[col_trainer_name].nunique()
                        trainers_not_recorded = unrecorded_df[col_trainer_name].dropna().unique()
                        unrecorded_trainers_count = len(trainers_not_recorded)
                        recorded_trainers_count = total_trainers - unrecorded_trainers_count

                        total_expected_hits = df_raw[col_total_prep].sum()
                        total_present_hits = df_raw[col_present].sum()
                        attendance_rate = round((total_present_hits / total_expected_hits) * 100, 2) if total_expected_hits > 0 else 0
                        
                        report_quality_msg = f"""
📑 *تقرير متابعة سير العملية التدريبية الأسبوعية* 📑
{SEP}
👥 *إحصائيات المتدربين والحضور:*
▫️ إجمالي المتدربين (التحضير): `{int(total_expected_hits)}`
▫️ المتدربين الحاضرين: `{int(total_present_hits)}`
📈 نسبة الحضور: `{attendance_rate}%`

📝 *إحصائيات الشعب التدريبية:*
▫️ إجمالي عدد الشعب: `{total_sections}`
✅ الشعب المحضرة: `{recorded_sections_count}`
⚠️ الشعب غير المحضرة: `{unrecorded_sections_count}`

👨‍🏫 *إحصائيات المدربين:*
▫️ إجمالي عدد المدربين: `{total_trainers}`
✅ المدربين المحضرين: `{recorded_trainers_count}`
⚠️ المدربين غير المحضرين: `{unrecorded_trainers_count}`
"""
                        if unrecorded_sections_count > 0:
                            report_quality_msg += f"\n{SEP}\n📋 *المدربين المتأخرين بالرصد:*"
                            for trainer in trainers_not_recorded:
                                trainer_sections = unrecorded_df[unrecorded_df[col_trainer_name] == trainer]
                                sections_count = len(trainer_sections)
                                report_quality_msg += f"\n▫️ {trainer} `({sections_count} شعب)`"
                        else:
                            report_quality_msg += f"\n{SEP}\n🎉 *عمل مميز! جميع الشعب مُحضرة بنسبة 100%.*"

                        os.remove(temp_file)
                        await status_msg.edit_text(report_quality_msg, parse_mode='Markdown')
                        return
                    
                    df_clean = pd.DataFrame()
                    col_map = {'c_course': -1, 'c_id': -1, 'c_name': -1, 'c_perc': -1, 'c_perc_no': -1, 'c_hrs': -1}
                    for i, col in enumerate(df_raw.columns):
                        clean_col = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا').replace('"', '')
                        if 'اسمالمقرر' in clean_col: col_map['c_course'] = i
                        elif 'رقمالمتدرب' in clean_col: col_map['c_id'] = i
                        elif 'اسمالمتدرب' in clean_col: col_map['c_name'] = i
                        elif 'بعذروبدون' in clean_col and 'نسبه' in clean_col: col_map['c_perc'] = i
                        elif 'بدونعذر' in clean_col and 'نسبه' in clean_col and 'بعذروبدون' not in clean_col: col_map['c_perc_no'] = i
                        elif 'ساعات' in clean_col and 'بعذروبدون' in clean_col: col_map['c_hrs'] = i

                    if col_map['c_course'] == -1: col_map['c_course'] = 14 if len(df_raw.columns) > 14 else 0
                    if col_map['c_id'] == -1: col_map['c_id'] = 16 if len(df_raw.columns) > 16 else 0
                    if col_map['c_name'] == -1: col_map['c_name'] = 17 if len(df_raw.columns) > 17 else 0
                    if col_map['c_perc'] == -1: col_map['c_perc'] = 18 if len(df_raw.columns) > 18 else 0
                    if col_map['c_perc_no'] == -1: col_map['c_perc_no'] = 22 if len(df_raw.columns) > 22 else -1
                    if col_map['c_hrs'] == -1: col_map['c_hrs'] = 25 if len(df_raw.columns) > 25 else -1

                    df_clean['c_nam'] = df_raw.iloc[:, col_map['c_course']].astype(str)
                    df_clean['stu_num'] = df_raw.iloc[:, col_map['c_id']].astype(str)
                    df_clean['stu_nam'] = df_raw.iloc[:, col_map['c_name']].astype(str)
                    df_clean['parsnt'] = df_raw.iloc[:, col_map['c_perc']].astype(str)
                    df_clean['parsnt_no'] = df_raw.iloc[:, col_map['c_perc_no']].astype(str) if col_map['c_perc_no'] != -1 else ""
                    df_clean['hrs'] = df_raw.iloc[:, col_map['c_hrs']].astype(str) if col_map['c_hrs'] != -1 else ""
                    
                    df_clean['stu_num'] = df_clean['stu_num'].str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                    df_clean = df_clean[df_clean['stu_num'].str.len() >= 5] 
                    for col in df_clean.columns: df_clean[col] = df_clean[col].replace('nan', '').str.strip()
                        
                    df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file)
                else:
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                
                github_status = backup_to_github("data.xlsx")
                await status_msg.edit_text(f"✅ *نجاح ساحق (تحديث قاعدة الطلاب)!*\n📊 *النتيجة:* حفظ `{records_count}` متدرب.\n🌐 *السحابة:* {github_status}", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ *فشل التحديث:* `{e}`", parse_mode='Markdown')
            return

    if update.message.photo or update.message.document:
        state = user_states.get(user_id, {})
        caption_text = update.message.caption
        
        stu_id = ''.join(filter(str.isdigit, str(caption_text)))
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض: وصف غير مكتمل!*\nيجب أن تقوم بإرفاق الصورة مرة أخرى وتأكد من كتابة *رقمك التدريبي* في الوصف لكي يتم ربطه بملفك.", parse_mode='Markdown', reply_markup=get_cancel_menu() if state.get('flow') == 'excuse' else get_main_menu())
            
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري الختم الآلي والإرسال...")
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if update.message.photo and HAS_PIL:
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                in_memory_img = io.BytesIO()
                await file.download_to_memory(in_memory_img)
                in_memory_img.seek(0)
                
                img = Image.open(in_memory_img)
                width, height = img.size
                txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
                ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id} | DATE: {timestamp}", fill="white")
                txt_img = txt_img.resize((width, int(width * 50 / 1000)))
                img.paste(txt_img, (0, height - txt_img.height)) 
                
                output = io.BytesIO()
                img.save(output, format='JPEG')
                output.seek(0)
                await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 *عذر مختوم:*\n{caption_text}\n⏱️ {timestamp}", parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 *عذر مرفق:*\n{caption_text}\n{timestamp}", parse_mode='Markdown')
                await update.message.copy(chat_id=GROUP_ID)
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الختم والإرسال للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
        except Exception as e:
            await status_msg.edit_text(f"⚠️ خطأ فني مباشر من السيرفر:\n`{str(e)}`\n\n*(تأكد من رقم القروب وصلاحيات البوت)*", parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    if query.data.startswith("ans_"):
        parts = query.data.split("_")
        q_idx, sel = int(parts[1]), int(parts[2])
        try:
            actual_question = QUESTIONS[q_idx]
            m = "🎉 *إجابة صحيحة!*" if sel == actual_question["answer"] else f"❌ *خاطئة!*"
            await query.edit_message_text(f"❓ *تحدي الأسبوع:*\n{actual_question['q']}\n{SEP}\n{m}", parse_mode='Markdown')
        except: pass

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) 
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("start", start))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النظام (مع تقارير الجودة الأسبوعية الاحترافية)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
