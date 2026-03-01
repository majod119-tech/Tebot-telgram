import os
import io
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

# --- 🌟 دوال مساعدة لضمان استقرار السيرفر ---
def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {}
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file:
            json.dump(d, file, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving JSON: {e}")

try:
    from questions_bank import QUESTIONS
except Exception as e:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

# --- 1. الإعدادات والبيانات الأساسية ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "\n━━━━━━━━━━━━━━\n"
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
        except Exception: pass
        time.sleep(3600)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            stats = load_json(STATS_FILE)
            scores = load_json(SCORES_FILE)
            html = f"""
            <html><head><title>لوحة قيادة قسم الحاسب</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Arial; direction: rtl; background: #f4f7f6; padding: 20px; text-align: center; }}
                .card-container {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-bottom: 30px; }}
                .card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 220px; }}
                .card h3 {{ color: #2c3e50; font-size: 18px; }}
                .card p {{ font-size: 28px; color: #27ae60; font-weight: bold; margin: 10px 0 0 0; }}
                table {{ margin: 0 auto; width: 90%; max-width: 800px; background: white; border-radius: 12px; border-collapse: collapse; }}
                th, td {{ padding: 15px; border-bottom: 1px solid #ddd; text-align: center; }}
                th {{ background: #27ae60; color: white; font-size: 18px; }}
            </style></head><body>
            <h1 style="color:#2c3e50;">📊 الإحصائيات الرسمية للمساعد الذكي</h1>
            <div class="card-container">
                <div class="card"><h3>👥 إجمالي المتدربين</h3><p>{len(stats.get('users_list', []))}</p></div>
                <div class="card"><h3>🤖 استفسارات الذكاء الاصطناعي</h3><p>{stats.get('ai_questions', 0)}</p></div>
                <div class="card"><h3>🎮 التحديات المنجزة</h3><p>{stats.get('quiz_attempts', 0)}</p></div>
            </div>
            <h2 style="color:#2c3e50;">🏆 لوحة الشرف الأسبوعية</h2>
            <table><tr><th>الاسم</th><th>النقاط</th><th>عدد الإجابات</th></tr>
            {"".join([f"<tr><td>{v['name']}</td><td style='color:#27ae60; font-weight:bold;'>{v['score']}</td><td>{len(v.get('answered', []))}</td></tr>" for k,v in sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)])}
            </table></body></html>"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Server Online. Access /stats for dashboard.")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 3. عقل المعلم الذكي ---
AI_KNOWLEDGE = f"""
أنت المعلم الذكي الرسمي لقسم الحاسب الآلي وتقنية المعلومات في المعهد الصناعي الثانوي ببريدة (مؤسسة التدريب التقني والمهني).
أجب باختصار شديد ومهنية. اعتمد على أنظمة دليل المتدرب التالية في إجاباتك إذا سئلت:
- الغياب والحرمان: إنذار عند 15% وحرمان نهائي عند 20%. يُطوى القيد إذا انقطع المتدرب أسبوعين متتاليين.
- المكافأة: 800 ريال لمتدربي المعاهد (يخصم 5 للصندوق). توقف إذا قل المعدل التراكمي عن 2.00.
- درجات النجاح: درجة الاجتياز في المعاهد 50، وفي الكليات التقنية 60.
- الحقائب التدريبية: {DRIVE_LINK}
- المنصات الثلاث: 
  1. رايات: للجدول، الغياب، والسجل التدريبي (rayat.tvtc.gov.sa)
  2. بلاك بورد: للمحتوى والاختبارات (lms.elearning.edu.sa)
  3. تقني: (tvtclms.edu.sa)
"""

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''))
                break
    except Exception as e: 
        print(f"Gemini Init Error: {e}")

ai_sessions, feedback_sessions, active_challenges, interrogation_sessions = {}, {}, {}, {}

TECH_TIPS = [
    "💡 **نصيحة أمنية:** استخدم `Win + L` لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ **نصيحة تقنية:** احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات.",
    "🚀 **نصيحة برمجية:** التنسيق والمسافات البادئة في لغة بايثون هي أساس عمل الكود."
]

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

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID: return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
    await update.message.reply_text("⏳ جاري تجهيز وإرسال النسخة الاحتياطية للقسم...")
    files_to_backup = ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json', 'plans.json']
    sent_any = False
    for file in files_to_backup:
        if os.path.exists(file):
            await context.bot.send_document(chat_id=user_id, document=open(file, 'rb'))
            sent_any = True
    if sent_any:
        await update.message.reply_text("✅ **تم الانتهاء من النسخ الاحتياطي بنجاح.**", parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ لم يتم العثور على ملفات للنسخ الاحتياطي.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID: return
    
    announcement = update.message.text.replace('/broadcast', '').strip()
    if not announcement:
        await update.message.reply_text("⚠️ الطريقة الصحيحة: `/broadcast نصل التعميم هنا`", parse_mode='Markdown')
        return

    stats = load_json(STATS_FILE)
    users = stats.get("users_list", [])
    if not users:
        await update.message.reply_text("⚠️ لا يوجد متدربين مسجلين في النظام بعد.")
        return

    await update.message.reply_text(f"📢 جاري إرسال التعميم لـ {len(users)} متدرب...")
    success_count = 0
    
    for u in users:
        try:
            await context.bot.send_message(chat_id=u, text=f"📢 **إعلان إداري هام:**\n{SEP}{announcement}", parse_mode='Markdown')
            success_count += 1
        except Exception:
            pass 
            
    await update.message.reply_text(f"✅ **تم إرسال التعميم بنجاح لـ {success_count} متدرب.**", parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    stats = load_json(STATS_FILE)
    users = stats.get("users_list", [])
    if user_id not in users: 
        users.append(user_id)
        stats["users_list"] = users
        save_json(STATS_FILE, stats)
    
    ai_sessions[user_id] = False
    feedback_sessions[user_id] = False
    
    welcome_msg = (
        f"أهلاً بك يا {update.effective_user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨{SEP}"
        f"أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n"
        f"👇 **الرجاء اختيار الخدمة المطلوبة من القائمة السفلية لبدء العمل:**"
    )
    
    try:
        if os.path.exists('IMG_1058.jpeg'):
            await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else:
            logo_url = "https://pbs.twimg.com/profile_images/1684496035272658944/p02_gM0p_400x400.jpg"
            await update.message.reply_photo(photo=logo_url, caption=welcome_msg, reply_markup=get_main_menu())
    except Exception:
        await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if user_id in interrogation_sessions:
        session = interrogation_sessions[user_id]
        step = session['step']
        if step == 1:
            session['aware_answer'] = text; session['step'] = 2
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_text("2️⃣ **ما هو العذر الرئيسي لغياباتك؟**\n(اكتب عذرك بالتفصيل...)", parse_mode='Markdown')
            return
        elif step == 2:
            session['excuse_answer'] = text; session['step'] = 3
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_text("3️⃣ **هل تتعهد بالانضباط لتفادي الحرمان (20%)؟**\n(أجب بنعم أو أتعهد)", parse_mode='Markdown')
            return
        elif step == 3:
            session['pledge_answer'] = text
            completed = load_json(INTERROGATIONS_FILE)
            if session['stu_num'] not in completed: completed[session['stu_num']] = []
            completed[session['stu_num']].append(session['subject'])
            save_json(INTERROGATIONS_FILE, completed)
            
            report = f"🚨 **تعهد (إنذار 15%)** 🚨\n\n👤 **المتدرب:** {session['stu_nam']} ({session['stu_num']})\n📖 **المادة:** {session['subject']}\n❓ **علم بالإنذار:** {session['aware_answer']}\n📝 **العذر:** {session['excuse_answer']}\n✍️ **الإقرار:** {session['pledge_answer']}"
            try: await context.bot.send_message(chat_id=GROUP_ID, text=report, parse_mode='Markdown')
            except Exception: pass
            del interrogation_sessions[user_id]
            await update.message.reply_text("✅ **تم توثيق إقرارك.**\nاحرص على الحضور. تم رفع الإيقاف عنك.", reply_markup=get_main_menu(), parse_mode='Markdown')
            return

    if text in ["🔙 الرجوع للقائمة الرئيسية", "📚 الحقائب التدريبية", "📄 الخطط التدريبية", "📊 استعلام الغياب", "📝 رفع الغياب والأعذار", "🔗 المنصات الإلكترونية", "📅 التقويم التدريبي", "📰 أخبار القسم والمعهد", "📍 موقع القسم", "❓ الأسئلة الشائعة", "📘 دليل المتدرب الرسمي", "📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]:
        ai_sessions[user_id] = False
        feedback_sessions[user_id] = False

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 **تم العودة للقائمة الرئيسية.**", reply_markup=get_main_menu())
        return

    if text == "📘 دليل المتدرب الرسمي":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        if os.path.exists("trainee_guide.pdf"):
            await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 **دليل المتدرب الرسمي (الإصدار الأخير)**\nيحتوي على كافة اللوائح، حقوق وواجبات المتدرب، والمكافآت.", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ **عذراً، جاري تحديث ملف الدليل من قبل الإدارة.**\nيرجى المحاولة لاحقاً.", parse_mode='Markdown')
        return

    if text == "❓ الأسئلة الشائعة":
        faq_msg = (
            f"❓ **الأسئلة الشائعة (بناءً على دليل المتدرب الرسمي):**{SEP}"
            f"🔹 **متى يقع الحرمان أو طي القيد؟**\n"
            f"تُحرم من المادة عند غياب (20%)، ويُطوى قيدك إذا انقطعت أسبوعين متتاليين أو قل معدلك عن 1.75 كمتدرب مستجد.\n\n"
            f"🔹 **كم تبلغ المكافأة الشهرية ومتى تنقطع؟**\n"
            f"تبلغ (1000 ريال) للكليات التقنية، و (800 ريال) للمعاهد الصناعية. وتتوقف إذا قل معدلك التراكمي عن (2.00) أو صدر بحقك حرمان/فصل.\n\n"
            f"🔹 **كم درجة النجاح في المقررات؟**\n"
            f"درجة الاجتياز في المعاهد هي (50)، وفي الكليات التقنية (60).\n\n"
            f"🔹 **ما هو الحد الأدنى والأعلى لتسجيل المواد؟**\n"
            f"الحد الأدنى 12 وحدة تدريبية، والحد الأعلى 24 وحدة للفصل.\n\n"
            f"🔹 **هل توجد مكافأة للمتفوقين؟**\n"
            f"نعم، (1000 ريال) فصلياً بشروط لمعدل 4.85 فأعلى، و (2000 ريال) للخريج بمعدل 4.75 فأعلى."
        )
        await update.message.reply_text(faq_msg, parse_mode='Markdown')
        return

    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        await update.message.reply_text("🤖 **المعلم الذكي!**\n💬 **اكتب سؤالك التقني أو الإداري وسأجيبك فوراً...**\n*(للخروج اضغط رجوع)*", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم غير متصل.", reply_markup=get_back_menu())
            return
        update_stat("ai_questions")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
            clean_text = response.text.replace("**", "").replace("* ", "🔹 ").strip()
            await update.message.reply_text(f"📝 رد المعلم الذكي:\n{SEP}{clean_text}", reply_markup=get_back_menu())
        except Exception: 
            await update.message.reply_text("⚠️ **حدث خطأ، حاول لاحقاً.**", reply_markup=get_back_menu())
        return

    if text == "📬 الاقتراحات والشكاوى":
        feedback_sessions[user_id] = True
        await update.message.reply_text("📬 **الاقتراحات والشكاوى**\nاكتب رسالتك الآن وستصل للإدارة بسرية...", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if feedback_sessions.get(user_id) == True:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 **شكوى/مقترح:**\nالمرسل: {update.effective_user.first_name}\nالنص: {text}")
            feedback_sessions[user_id] = False
            await update.message.reply_text("✅ **تم استلام رسالتك.**", reply_markup=get_main_menu(), parse_mode='Markdown')
        except:
            await update.message.reply_text("⚠️ فشل الإرسال.", reply_markup=get_main_menu())
        return

    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]:
        plans = load_json("plans.json")
        if not plans: 
            await update.message.reply_text("⚠️ ملف الخطط (plans.json) قيد التحديث من قبل الإدارة.")
            return
            
        reply_msg = f"{plans.get(text, '')}{SEP}🔗 **لتحميل المنهج اضغط الزر بالأسفل:**"
        keyboard = [[InlineKeyboardButton("📥 تحميل الحقائب الرسمية", url=DRIVE_LINK)]]
        await update.message.reply_text(reply_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 **اختر الفصل:**", reply_markup=get_plans_menu(), parse_mode='Markdown')
        return

    if text == "🕹️ قسم الألعاب والإضافات":
        await update.message.reply_text("🕹️ **اختر النشاط:**", reply_markup=get_games_menu(), parse_mode='Markdown')
        return

    if text == "💡 نصيحة تقنية":
        await update.message.reply_text(random.choice(TECH_TIPS), parse_mode='Markdown')
        return

    if text == "🌐 أخبار التقنية":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            req = urllib.request.Request("https://www.tech-wd.com/wd/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 **موجز الأخبار التقنية**{SEP}"
            for i, item in enumerate(root.findall('.//item')):
                if i >=
