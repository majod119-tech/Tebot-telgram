import os
import pandas as pd
import json
import random
import time
import urllib.request
import xml.etree.ElementTree as ET
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 🌟 استدعاء بنك الأسئلة الخارجي بأمان ---
try:
    from questions_bank import QUESTIONS
except ImportError:
    print("⚠️ تنبيه: ملف questions_bank.py غير موجود. تم وضع سؤال احتياطي.")
    QUESTIONS = [
        {"q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}
    ]

# --- 1. سيرفر الويب المطور (Dashboard) ---
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
                table {{ margin: 0 auto; width: 90%; max-width: 800px; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border-collapse: collapse; }}
                th, td {{ padding: 15px; border-bottom: 1px solid #ddd; text-align: center; }}
                th {{ background: #27ae60; color: white; font-size: 18px; }}
                tr:hover {{ background-color: #f1f1f1; }}
            </style></head><body>
            <h1 style="color:#2c3e50; border-bottom: 3px solid #27ae60; display: inline-block; padding-bottom: 10px;">📊 لوحة إحصائيات النظام الذكي</h1>
            <div class="card-container">
                <div class="card"><h3>👥 إجمالي المستخدمين</h3><p>{len(stats.get('users_list', []))}</p></div>
                <div class="card"><h3>🤖 أسئلة المعلم الذكي</h3><p>{stats.get('ai_questions', 0)}</p></div>
                <div class="card"><h3>🎮 محاولات التحدي</h3><p>{stats.get('quiz_attempts', 0)}</p></div>
            </div>
            <h2 style="color:#2c3e50;">🏆 قائمة المتصدرين (لوحة الشرف)</h2>
            <table><tr><th>الاسم</th><th>إجمالي النقاط</th><th>التحديات المنجزة</th></tr>
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

# --- 2. الإعدادات والبيانات الأساسية ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "\n━━━━━━━━━━━━━━\n"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

# إعدادات المعلم الذكي
AI_KNOWLEDGE = f"""
أنت المعلم الذكي لقسم الحاسب الآلي في المعهد الصناعي الثانوي.
التعليمات الصارمة لك:
1. أجب باختصار شديد وبشكل مباشر في صلب الموضوع.
2. لا تقم بالترحيب الطويل، ولا تكرر وظائفك أو الروابط إلا إذا سألك المتدرب عنها تحديداً.
3. اشرح المفاهيم التقنية بأسلوب مبسط وعملي.
4. معلومات القسم (لا تذكرها إلا عند السؤال):
   - الحقائب: {DRIVE_LINK}
   - الغياب: إنذار عند 15%، حرمان عند 20%. قل للمتدرب: "لمعرفة غيابك أدخل رقمك التدريبي في القائمة الرئيسية".
"""

# نظام الاستكشاف التلقائي لموديل الذكاء الاصطناعي
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        selected_model_name = None
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.replace('models/', '')
                selected_model_name = model_name
                if 'flash' in model_name.lower():
                    break
        if selected_model_name:
            ai_model = genai.GenerativeModel(selected_model_name)
    except Exception as e: 
        ai_model = None

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"

def load_json(f): return json.load(open(f, "r")) if os.path.exists(f) else {}
def save_json(f, d): json.dump(d, open(f, "w"))
def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

ai_sessions = {}
feedback_sessions = {}
active_challenges = {}

TECH_TIPS = [
    "💡 **نصيحة أمنية:** استخدم اختصار `Win + L` لقفل شاشة جهازك فوراً عند الابتعاد عنه لحماية بياناتك.",
    "🛡️ **نصيحة تقنية:** احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات الأمنية المكتشفة حديثاً.",
    "🚀 **نصيحة برمجية:** في لغة بايثون، التنسيق والمسافات البادئة (Indentation) هي أساس عمل الكود وليست للجماليات فقط.",
    "🌐 **نصيحة شبكات:** عنوان `127.0.0.1` يُعرف بـ Localhost ويستخدم لاختبار كرت الشبكة في جهازك دون الحاجة لإنترنت."
]

# --- 3. تصميم القوائم ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المعلم الذكي (الدليل الشامل)"], 
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        ["📬 قسم الاقتراحات والشكاوى"],
        ["🕹️ قسم الألعاب والإضافات"]
    ], resize_keyboard=True, is_persistent=True)

def get_plans_menu():
    return ReplyKeyboardMarkup([
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"],
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"],
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"],
        ["🖥️ برامج فصلية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_games_menu():
    return ReplyKeyboardMarkup([
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"],
        ["💡 نصيحة تقنية", "🌐 أخبار التقنية"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_back_menu(): 
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 4. المنطق البرمجي والمحتوى المفصل ---
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
        f"أهلاً بك يا {update.effective_user.first_name} في بوت قسم الحاسب وتقنية المعلومات 💻✨{SEP}"
        f"أنا مساعدك الرقمي، تم تصميمي لتسهيل رحلتك التدريبية.\n"
        f"يمكنك من خلالي استعراض الخطط، تحميل الحقائب، متابعة غيابك، وحتى سؤالي عن أي استفسار تقني!\n\n"
        f"👇 **الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:**"
    )
    
    try:
        if os.path.exists('IMG_1058.jpeg'):
            await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else:
            logo_url = "https://pbs.twimg.com/profile_images/1684496035272658944/p02_gM0p_400x400.jpg"
            await update.message.reply_photo(photo=logo_url, caption=welcome_msg, reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if text in ["🔙 الرجوع للقائمة الرئيسية", "📚 الحقائب التدريبية", "📄 الخطط التدريبية", "📊 استعلام الغياب", "📝 رفع الغياب والأعذار", "🔗 منصة تقني ورايات", "📅 التقويم التدريبي", "📰 أخبار القسم والمعهد", "📍 موقع القسم", "📬 قسم الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]:
        ai_sessions[user_id] = False
        feedback_sessions[user_id] = False

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 **تم العودة للقائمة الرئيسية.**\nاختر الخدمة التي تريدها من الأسفل 👇", reply_markup=get_main_menu())
        return

    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        guide_msg = (
            f"🤖 **المعلم الذكي في خدمتك!**{SEP}"
            f"أنا مدعوم بتقنيات الذكاء الاصطناعي لمساعدتك في فهم تخصصك.\n\n"
            f"💬 **اكتب سؤالك التقني الآن في رسالة وسأقوم بالرد عليك باختصار...**\n"
            f"*(للخروج من هذه المحادثة، اضغط على زر الرجوع)*"
        )
        await update.message.reply_text(guide_msg, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم الذكي غير متصل حالياً بسبب مشكلة في المفتاح.", reply_markup=get_back_menu())
            return
            
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ أقرأ سؤالك...")
        try:
            prompt = f"{AI_KNOWLEDGE}\nسؤال المتدرب: {text}"
            response = await ai_model.generate_content_async(prompt)
            await status_msg.delete()
            clean_text = response.text.replace("**", "").replace("* ", "🔹 ").strip()
            reply_text = f"📝 رد المعلم الذكي:\n{SEP}{clean_text}\n\n💡 هل لديك سؤال آخر؟ اكتبه مباشرة!"
            await update.message.reply_text(reply_text, reply_markup=get_back_menu())
        except Exception as e: 
            await status_msg.delete()
            await update.message.reply_text(f"⚠️ **عذراً، واجهت مشكلة تقنية.**\n\nالرجاء المحاولة لاحقاً.", reply_markup=get_back_menu())
        return

    if text == "📬 قسم الاقتراحات والشكاوى":
        feedback_sessions[user_id] = True
        msg = (
            f"📬 **قسم الاقتراحات والشكاوى**{SEP}"
            f"رأيك يهمنا جداً في تطوير القسم وخدماته.\n"
            f"سواء كان لديك فكرة جديدة، أو ملاحظة، أو مشكلة واجهتك، اكتبها هنا وسوف تصل مباشرة وبسرية لإدارة القسم.\n\n"
            f"✍️ **اكتب رسالتك الآن في الأسفل...**"
        )
        await update.message.reply_text(msg, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if feedback_sessions.get(user_id) == True:
        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 **رسالة من قسم الاقتراحات والشكاوى:**\nالمرسل: {update.effective_user.first_name}\nالرسالة: {text}")
            feedback_sessions[user_id] = False
            await update.message.reply_text("✅ **تم استلام رسالتك بنجاح.** شكراً لتواصلك ومساهمتك في التطوير!", reply_markup=get_main_menu(), parse_mode='Markdown')
        except:
            await update.message.reply_text("⚠️ عذراً، فشل إرسال الرسالة إلى الإدارة. تأكد من إعدادات البوت.", reply_markup=get_main_menu())
        return

    term_plans = {
        "1️⃣ الفصل الأول": "📚 **مقررات الفصل التدريبي الأول:**\n🔹 ثقافة إسلامية 1\n🔹 لغة إنجليزية 1\n🔹 رياضيات 1\n🔹 فيزياء\n🔹 التربية البدنية 1\n🔹 لغة عربية 1\n🔹 أساسيات الحاسب الآلي\n🔹 مدخل إلى مهارات القرن 21\n🔹 السلامة والصحة المهنية",
        "2️⃣ الفصل الثاني": "📚 **مقررات الفصل التدريبي الثاني:**\n🔹 سلوك مهني\n🔹 لغة عربية 2\n🔹 لغة إنجليزية 2\n🔹 رياضيات 2\n🔹 التربية البدنية 2\n🔹 ثقافة إسلامية 2\n🔹 ورش تأسيسية\n🔹 تطبيقات الحاسب الآلي\n🔹 مهارات التواصل والتعاون\n🔹 التفكير الناقد والإبداعي",
        "3️⃣ الفصل الثالث": "📚 **مقررات الفصل التدريبي الثالث:**\n🔹 ثقافة إسلامية 3\n🔹 الرسم الهندسي\n🔹 بحث ومصادر المعلومات\n🔹 رياضيات 3\n🔹 لغة إنجليزية 3\n🔹 أجهزة وقياس\n🔹 أساسيات الكهرباء\n🔹 أساسيات الإلكترونيات\n🔹 تطبيقات مفتوحة المصدر",
        "4️⃣ الفصل الرابع": "📚 **مقررات الفصل التدريبي الرابع:**\n🔹 مقدمة في ريادة الأعمال\n🔹 تقنيات الانترنت\n🔹 مكونات الحاسب 1\n🔹 لغة برمجة 1\n🔹 أساسيات الشبكات\n🔹 رسم الشبكات بالحاسب\n🔹 أساسيات نظام لينكس\n🔹 أنشطة مهنية",
        "5️⃣ الفصل الخامس": "📚 **مقررات الفصل التدريبي الخامس:**\n🔹 مكونات الحاسب 2\n🔹 صيانة الأجهزة الكفية\n🔹 لغة برمجة 2\n🔹 تمديد الكيابل النحاسية\n🔹 شبكات الحاسب\n🔹 نظام تشغيل الشبكة 1\n🔹 مشاريع إنتاجية\n🔹 أنشطة مهنية 2",
        "6️⃣ الفصل السادس": "📚 **مقررات الفصل التدريبي السادس:**\n🔹 مبادئ قواعد البيانات\n🔹 طرفيات الحاسب\n🔹 مهارات صيانة الحاسب\n🔹 تمديد كيابل الألياف الضوئية\n🔹 نظام تشغيل الشبكة 2\n🔹 تدريب إنتاجي\n🔹 أنشطة مهنية 3",
        "🖥️ برامج فصلية": "📚 **البرامج القصيرة المساندة:**\n🔹 برنامج إدخال البيانات ومعالجة النصوص"
    }

    if text in term_plans:
        reply_msg = f"{term_plans[text]}{SEP}🔗 **لتحميل ملفات الحقائب التدريبية الخاصة بهذه المواد، اضغط على الرابط التالي:**\n{DRIVE_LINK}"
        await update.message.reply_text(reply_msg, parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "📄 الخطط التدريبية":
        msg = (
            f"📄 **الخطط التدريبية الشاملة**{SEP}"
            f"هنا يمكنك استعراض جميع المقررات الدراسية المطلوبة لاجتياز الدبلوم.\n"
            f"👇 **الرجاء اختيار الفصل التدريبي الذي تبحث عنه من القائمة أدناه:**"
        )
        await update.message.reply_text(msg, reply_markup=get_plans_menu(), parse_mode='Markdown')
        return

    if text == "🕹️ قسم الألعاب والإضافات":
        msg = (
            f"🕹️ **ساحة الأنشطة والتفاعل**{SEP}"
            f"هذا القسم مخصص للترفيه والفائدة!\n"
            f"يمكنك هنا اختبار معلوماتك في (تحدي الأسبوع)، معرفة المتصدرين في (بطل الأسبوع)، أو متابعة (أخبار التقنية).\n\n"
            f"👇 **اختر النشاط الذي تفضله:**"
        )
        await update.message.reply_text(msg, reply_markup=get_games_menu(), parse_mode='Markdown')
        return

    if text == "💡 نصيحة تقنية":
        await update.message.reply_text(random.choice(TECH_TIPS), parse_mode='Markdown')
        return

    if text == "🌐 أخبار التقنية":
        status_msg = await update.message.reply_text("⏳ جاري سحب أحدث الأخبار التقنية...")
        try:
            url = "https://aitnews.com/feed/"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            xml_data = response.read()
            root = ET.fromstring(xml_data)

            news_msg = f"🌐 **موجز الأخبار التقنية (تحديث تلقائي)**{SEP}"
            count = 0
            for item in root.findall('.//item'):
                title = item.find('title').text
                link = item.find('link').text
                news_msg += f"🔹 [{title}]({link})\n\n"
                count += 1
                if count >= 3: 
                    break
            
            await status_msg.edit_text(news_msg, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            await status_msg.edit_text("⚠️ **عذراً، مصدر الأخبار لا يستجيب حالياً.**\nالرجاء المحاولة بعد قليل.", parse_mode='Markdown')
        return

    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        active_challenges[user_id] = time.time()
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        await update.message.reply_text(f"❓ **تحدي الأسبوع:**\n\n{q['q']}\n\n⚠️ أمامك 15 ثانية فقط للإجابة، اختر من الخيارات أدناه:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: 
            await update.message.reply_text("📉 لم يتم تسجيل أي نقاط لأي متدرب حتى الآن. كن أنت المبادر الأول!", parse_mode='Markdown')
            return
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        msg = (
            f"🏆 **لوحة شرف قسم الحاسب**{SEP}"
            f"🥇 **المتصدر لهذا الأسبوع:** {top['name']}\n"
            f"🌟 **الرصيد:** {top['score']} نقطة\n\n"
            f"تهانينا للبطل! شارك في (تحدي الأسبوع) لتخطف المركز الأول. 💪"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text == "📊 استعلام الغياب":
        msg = (
            f"🔎 **نظام استعلام الغياب الذكي**{SEP}"
            f"هذا النظام يتيح لك معرفة نسبة غيابك الحالية في جميع المواد التدريبية.\n\n"
            f"⚠️ **تنبيه:** يتم توجيه إنذار للمتدرب عند بلوغ غيابه 15%، ويُحرم من المادة عند بلوغ 20%.\n\n"
            f"👇 **الرجاء إرسال (رقمك التدريبي) المكون من أرقام فقط الآن للبحث في السجلات...**"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري البحث في سجلات القسم...")
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            res = df[df['stu_num'].astype(str).str.strip() == text]
            await status_msg.delete()
            
            if not res.empty:
                m = f"✅ **تم العثور على السجل التدريبي لـ:** `{res.iloc[0]['stu_nam']}`{SEP}"
                for _, r in res.iterrows(): 
                    val = float(r['parsnt'])
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ إنذار" if val >= 15 else "🟢 منتظم")
                    m += f"📖 {r['c_nam']}: %{val} {icon}\n"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **عذراً، الرقم التدريبي الذي أدخلته غير مسجل لدينا.**\nيرجى التأكد من كتابة الرقم بشكل صحيح باللغة الإنجليزية.", parse_mode='Markdown')
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text("⚠️ **حدث خطأ فني:** ملف الغياب (data.xlsx) غير متوفر في السيرفر حالياً. يرجى مراجعة إدارة القسم.", parse_mode='Markdown')
        return

    if text == "📝 رفع الغياب والأعذار": 
        msg = (
            f"📝 **بوابة رفع الأعذار**{SEP}"
            f"لضمان قبول عذرك (الطبي أو الرسمي) وعدم احتسابه في نسبة الحرمان، اتبع الخطوات التالية بدقة:\n\n"
            f"1️⃣ التقط صورة واضحة لورقة العذر.\n"
            f"2️⃣ اكتب (رقمك التدريبي + اسمك) في خانة الوصف (Caption) للصورة.\n"
            f"3️⃣ أرسل الصورة هنا في المحادثة وسنقوم بتسليمها للإدارة فوراً."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return
        
    if text == "📚 الحقائب التدريبية": 
        msg = (
            f"📚 **المستودع الرقمي للحقائب التدريبية**{SEP}"
            f"جميع الكتب والمقررات التدريبية الخاصة بالمؤسسة العامة للتدريب التقني والمهني متوفرة بصيغة PDF.\n\n"
            f"🔗 **للدخول والتحميل اضغط على الرابط التالي:**\n{DRIVE_LINK}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=True)
        return
        
    if text == "🔗 منصة تقني ورايات": 
        msg = (
            f"🌐 **روابط المنصات الإلكترونية الهامة**{SEP}"
            f"🔹 **منصة التدريب الإلكتروني (تقني):** للمحاضرات عن بعد والواجبات.\nhttps://tvtclms.edu.sa\n\n"
            f"🔹 **بوابة المتدربين (رايات):** للجداول والدرجات الرسمية.\nhttps://rayat.tvtc.gov.sa"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=True)
        return
        
    if text == "📍 موقع القسم": 
        await update.message.reply_text(f"📍 **الموقع الجغرافي لقسم الحاسب الآلي:**{SEP}http://googleusercontent.com/maps.google.com/3", parse_mode='Markdown')
        return
        
    if text == "📰 أخبار القسم والمعهد": 
        msg = (
            f"📰 **لوحة الإعلانات والأخبار**{SEP}"
            f"لمتابعة أحدث الإعلانات والتغطيات الرسمية لقسم الحاسب والمعهد، نرجو زيارة حسابنا الرسمي على منصة X.\n\n"
            f"👇 **اضغط على الزر أدناه للذهاب مباشرة:**"
        )
        keyboard = [[InlineKeyboardButton("📱 عرض آخر الأخبار في منصة X", url=TVTC_X_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        return
        
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'): 
            await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption="📅 التقويم التدريبي المعتمد للفصل الحالي.")
        else: 
            await update.message.reply_text("⚠️ **عذراً:** ملف صورة التقويم التدريبي غير متوفر في النظام حالياً.", parse_mode='Markdown')
        return

    if not ai_sessions.get(user_id) and not feedback_sessions.get(user_id):
        await update.message.reply_text("⚠️ **عذراً، لم أتعرف على طلبك.**\nالرجاء اختيار إحدى الخدمات من القائمة المتاحة أدناه 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption: 
        await update.message.reply_text("⚠️ **خطأ في الرفع:**\nالرجاء إرفاق الصورة مرة أخرى، والتأكد من كتابة **رقمك التدريبي** في خانة الوصف (Caption) للصورة ليتم قبول عذرك.", parse_mode='Markdown')
        return
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر طبي/رسمي جديد:**\nالمرسل: {update.effective_user.first_name}\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ **تم استلام عذرك بنجاح.**\nسيتم مراجعته من قبل مشرفي القسم قريباً. شكراً لك!", parse_mode='Markdown')
    except Exception as e: 
        await update.message.reply_text("⚠️ **خطأ فني:** تعذر إرسال العذر لمجموعة الأرشيف. الرجاء التأكد من إضافة البوت كمشرف في المجموعة.", parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    if query.data.startswith("ans_"):
        start_time = active_challenges.get(user_id, 0)
        time_taken = time.time() - start_time
        parts = query.data.split("_")
        q_idx, sel = int(parts[1]), int(parts[2])
        
        sc = load_json(SCORES_FILE)
        ui = sc.get(user_id, {"name": query.from_user.first_name, "score": 0, "answered": []})
        
        if time_taken > 15: 
            m = "⏳ **انتهى الوقت!** لقد استغرقت أكثر من 15 ثانية."
        elif sel == QUESTIONS[q_idx]["answer"]: 
            ui["score"] += 10
            m = "🎉 **إجابة صحيحة!** كسبت 10 نقاط."
        else: 
            correct_answer_text = QUESTIONS[q_idx]['options'][QUESTIONS[q_idx]['answer']]
            m = f"❌ **إجابة خاطئة!**\nالإجابة الصحيحة هي: {correct_answer_text}"
            
        ui["answered"].append(q_idx)
        sc[user_id] = ui
        save_json(SCORES_FILE, sc)
        
        await query.edit_message_text(f"❓ **تحدي الأسبوع:**\n{QUESTIONS[q_idx]['q']}{SEP}{m}", parse_mode='Markdown')

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تم تشغيل النسخة الشاملة والمفصلة بنجاح...")
    app.run_polling()

if __name__ == '__main__': 
    main()
