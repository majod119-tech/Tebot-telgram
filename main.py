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

# --- 🌟 استدعاء مكتبة الصور للختم الآلي بحماية ---
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- 🌟 دوال مساعدة لإدارة الملفات ---
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
    "💡 **نصيحة أمنية:** استخدم `Win + L` لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ **نصيحة تقنية:** احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات.",
    "🚀 **نصيحة برمجية:** التنسيق والمسافات البادئة في لغة بايثون هي أساس عمل الكود.",
    "💾 **نصيحة:** احرص دائماً على أخذ نسخة احتياطية لملفاتك المهمة.",
    "🌐 **نصيحة:** تجنب الاتصال بشبكات الواي فاي العامة المفتوحة بدون VPN."
]

# --- 🌟 إعدادات النظام ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
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

# --- 🌟 أداة الرفع السحابي لـ GitHub ---
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

# --- 🌟 قيود المعلم الذكي (الصارمة والمخصصة للمؤسسة) 🌟 ---
AI_KNOWLEDGE = (
    "أنت 'المعلم الذكي'، مساعد رقمي رسمي وأكاديمي لقسم الحاسب الآلي بالإدارة العامة للتدريب التقني والمهني بمنطقة القصيم. "
    "مهمتك الوحيدة والأساسية هي الإجابة على استفسارات المتدربين حول أنظمة ولوائح التدريب فقط.\n"
    "اللوائح الثابتة: الإنذار يبدأ عند غياب 15%، والحرمان وطي القيد عند 20%. المكافأة 800 ريال وتتوقف إذا نزل المعدل عن 2.00. درجة الاجتياز 50 للمعاهد.\n"
    f"رابط الحقائب التدريبية: {DRIVE_LINK}\n"
    "🚨 تعليمات صارمة جداً: يُمنع منعاً باتاً الإجابة على أي سؤال عام أو خارج النطاق التقني أو التدريبي للمؤسسة. إذا سألك المستخدم عن شيء خارج هذا النطاق، قل حرفياً: "
    "عذراً، أنا مخصص لخدمة متدربي المؤسسة العامة للتدريب التقني والمهني للإجابة على الاستفسارات الأكاديمية والتدريبية فقط."
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                # إعدادات لتقليل الخيال وجعل البوت أكثر رسمية
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''), generation_config={"temperature": 0.2})
                break
    except: pass

user_states = {}
active_challenges = {}

# --- 🌟 تصميم القوائم 🌟 ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي (الدليل الشامل)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 المنصات الإلكترونية", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["❓ الأسئلة الشائعة", "📘 دليل المتدرب الرسمي"],
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

# --- 🌟 أوامر الإدارة 🌟 ---
async def db_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    try:
        if not os.path.exists('data.xlsx'):
            await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
            return
        df = pd.read_excel('data.xlsx', dtype=str)
        sample = df['stu_num'].dropna().unique()[:5]
        msg = f"📊 **كشاف البيانات:**\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام:\n`{', '.join(sample)}`"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except: pass

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("⏳ جاري التجهيز...")
    for f in ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json', 'plans.json']:
        if os.path.exists(f): await context.bot.send_document(chat_id=update.effective_chat.id, document=open(f, 'rb'))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    text = update.message.text.replace('/broadcast', '').strip()
    if not text: return await update.message.reply_text("⚠️ الطريقة: `/broadcast التعميم هنا`", parse_mode='Markdown')
    users = load_json(STATS_FILE).get("users_list", [])
    await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        try: await context.bot.send_message(chat_id=u, text=f"📢 **إعلان إداري هام:**\n{SEP}\n{text}", parse_mode='Markdown')
        except: pass
    await update.message.reply_text("✅ تم إرسال التعميم.")

