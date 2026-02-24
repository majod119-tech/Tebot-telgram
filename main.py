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
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 🌟 استدعاء مكتبة الصور بحماية من الانهيار ---
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- 🌟 دوال مساعدة لضمان عدم توقف السيرفر ---
def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {}
    return {}

def save_json(f, d): 
    with open(f, "w", encoding="utf-8") as file:
        json.dump(d, file, ensure_ascii=False)

# --- 🌟 استدعاء بنك الأسئلة الخارجي بحماية كاملة ---
try:
    from questions_bank import QUESTIONS
except Exception as e:
    print(f"⚠️ تنبيه: تعذر تحميل ملف الأسئلة بسبب خطأ: {e}")
    QUESTIONS = [
        {"q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}
    ]

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

# --- 🌟 النظام الذكي للتصفير التلقائي ---
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
                    print(f"✅ تم تصفير نقاط تحدي الأسبوع تلقائياً بتاريخ: {today_str}")
        except Exception as e:
            pass
        time.sleep(3600)

# --- 2. سيرفر الويب المطور (Dashboard) ---
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

# --- 3. إعدادات المعلم الذكي ---
AI_KNOWLEDGE = f"""
أنت المعلم الذكي لقسم الحاسب الآلي في المعهد الصناعي الثانوي.
التعليمات الصارمة لك:
1. أجب باختصار شديد وبشكل مباشر في صلب الموضوع.
2. لا تقم بالترحيب الطويل، ولا تكرر وظائفك أو الروابط إلا إذا سألك المتدرب عنها تحديداً.
3. اشرح المفاهيم التقنية بأسلوب مبسط وعملي.
4. معلومات القسم: الحقائب في {DRIVE_LINK} | الغياب: إنذار 15% وحرمان 20%.
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
    except Exception: pass

ai_sessions, feedback_sessions, active_challenges = {}, {}, {}
interrogation_sessions = {} 

TECH_TIPS = [
    "💡 **نصيحة أمنية:** استخدم اختصار `Win + L` لقفل شاشة جهازك فوراً عند الابتعاد.",
    "🛡️ **نصيحة تقنية:** احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات الأمنية.",
    "🚀 **نصيحة برمجية:** التنسيق والمسافات البادئة في بايثون هي أساس عمل الكود.",
    "🌐 **نصيحة شبكات:** عنوان `127.0.0.1` يُعرف بـ Localhost ويستخدم لاختبار كرت الشبكة."
]

# --- 4. تصميم القوائم ---
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

# --- 5. المنطق البرمجي ---
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
        f"👇 **الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:**"
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

    # 🚨 اعتراض الاستجواب الآلي 🚨
    if user_id in interrogation_sessions:
        session = interrogation_sessions[user_id]
        step = session['step']
        
        if step == 1:
            session['aware_answer'] = text
            session['step'] = 2
            await update.message.reply_text("2️⃣ **ما هو المبرر أو العذر الرئيسي لغياباتك؟**\n(اكتب عذرك بالتفصيل الآن...)", parse_mode='Markdown')
            return
        elif step == 2:
            session['excuse_answer'] = text
            session['step'] = 3
            await update.message.reply_text("3️⃣ **هل تتعهد رسمياً بالانضباط وعدم الغياب لتفادي الحرمان النهائي (20%)؟**\n(أجب بـ نعم أو أتعهد)", parse_mode='Markdown')
            return
        elif step == 3:
            session['pledge_answer'] = text
            completed = load_json(INTERROGATIONS_FILE)
            stu_num = session['stu_num']
            if stu_num not in completed: completed[stu_num] = []
            completed[stu_num].append(session['subject'])
            save_json(INTERROGATIONS_FILE, completed)

            report = (
                f"🚨 **تعهد قبل الحرمان (مرحلة الإنذار 15%)** 🚨\n\n"
                f"👤 **المتدرب:** {session['stu_nam']} ({stu_num})\n"
                f"📖 **المادة:** {session['subject']}\n"
                f"❓ **علم بالإنذار:** {session['aware_answer']}\n"
                f"📝 **العذر:** {session['excuse_answer']}\n"
                f"✍️ **الإقرار:** {session['pledge_answer']}\n\n"
                f"✅ تم تسجيل الإقرار آلياً وحفظه."
            )
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=report, parse_mode='Markdown')
            except Exception: pass
            del interrogation_sessions[user_id]
            await update.message.reply_text("✅ **تم توثيق إقرارك رسمياً.**\n\nاحرص على الحضور لتفادي الحرمان النهائي. تم رفع الإيقاف عنك.", reply_markup=get_main_menu(), parse_mode='Markdown')
            return

    if text in ["🔙 الرجوع للقائمة الرئيسية", "📚 الحقائب التدريبية", "📄 الخطط التدريبية", "📊 استعلام الغياب", "📝 رفع الغياب والأعذار", "🔗 منصة تقني ورايات", "📅 التقويم التدريبي", "📰 أخبار القسم والمعهد", "📍 موقع القسم", "📬 قسم الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]:
        ai_sessions[user_id] = False
        feedback_sessions[user_id] = False

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 **تم العودة للقائمة الرئيسية.**", reply_markup=get_main_menu())
        return

    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        guide_msg = f"🤖 **المعلم الذكي في خدمتك!**\n💬 **اكتب سؤالك التقني الآن وسأقوم بالرد عليك...**\n*(للخروج اضغط على زر الرجوع)*"
        await update.message.reply_text(guide_msg, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم الذكي غير متصل حالياً.", reply_markup=get_back_menu())
            return
        update_stat("ai_questions")
        status_msg = await update.message.reply_text("⏳ أقرأ سؤالك...")
        try:
            response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال المتدرب: {text}")
            await status_msg.delete()
            clean_text = response.text.replace("**", "").replace("* ", "🔹 ").strip()
            await update.message.reply_text(f"📝 رد المعلم الذكي:\n{SEP}{clean_text}", reply_markup=get_back_menu())
        except Exception: 
            await status_msg.delete()
            await update.message.reply_text(f"⚠️ **عذراً، واجهت مشكلة تقنية.**", reply_markup=get_back_menu())
        return

    if text == "📬 قسم الاقتراحات والشكاوى":
        feedback_sessions[user_id] = True
        msg = f"📬 **قسم الاقتراحات والشكاوى**\nرأيك يهمنا، اكتب رسالتك الآن وستصل مباشرة وبسرية للإدارة..."
        await update.message.reply_text(msg, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if feedback_sessions.get(user_id) == True:
        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 **رسالة مقترح/شكوى:**\nالمرسل: {update.effective_user.first_name}\nالرسالة: {text}")
            feedback_sessions[user_id] = False
            await update.message.reply_text("✅ **تم استلام رسالتك بنجاح.** شكراً لتواصلك!", reply_markup=get_main_menu(), parse_mode='Markdown')
        except:
            await update.message.reply_text("⚠️ عذراً، فشل إرسال الرسالة إلى الإدارة.", reply_markup=get_main_menu())
        return

    term_plans = {
        "1️⃣ الفصل الأول": "📚 ثقافة إسلامية 1\n🔹 إنجليزي 1\n🔹 رياضيات 1\n🔹 فيزياء\n🔹 بدنية 1\n🔹 عربي 1\n🔹 أساسيات حاسب",
        "2️⃣ الفصل الثاني": "📚 سلوك مهني\n🔹 عربي 2\n🔹 إنجليزي 2\n🔹 رياضيات 2\n🔹 بدنية 2\n🔹 تطبيقات حاسب",
        "3️⃣ الفصل الثالث": "📚 الرسم الهندسي\n🔹 بحث ومصادر\n🔹 رياضيات 3\n🔹 إنجليزي 3\n🔹 أساسيات شبكات",
        "4️⃣ الفصل الرابع": "📚 ريادة أعمال\n🔹 تقنيات انترنت\n🔹 مكونات حاسب 1\n🔹 برمجة 1\n🔹 نظام لينكس",
        "5️⃣ الفصل الخامس": "📚 مكونات حاسب 2\n🔹 صيانة أجهزة\n🔹 برمجة 2\n🔹 تمديد كيابل\n🔹 شبكات حاسب\n🔹 تشغيل شبكة 1",
        "6️⃣ الفصل السادس": "📚 قواعد بيانات\n🔹 طرفيات حاسب\n🔹 مهارات صيانة\n🔹 ألياف ضوئية\n🔹 تشغيل شبكة 2",
        "🖥️ برامج فصلية": "📚 برنامج إدخال البيانات ومعالجة النصوص"
    }

    if text in term_plans:
        await update.message.reply_text(f"{term_plans[text]}{SEP}🔗 **التحميل:** {DRIVE_LINK}", parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 **اختر الفصل التدريبي:**", reply_markup=get_plans_menu(), parse_mode='Markdown')
        return

    if text == "🕹️ قسم الألعاب والإضافات":
        await update.message.reply_text("🕹️ **اختر النشاط الذي تفضله:**", reply_markup=get_games_menu(), parse_mode='Markdown')
        return

    if text == "💡 نصيحة تقنية":
        await update.message.reply_text(random.choice(TECH_TIPS), parse_mode='Markdown')
        return

    if text == "🌐 أخبار التقنية":
        status_msg = await update.message.reply_text("⏳ جاري سحب أحدث الأخبار التقنية...")
        try:
            req = urllib.request.Request("https://aitnews.com/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 **موجز الأخبار التقنية**{SEP}"
            for i, item in enumerate(root.findall('.//item')):
                if i >= 3: break
                news_msg += f"🔹 [{item.find('title').text}]({item.find('link').text})\n\n"
            await status_msg.edit_text(news_msg, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            await status_msg.edit_text("⚠️ **عذراً، مصدر الأخبار لا يستجيب حالياً.**", parse_mode='Markdown')
        return

    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        active_challenges[user_id] = time.time()
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        await update.message.reply_text(f"❓ **تحدي الأسبوع:**\n\n{q['q']}\n\n⚠️ أمامك 15 ثانية فقط للإجابة:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: 
            await update.message.reply_text("📉 لم يتم تسجيل أي نقاط لأي متدرب حتى الآن.", parse_mode='Markdown')
            return
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        msg = f"🏆 **بطل الأسبوع:** {top['name']}\n🌟 **الرصيد:** {top['score']} نقطة"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text == "📊 استعلام الغياب":
        msg = f"🔎 **نظام استعلام الغياب الذكي**\n👇 **أرسل (رقمك التدريبي) المكون من أرقام فقط الآن للبحث...**"
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
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(text, [])
                subject_to_interrogate = None
                has_deprivation = False
                m = f"✅ **تم العثور على السجل لـ:** `{stu_nam}`{SEP}"
                
                for _, r in res.iterrows():
                    val = float(r['parsnt'])
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ إنذار" if val >= 15 else "🟢 منتظم")
                    m += f"📖 {r['c_nam']}: %{val} {icon}\n"
                    if val >= 20:
                        has_deprivation = True
                    elif 15 <= val < 20 and r['c_nam'] not in completed_interrogations:
                        if not subject_to_interrogate:
                            subject_to_interrogate = r['c_nam']
                
                if subject_to_interrogate:
                    interrogation_sessions[user_id] = {
                        'step': 1, 'stu_num': text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate
                    }
                    warning_msg = (
                        f"⚠️ **إنذار أخير قبل الحرمان!** ⚠️\n\n"
                        f"المتدرب `{stu_nam}`، لقد بلغت نسبة غيابك مرحلة الخطر (15%) في مادة:\n"
                        f"🟡 **{subject_to_interrogate}**\n\n"
                        f"🛑 **تم إيقاف خدمات البوت عنك مؤقتاً.**\n"
                        f"لرفع الإيقاف، أجب بصراحة:\n\n1️⃣ **هل أنت على علم بأن غيابك اقترب من الحرمان النهائي؟**"
                    )
                    await update.message.reply_text(warning_msg, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
                    return
                
                if has_deprivation:
                    m += f"\n{SEP}🛑 **تنبيه حرمان إداري!** 🛑\n"
                    m += "لقد تجاوزت النسبة المسموحة (20%) وأصبحت **محروماً**.\n"
                    m += "⚠️ يجب تقديم عذرك الطبي عبر قسم (📝 رفع الغياب والأعذار) خلال **(3 إلى 5 أيام)** من الغياب."
                
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **عذراً، الرقم التدريبي غير مسجل لدينا.**", parse_mode='Markdown')
        except Exception:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text("⚠️ **حدث خطأ فني:** ملف الغياب غير متوفر.", parse_mode='Markdown')
        return

    if text == "📝 رفع الغياب والأعذار": 
        msg = (
            f"📝 **بوابة رفع الأعذار**{SEP}"
            f"لضمان قبول عذرك وعدم احتسابه في نسبة الحرمان:\n\n"
            f"1️⃣ التقط صورة واضحة لورقة العذر.\n"
            f"2️⃣ اكتب (رقمك التدريبي + اسمك) في خانة الوصف.\n"
            f"3️⃣ أرسل الصورة هنا وسنقوم بختمها وتسليمها للإدارة.\n\n"
            f"⏳ **ملاحظة:** لن يتم قبول أي عذر إلا إذا تم تقديمه خلال **(3 إلى 5 أيام)** من تاريخ الغياب."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return
        
    if text == "📚 الحقائب التدريبية": 
        await update.message.reply_text(f"📚 **الحقائب التدريبية**\n🔗 {DRIVE_LINK}", parse_mode='Markdown', disable_web_page_preview=True)
        return
        
    if text == "🔗 منصة تقني ورايات": 
        msg = f"🌐 **منصات المؤسسة**\n🔹 تقني: https://tvtclms.edu.sa\n🔹 رايات: https://rayat.tvtc.gov.sa"
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=True)
        return
        
    if text == "📍 موقع القسم": 
        await update.message.reply_text(f"📍 **الموقع الجغرافي:** http://googleusercontent.com/maps.google.com/3", parse_mode='Markdown')
        return
        
    if text == "📰 أخبار القسم والمعهد": 
        keyboard = [[InlineKeyboardButton("📱 عرض آخر الأخبار في منصة X", url=TVTC_X_LINK)]]
        await update.message.reply_text(f"📰 **لمتابعة أحدث الإعلانات:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
        
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'): await update.message.reply_photo(photo=open('calendar.jpg', 'rb'))
        else: await update.message.reply_text("⚠️ ملف التقويم غير متوفر.")
        return

    if not ai_sessions.get(user_id) and not feedback_sessions.get(user_id):
        await update.message.reply_text("⚠️ **عذراً، لم أتعرف على طلبك.**", reply_markup=get_main_menu())

# --- 🌟 التعديل الساحق: نظام الختم الرقمي للأعذار 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption: 
        await update.message.reply_text("⚠️ **الرجاء إرفاق الصورة مرة أخرى مع كتابة (رقمك التدريبي) في الوصف.**", parse_mode='Markdown')
        return
    
    status_msg = await update.message.reply_text("⏳ جاري تحليل الصورة وختمها إلكترونياً...")
    
    try:
        caption_text = update.message.caption
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stu_id = ''.join(filter(str.isdigit, caption_text)) # استخراج الأرقام فقط لضمان سلامة الختم
        if not stu_id: stu_id = "UNKNOWN"
        
        # 🌟 إذا كانت الصورة موجودة ومكتبة PIL مثبتة، نقوم بختم الصورة
        if update.message.photo and HAS_PIL:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # تنزيل الصورة إلى الذاكرة المؤقتة
            in_memory_img = io.BytesIO()
            await file.download_to_memory(in_memory_img)
            in_memory_img.seek(0)
            
            img = Image.open(in_memory_img)
            width, height = img.size
            
            # صنع شريط أحمر للختم يتناسب مع حجم الصورة
            watermark_text = f"AUTO-SYSTEM: VALIDATED | STU-ID: {stu_id} | DATE: {timestamp}"
            txt_img = Image.new('RGB', (1000, 50), color='#d32f2f') # لون أحمر رسمي
            d = ImageDraw.Draw(txt_img)
            d.text((20, 15), watermark_text, fill="white")
            
            # تصغير أو تكبير الختم ليناسب عرض الصورة الأصلية
            txt_img = txt_img.resize((width, int(width * 50 / 1000)))
            img.paste(txt_img, (0, height - txt_img.height)) # لصق الختم أسفل الصورة
            
            output = io.BytesIO()
            img.save(output, format='JPEG')
            output.seek(0)
            
            await context.bot.send_photo(
                chat_id=GROUP_ID,
                photo=output,
                caption=f"📥 **عذر طبي/رسمي (مختوم آلياً):**\n👤 بيانات الطالب: {caption_text}\n⏱️ وقت الرفع: {timestamp}",
                parse_mode='Markdown'
            )
            
        else:
            # طريقة الإرسال العادية (إذا أرسل ملف PDF أو إذا كانت المكتبة غير مثبتة)
            await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر جديد:**\nالمرسل: {update.effective_user.first_name}\nالبيانات: {caption_text}\nوقت الرفع: {timestamp}")
            await update.message.copy(chat_id=GROUP_ID)
            
        await status_msg.edit_text("✅ **تم ختم عذرك إلكترونياً واستلامه بنجاح.**\nسيتم مراجعته من قبل إدارة القسم.", parse_mode='Markdown')
        
    except Exception as e: 
        await status_msg.edit_text("⚠️ **خطأ في المعالجة أو في الإرسال للأرشيف.**", parse_mode='Markdown')

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
        
        try:
            actual_question = QUESTIONS[q_idx]
            if time_taken > 15: 
                m = "⏳ **انتهى الوقت!** لقد استغرقت أكثر من 15 ثانية."
            elif sel == actual_question["answer"]: 
                ui["score"] += 10
                m = "🎉 **إجابة صحيحة!** كسبت 10 نقاط."
            else: 
                correct_answer_text = actual_question['options'][actual_question['answer']]
                m = f"❌ **إجابة خاطئة!**\nالإجابة الصحيحة هي: {correct_answer_text}"
                
            ui["answered"].append(q_idx)
            sc[user_id] = ui
            save_json(SCORES_FILE, sc)
            
            await query.edit_message_text(f"❓ **تحدي الأسبوع:**\n{actual_question['q']}{SEP}{m}", parse_mode='Markdown')
        except Exception:
            await query.edit_message_text("⚠️ عذراً، هذا التحدي قديم وتم تحديث بنك الأسئلة. جرب تحدياً جديداً!")

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تم تشغيل النسخة المستقرة مع نظام الختم الرقمي للأعذار...")
    app.run_polling()

if __name__ == '__main__': 
    main()
