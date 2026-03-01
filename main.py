import os
import io
import pandas as pd
import json
import random
import time
import urllib.request
import xml.etree.ElementTree as ET
import re
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
            </style></head><body>
            <h1 style="color:#2c3e50;">📊 الإحصائيات الرسمية للمساعد الذكي</h1>
            <div class="card-container">
                <div class="card"><h3>👥 إجمالي المتدربين</h3><p>{len(stats.get('users_list', []))}</p></div>
                <div class="card"><h3>🤖 استفسارات الذكاء الاصطناعي</h3><p>{stats.get('ai_questions', 0)}</p></div>
                <div class="card"><h3>🎮 التحديات المنجزة</h3><p>{stats.get('quiz_attempts', 0)}</p></div>
            </div>
            </body></html>"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Server Online. Access /stats for dashboard.")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

AI_KNOWLEDGE = f"""
أنت المعلم الذكي الرسمي لقسم الحاسب الآلي وتقنية المعلومات في المعهد الصناعي الثانوي ببريدة (مؤسسة التدريب التقني والمهني).
أجب باختصار شديد ومهنية. اعتمد على أنظمة دليل المتدرب التالية في إجاباتك إذا سئلت:
- الغياب والحرمان: إنذار عند 15% وحرمان نهائي عند 20%. يُطوى القيد إذا انقطع المتدرب أسبوعين متتاليين.
- المكافأة: 800 ريال لمتدربي المعاهد. توقف إذا قل المعدل التراكمي عن 2.00.
- درجات النجاح: درجة الاجتياز في المعاهد 50.
- الحقائب التدريبية: {DRIVE_LINK}
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
        pass

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

async def db_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID: return
    try:
        if not os.path.exists('data.xlsx'):
            await update.message.reply_text("⚠️ لا يوجد ملف data.xlsx حالياً.")
            return
        df = pd.read_excel('data.xlsx', dtype=str)
        sample = df['stu_num'].dropna().unique()[:5]
        msg = f"📊 **كشاف قاعدة البيانات:**\n✅ عدد السجلات المحفوظة: {len(df)}\n🔍 أول 5 أرقام متدربين تم حفظها:\n`{', '.join(sample)}`"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ: {e}")

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
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    if user_id in interrogation_sessions:
        session = interrogation_sessions[user_id]
        step = session['step']
        if step == 1:
            session['aware_answer'] = text; session['step'] = 2
            await update.message.reply_text("2️⃣ **ما هو العذر الرئيسي لغياباتك؟**", parse_mode='Markdown')
            return
        elif step == 2:
            session['excuse_answer'] = text; session['step'] = 3
            await update.message.reply_text("3️⃣ **هل تتعهد بالانضباط لتفادي الحرمان (20%)؟**", parse_mode='Markdown')
            return
        elif step == 3:
            session['pledge_answer'] = text
            completed = load_json(INTERROGATIONS_FILE)
            if session['stu_num'] not in completed: completed[session['stu_num']] = []
            completed[session['stu_num']].append(session['subject'])
            save_json(INTERROGATIONS_FILE, completed)
            del interrogation_sessions[user_id]
            await update.message.reply_text("✅ **تم توثيق إقرارك.**\nاحرص على الحضور.", reply_markup=get_main_menu(), parse_mode='Markdown')
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
            await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 **دليل المتدرب الرسمي**", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ **عذراً، جاري تحديث ملف الدليل من قبل الإدارة.**", parse_mode='Markdown')
        return

    if text == "❓ الأسئلة الشائعة":
        faq_msg = f"❓ **الأسئلة الشائعة:**\n🔹 **متى يقع الحرمان؟** عند غياب (20%).\n🔹 **المكافأة؟** 800 ريال للمعاهد وتتوقف إذا قل المعدل عن 2.00.\n🔹 **درجة النجاح؟** 50 للمعاهد."
        await update.message.reply_text(faq_msg, parse_mode='Markdown')
        return

    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        await update.message.reply_text("🤖 **المعلم الذكي!**\n💬 **اكتب سؤالك التقني أو الإداري وسأجيبك فوراً...**", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم غير متصل.", reply_markup=get_back_menu())
            return
        update_stat("ai_questions")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
            await update.message.reply_text(f"📝 رد المعلم الذكي:\n{SEP}{response.text}", reply_markup=get_back_menu())
        except Exception: 
            await update.message.reply_text("⚠️ **حدث خطأ، حاول لاحقاً.**", reply_markup=get_back_menu())
        return

    if text == "📬 الاقتراحات والشكاوى":
        feedback_sessions[user_id] = True
        await update.message.reply_text("📬 **الاقتراحات والشكاوى**\nاكتب رسالتك الآن وستصل للإدارة بسرية...", reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if feedback_sessions.get(user_id) == True:
        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 **شكوى/مقترح:**\nالمرسل: {update.effective_user.first_name}\nالنص: {text}")
            feedback_sessions[user_id] = False
            await update.message.reply_text("✅ **تم استلام رسالتك.**", reply_markup=get_main_menu(), parse_mode='Markdown')
        except: pass
        return

    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]:
        plans = load_json("plans.json")
        reply_msg = f"{plans.get(text, 'جاري التحديث')}{SEP}🔗 **لتحميل المنهج اضغط الزر بالأسفل:**"
        await update.message.reply_text(reply_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 تحميل", url=DRIVE_LINK)]]), parse_mode='Markdown')
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

    if text == "🎮 تحدي الأسبوع":
        update_stat("quiz_attempts")
        q = random.choice(QUESTIONS)
        active_challenges[user_id] = time.time()
        kb = [[InlineKeyboardButton(o, callback_data=f"ans_{QUESTIONS.index(q)}_{i}")] for i, o in enumerate(q['options'])]
        await update.message.reply_text(f"❓ **تحدي الأسبوع:**\n\n{q['q']}\n\n⚠️ أمامك 15 ثانية:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    if text == "🏆 بطل الأسبوع":
        sc = load_json(SCORES_FILE)
        if not sc: 
            await update.message.reply_text("📉 لا يوجد نقاط مسجلة.", parse_mode='Markdown')
            return
        top = sorted(sc.items(), key=lambda x: x[1]['score'], reverse=True)[0][1]
        await update.message.reply_text(f"🏆 **بطل الأسبوع:** {top['name']}\n🌟 **النقاط:** {top['score']}", parse_mode='Markdown')
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 **استعلام الغياب**\n👇 **أرسل رقمك التدريبي...**", parse_mode='Markdown')
        return

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'):
                await update.message.reply_text("⚠️ **قاعدة البيانات فارغة.** الإدارة لم ترفع ملف رايات بعد.", parse_mode='Markdown')
                return

            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None
                has_deprivation = False
                m = f"✅ **السجل لـ:** `{stu_nam}`{SEP}"
                
                for _, r in res.iterrows():
                    raw_val = str(r.get('parsnt', '0')).strip()
                    try:
                        val = float(raw_val)
                        icon = "🔴 حرمان" if val >= 20 else ("⚠️ إنذار" if val >= 15 else "🟢 منتظم")
                        display_val = f"%{val} {icon}"
                    except Exception:
                        val = 0.0
                        display_val = f"{raw_val} ⚠️ (معدل غير مقروء)"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    m += f"📖 {r['c_nam']}: {display_val}\n📅 تاريخ التحديث: {day_val}\n\n"
                    
                    if val >= 20: has_deprivation = True
                    elif 15 <= val < 20 and r['c_nam'] not in completed_interrogations:
                        if not subject_to_interrogate: subject_to_interrogate = r['c_nam']
                
                if subject_to_interrogate:
                    interrogation_sessions[user_id] = {'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    await update.message.reply_text(f"⚠️ **إنذار قبل الحرمان!**\nوصلت 15% في: **{subject_to_interrogate}**\n🛑 أجب:\n1️⃣ هل تعلم أنك اقتربت من الحرمان؟", parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
                    return
                
                if has_deprivation: m += f"🛑 **أنت محروم إدارياً (20%)!**"
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **الرقم التدريبي غير مسجل أو لا يوجد غياب.**", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ **حدث خطأ فني:** `{str(e)}`", parse_mode='Markdown')
        return

    if text == "📝 رفع الغياب والأعذار": 
        await update.message.reply_text("📝 **رفع الأعذار**\nصور العذر واكتب رقمك بالوصف ثم أرسله ليتم ختمه آلياً.", parse_mode='Markdown')
        return
        
    if text == "📚 الحقائب التدريبية": 
        await update.message.reply_text("📚 **الحقائب التدريبية:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول للمستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
        return
        
    if text == "🔗 المنصات الإلكترونية": 
        kb = [[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")], [InlineKeyboardButton("بلاك بورد", url="https://lms.elearning.edu.sa/")]]
        await update.message.reply_text("🌐 **المنصات الإلكترونية:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return
        
    if text == "📍 موقع القسم": 
        await update.message.reply_text("📍 **موقع قسم الحاسب:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
        return
        
    if text == "📰 أخبار القسم والمعهد": 
        await update.message.reply_text("📰 **أخبار المعهد:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 حساب منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
        return

    if not ai_sessions.get(user_id) and not feedback_sessions.get(user_id):
        await update.message.reply_text("⚠️ **الرجاء اختيار خدمة من الأسفل 👇**", reply_markup=get_main_menu())


# --- 🌟 محرك سحب ملفات رايات (المفصل خصيصاً على ملفك) 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ **جاري قراءة ملف رايات الأصلي...**", parse_mode='Markdown')
            
            try:
                file = await context.bot.get_file(doc.file_id)
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    df_raw = None
                    for enc in ['utf-8-sig', 'windows-1256', 'utf-8', 'cp1256']:
                        try:
                            temp_df = pd.read_csv(temp_file, encoding=enc, dtype=str)
                            # بما أنني رأيت الملف، أعرف أن كلمة (اسم المتدرب) موجودة
                            if any('اسم المتدرب' in str(c) for c in temp_df.columns):
                                df_raw = temp_df
                                break
                        except Exception:
                            pass
                    
                    if df_raw is None:
                        raise Exception("لم يتم التعرف على بنية ملف رايات.")

                    df_clean = pd.DataFrame()
                    
                    # 🌟 البحث الدقيق عن الأعمدة 🌟
                    c_course = next(c for c in df_raw.columns if 'اسم المقرر' in str(c))
                    c_id = next(c for c in df_raw.columns if 'رقم المتدرب' in str(c))
                    c_name = next(c for c in df_raw.columns if 'اسم المتدرب' in str(c))
                    c_perc = next(c for c in df_raw.columns if 'نسبة الغياب بعذر وبدون' in str(c))
                    
                    df_clean['c_nam'] = df_raw[c_course]
                    df_clean['stu_num'] = df_raw[c_id]
                    df_clean['stu_nam'] = df_raw[c_name]
                    df_clean['parsnt'] = df_raw[c_perc]

                    # 🌟 تنظيف الأرقام 🌟
                    df_clean['stu_num'] = df_clean['stu_num'].astype(str).str.replace(r'\D', '', regex=True)
                    df_clean = df_clean[df_clean['stu_num'] != ''] 
                    
                    df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file) 
                    
                else:
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                    
                await status_msg.edit_text(f"✅ **نجاح التحديث من رايات!**\n📊 **النتيجة:** تم حفظ `{records_count}` متدرب بنجاح.\n*(اكتب الأمر /db للتأكد، أو ابحث عن أي طالب فوراً)* 🚀", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

    # --- باقي الكود: الختم الآلي للأعذار ---
    if not update.message.caption: 
        await update.message.reply_text("⚠️ **الرجاء إرفاق الصورة مع كتابة رقمك في الوصف.**", parse_mode='Markdown')
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    status_msg = await update.message.reply_text("⏳ جاري المعالجة والختم...")
    
    try:
        caption_text = update.message.caption
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stu_id = ''.join(filter(str.isdigit, caption_text)) or "UNKNOWN"
        
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
            await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 **عذر مختوم رسمياً:**\n{caption_text}\n⏱️ {timestamp}", parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر:**\n{caption_text}\n{timestamp}")
            await update.message.copy(chat_id=GROUP_ID)
            
        await status_msg.edit_text("✅ **تم الختم والإرسال للإدارة بنجاح.**", parse_mode='Markdown')
    except Exception as e:
        await status_msg.edit_text("⚠️ **حدث خطأ فني أثناء الإرسال.**", parse_mode='Markdown')

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
            if time_taken > 15: m = "⏳ **انتهى الوقت!** استغرقت أكثر من 15 ثانية."
            elif sel == actual_question["answer"]: 
                ui["score"] += 10
                m = "🎉 **إجابة صحيحة!** كسبت 10 نقاط."
            else: m = f"❌ **خاطئة!**\nالصحيحة: {actual_question['options'][actual_question['answer']]}"
                
            ui["answered"].append(q_idx); sc[user_id] = ui; save_json(SCORES_FILE, sc)
            await query.edit_message_text(f"❓ **تحدي الأسبوع:**\n{actual_question['q']}{SEP}{m}", parse_mode='Markdown')
        except Exception:
            await query.edit_message_text("⚠️ تحدي قديم. جرب سؤالاً جديداً!")

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) # 🌟 أمر كشف البيانات السري 🌟
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تم استعادة جميع القوائم والأزرار + محرك رايات الحقيقي يعمل بنجاح...")
    app.run_polling()

if __name__ == '__main__': 
    main()