# --- 🌟 تقرير التميز المؤسسي المتوافق مع معايير الجائزة 🌟 ---
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    stats = load_json(STATS_FILE)
    interrogations = load_json(INTERROGATIONS_FILE)
    
    users_count = len(stats.get("users_list", []))
    ai_queries = stats.get("ai_questions", 0)
    quiz_attempts = stats.get("quiz_attempts", 0)
    
    db_records = 0
    if os.path.exists('data.xlsx'):
        try: db_records = len(pd.read_excel('data.xlsx'))
        except: pass
        
    pledges_count = sum(len(subjects) for subjects in interrogations.values())
    
    saved_minutes_ai = ai_queries * 3
    saved_minutes_pledges = pledges_count * 15
    total_hours_saved = round((saved_minutes_ai + saved_minutes_pledges) / 60, 1)
    
    report_msg = f"""
🏆 **تقرير الأداء لجائزة التميز بمنطقة القصيم** 🏆
{SEP}
📱 **معيار التحول الرقمي:**
🔹 إجمالي المتدربين المستفيدين: `{users_count}` متدرب
🔹 السجلات المؤتمتة بالنظام: `{db_records}` سجل

📊 **معيار الأثر الفعلي:**
🔹 استفسارات عولجت بالذكاء الاصطناعي: `{ai_queries}` استفسار
🔹 إقرارات وتعهدات غياب نُفذت آلياً: `{pledges_count}` تعهد
🔹 مشاركات التثقيف التقني (التحديات): `{quiz_attempts}` مشاركة

⏳ **معيار الكفاءة التشغيلية:**
*(الجهد الإداري المُوفر بفضل الأتمتة)*
✅ توفير وقت الإدارة بمقدار: **{total_hours_saved} ساعة عمل!**

♻️ **معيار الاستدامة:**
✅ ربط سحابي (GitHub) وحفظ دائم (24/7).
{SEP}
💡 *تتوافق هذه المؤشرات مع أهداف التميز للمؤسسة العامة للتدريب التقني والمهني.*
"""
    await update.message.reply_text(report_msg, parse_mode='Markdown')

# --- 🌟 محرك الاستجابة الشامل 🌟 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_msg = (f"أهلاً بك يا {update.effective_user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
                   f"أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n"
                   f"👇 **الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:**")
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    # 1. نظام الحجر الذكي (لإدارة حالات المستخدمين الصارمة)
    if user_id in user_states:
        state = user_states[user_id]
        
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            await update.message.reply_text("تم إلغاء العملية، والعودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
            return

        if state['flow'] == 'pledge':
            step = state['step']
            if step == 1:
                if len(text) < 2: return await update.message.reply_text("⚠️ إجابة غير واضحة، أرجو الإجابة بشكل صحيح:", reply_markup=get_cancel_menu())
                user_states[user_id]['aware'] = text
                user_states[user_id]['step'] = 2
                return await update.message.reply_text("2️⃣ **ما هو العذر الرئيسي لكثرة غياباتك؟**\n(نرجو التفصيل لرفعه للإدارة)", parse_mode='Markdown', reply_markup=get_cancel_menu())
            
            elif step == 2:
                if len(text) < 10: return await update.message.reply_text("⚠️ **العذر قصير جداً وغير مقنع!**\nالرجاء كتابة العذر بالتفصيل لكي تأخذه الإدارة بعين الاعتبار:", parse_mode='Markdown', reply_markup=get_cancel_menu())
                user_states[user_id]['excuse'] = text
                user_states[user_id]['step'] = 3
                return await update.message.reply_text("3️⃣ **هل تتعهد بالانضباط والالتزام لتفادي الحرمان النهائي (20%)؟**\n🛑 *(يجب أن تكتب كلمة: نعم ، أو كلمة: أتعهد)*", parse_mode='Markdown', reply_markup=get_cancel_menu())
            
            elif step == 3:
                if "نعم" not in text and "تعهد" not in text:
                    return await update.message.reply_text("⚠️ **لم يتم قبول إقرارك!**\nالرجاء كتابة (نعم) أو (أتعهد) للموافقة والالتزام:", parse_mode='Markdown', reply_markup=get_cancel_menu())
                
                completed = load_json(INTERROGATIONS_FILE)
                completed.setdefault(state['stu_num'], []).append(state['subject'])
                save_json(INTERROGATIONS_FILE, completed)
                
                report = f"🚨 **تعهد (إنذار 15%)** 🚨\n👤 **المتدرب:** {state['stu_nam']} ({state['stu_num']})\n📖 **المادة:** {state['subject']}\n❓ **العذر:** {state['excuse']}\n✍️ **الإقرار:** {text}"
                try: await context.bot.send_message(chat_id=GROUP_ID, text=report, parse_mode='Markdown')
                except: pass
                
                del user_states[user_id]
                await update.message.reply_text("✅ **تم توثيق إقرارك رسمياً لدى الإدارة.**\nاحرص على الحضور لتفادي طي القيد.", reply_markup=get_main_menu(), parse_mode='Markdown')
                return

        if state['flow'] == 'feedback':
            if len(text) < 15:
                return await update.message.reply_text("⚠️ **الرسالة قصيرة جداً!**\nالرجاء كتابة رسالتك بالتفصيل (أكثر من 15 حرف) لكي نأخذها بجدية.", parse_mode='Markdown', reply_markup=get_cancel_menu())
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 **شكوى/مقترح:**\nالمرسل: {update.effective_user.first_name}\nالنص: {text}")
                del user_states[user_id]
                return await update.message.reply_text("✅ **تم إرسال رسالتك للإدارة بسرية تامة.**", reply_markup=get_main_menu(), parse_mode='Markdown')
            except: 
                del user_states[user_id]
                return await update.message.reply_text("⚠️ فشل الإرسال، حاول لاحقاً.", reply_markup=get_main_menu())

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
            return await update.message.reply_text("⚠️ **هذا نص! الرجاء إرسال (صورة أو ملف PDF) للعذر الطبي مع كتابة رقمك في الوصف الخاص بالصورة.**", parse_mode='Markdown', reply_markup=get_cancel_menu())

    # 2. القوائم التفاعلية
    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        await update.message.reply_text("📝 **نظام رفع الأعذار الصارم:**\nالرجاء إرفاق (صورة العذر) الآن، **ويجب** كتابة (رقمك واسمك) في خانة الوصف (Caption) الخاصة بالصورة لكي يقبلها النظام.", parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        await update.message.reply_text("📬 **صندوق الإدارة:**\nاكتب رسالتك، اقتراحك، أو شكواك الآن بالتفصيل وسوف تصل للإدارة بسرية تامة...", parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        user_states[user_id] = {'flow': 'ai'}
        await update.message.reply_text("🤖 **المعلم الذكي!**\n💬 أنا جاهز، اكتب أي سؤال تقني أو إداري وسأجيبك فوراً...", parse_mode='Markdown', reply_markup=get_back_menu())
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 **استعلام الغياب**\n👇 **أرسل رقمك التدريبي الآن (أرقام فقط)...**", parse_mode='Markdown')
        return

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'):
                return await update.message.reply_text("⚠️ **قاعدة البيانات فارغة.**", parse_mode='Markdown')

            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None
                has_deprivation = False
                
                m = f"🎓 **السجل الأكاديمي للغياب** 🎓\n{SEP}\n👤 **المتدرب:** `{stu_nam}`\n🔢 **الرقم التدريبي:** `{clean_text}`\n{SEP}\n📊 **تفاصيل المقررات:**\n\n"
                
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    parsnt_no = str(r.get('parsnt_no', '0')).replace('%', '').strip()
                    hrs = str(r.get('hrs', '0')).replace('.0', '').strip()
                    if raw_val == 'nan' or raw_val == '': raw_val = '0'
                    
                    if raw_val == 'ح' or 'حرمان' in raw_val:
                        icon = "🔴 حرمان مؤكد"
                        display_val = f"**حرمان (ح)** {icon}"
                        has_deprivation = True
                        extras = []
                        if parsnt_no and parsnt_no.lower() not in ['nan', 'none', '', '0']: extras.append(f"بدون عذر: {parsnt_no}%")
                        if hrs and hrs.lower() not in ['nan', 'none', '', '0']: extras.append(f"الغياب: {hrs} ساعة")
                        if extras: display_val += f"\n   ↳ 🔍 *التفاصيل:* {' | '.join(extras)}"
                    elif raw_val == 'ط' or 'طي' in raw_val:
                        icon = "⚫ طي قيد"
                        display_val = f"**طي قيد (ط)** {icon}"
                        has_deprivation = True
                    else:
                        try:
                            val = float(raw_val)
                            if val >= 20:
                                icon = "🔴 حرمان"
                                has_deprivation = True
                            elif val >= 15:
                                icon = "⚠️ إنذار (مهدد بالحرمان)"
                                if c_name_text not in completed_interrogations: subject_to_interrogate = c_name_text
                            else: icon = "🟢 منتظم"
                            display_val = f"**{val}%** {icon}"
                            extras = []
                            if hrs and hrs.lower() not in ['nan', 'none', '', '0']: extras.append(f"الغياب: {hrs} ساعة")
                            if extras: display_val += f" `({', '.join(extras)})`"
                        except: display_val = f"**{raw_val}** ⚠️ (بيانات غير مقروءة)"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    m += f"📖 **{c_name_text}**\n▫️ النتيجة: {display_val}\n📅 التحديث: {day_val}\n\n"
                
                m += f"{SEP}\n💡 *الإنذار يبدأ عند 15%، والحرمان عند 20%.*"

                if subject_to_interrogate:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    warning_msg = f"⚠️ **تنبيه إداري عاجل!** ⚠️\nلقد وصلت غياباتك إلى مرحلة الخطر (15% فأكثر) في مقرر:\n**{subject_to_interrogate}**\n\n🛑 **النظام مغلق حتى تُكمل الإقرار!**\n1️⃣ هل تعلم أنك اقتربت من الحرمان؟"
                    return await update.message.reply_text(warning_msg, parse_mode='Markdown', reply_markup=get_cancel_menu())
                
                if has_deprivation: m += f"\n\n🛑 **تنبيه إداري:** أنت محروم في مقرر أو أكثر. راجع الإدارة."
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **الرقم التدريبي غير مسجل أو لا توجد غيابات.**", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ **حدث خطأ:** `{str(e)}`", parse_mode='Markdown')
        return

    # 3. الردود الثابتة
    if text == "📚 الحقائب التدريبية": 
        return await update.message.reply_text("📚 **الحقائب التدريبية:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول للمستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🔗 المنصات الإلكترونية": 
        kb = [[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")], [InlineKeyboardButton("بلاك بورد", url="https://lms.elearning.edu.sa/")]]
        return await update.message.reply_text("🌐 **المنصات الإلكترونية:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    if text == "📍 موقع القسم": 
        return await update.message.reply_text("📍 **موقع قسم الحاسب:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": 
        return await update.message.reply_text("📰 **أخبار المعهد:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 حساب منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📅 التقويم التدريبي":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        if os.path.exists('calendar.jpg'): return await update.message.reply_photo(photo=open('calendar.jpg', 'rb'))
        else: return await update.message.reply_text("⚠️ ملف التقويم قيد التحديث.")
    if text == "📘 دليل المتدرب الرسمي":
        if os.path.exists("trainee_guide.pdf"): return await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 **دليل المتدرب الرسمي**", parse_mode='Markdown')
        else: return await update.message.reply_text("⚠️ **جاري التحديث من قبل الإدارة.**", parse_mode='Markdown')
    
    if text == "❓ الأسئلة الشائعة":
        faq_msg = (
            "🏛️ **اللوائح والأنظمة التدريبية الشائعة** 🏛️\n"
            f"{SEP}\n"
            "📌 **لائحة الحرمان وطي القيد:**\n"
            "يُحرم المتدرب من المقرر التدريبي ويُطوى قيده نظامياً في حال بلوغ نسبة الغياب حد الـ (20%).\n\n"
            "💳 **ضوابط المكافأة الشهرية:**\n"
            "تُصرف للمتدرب مكافأة مالية قدرها (800 ريال)، ويُعلق صرفها آلياً في حال انخفاض المعدل التراكمي عن (2.00).\n\n"
            "🎓 **درجة الاجتياز الأكاديمي:**\n"
            "الحد الأدنى لاجتياز المقررات التدريبية واعتبار المتدرب ناجحاً في نظام المعاهد هو الحصول على (50) درجة.\n"
            f"{SEP}\n"
            "💡 *للاطلاع على اللوائح كاملة، يرجى تصفح (دليل المتدرب الرسمي) من القائمة.*"
        )
        return await update.message.reply_text(faq_msg, parse_mode='Markdown')
        
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]:
        plans = load_json("plans.json")
        return await update.message.reply_text(f"{plans.get(text, 'جاري التحديث')}\n{SEP}\n🔗 **لتحميل المنهج:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 تحميل", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "📄 الخطط التدريبية":
        return await update.message.reply_text("📄 **اختر الفصل:**", reply_markup=get_plans_menu(), parse_mode='Markdown')
    if text == "🕹️ قسم الألعاب والإضافات":
        return await update.message.reply_text("🕹️ **اختر النشاط:**", reply_markup=get_games_menu(), parse_mode='Markdown')
    if text == "💡 نصيحة تقنية":
        return await update.message.reply_text(random.choice(TECH_TIPS), parse_mode='Markdown')
    if text == "🌐 أخبار التقنية":
        try:
            req = urllib.request.Request("https://www.tech-wd.com/wd/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 **الأخبار التقنية**\n{SEP}\n"
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
        return await update.message.reply_text(f"❓ **تحدي الأسبوع:**\n\n{q['q']}\n\n⚠️ أمامك 15 ثانية:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: return await update.message.reply_text("📉 لا يوجد نقاط مسجلة.", parse_mode='Markdown')
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        return await update.message.reply_text(f"🏆 **بطل الأسبوع:** {top['name']}\n🌟 **النقاط:** {top['score']}", parse_mode='Markdown')

    await update.message.reply_text("⚠️ **الرجاء اختيار خدمة من الأسفل 👇**", reply_markup=get_main_menu())

# --- 🌟 محرك سحب رايات والأعذار 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ **جاري السحب وفك تشفير اللغة العربية...**", parse_mode='Markdown')
            
            try:
                file = await context.bot.get_file(doc.file_id)
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    with open(temp_file, 'rb') as f: raw_bytes = f.read()
                    best_enc = 'utf-8-sig' 
                    for enc in ['utf-8-sig', 'windows-1256', 'cp1256', 'utf-8', 'iso-8859-6']:
                        try:
                            text = raw_bytes.decode(enc)
                            if 'المتدرب' in text or 'المقرر' in text or 'الغياب' in text:
                                best_enc = enc; break 
                        except: pass
                            
                    df_raw = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
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
                await status_msg.edit_text(f"✅ **نجاح ساحق!**\n📊 **النتيجة:** حفظ `{records_count}` متدرب.\n🌐 **السحابة:** {github_status}", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

    if update.message.photo or update.message.document:
        state = user_states.get(user_id, {})
        caption_text = update.message.caption
        
        stu_id = ''.join(filter(str.isdigit, str(caption_text)))
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 **مرفوض: وصف غير مكتمل!**\nيجب أن تقوم بإرفاق الصورة مرة أخرى وتأكد من كتابة **رقمك التدريبي** في الوصف لكي يتم ربطه بملفك.", parse_mode='Markdown', reply_markup=get_cancel_menu() if state.get('flow') == 'excuse' else get_main_menu())
            
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري الختم الآلي...")
        
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
                await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 **عذر مختوم:**\n{caption_text}\n⏱️ {timestamp}", parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر مرفق:**\n{caption_text}\n{timestamp}")
                await update.message.copy(chat_id=GROUP_ID)
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ **تم الختم والإرسال للإدارة بنجاح.**", parse_mode='Markdown')
            await update.message.reply_text("العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
        except:
            await status_msg.edit_text("⚠️ **خطأ فني أثناء الإرسال.**", parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    if query.data.startswith("ans_"):
        parts = query.data.split("_")
        q_idx, sel = int(parts[1]), int(parts[2])
        try:
            actual_question = QUESTIONS[q_idx]
            m = "🎉 **إجابة صحيحة!**" if sel == actual_question["answer"] else f"❌ **خاطئة!**"
            await query.edit_message_text(f"❓ **تحدي الأسبوع:**\n{actual_question['q']}\n{SEP}\n{m}", parse_mode='Markdown')
        except: pass

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) 
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("start", start))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النسخة الماسية النهائية (Ultimate Diamond Edition)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
