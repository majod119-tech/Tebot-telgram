import os
import io
import csv
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

# 🌟 الدالة التي تسببت في الخطأ تم استعادتها هنا 🌟
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
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Server Online.")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

AI_KNOWLEDGE = f"أنت المعلم الذكي. الغياب إنذار 15% حرمان 20%. الحقائب: {DRIVE_LINK}"

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

ai_sessions, feedback_sessions, active_challenges, interrogation_sessions = {}, {}, {}, {}

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

def get_back_menu(): 
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

async def db_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID: return
    try:
        if not os.path.exists('data.xlsx'):
            await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
            return
        df = pd.read_excel('data.xlsx', dtype=str)
        sample = df['stu_num'].dropna().unique()[:5]
        msg = f"📊 **كشاف البيانات:**\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام: `{', '.join(sample)}`"
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
    await update.message.reply_text(f"أهلاً بك {update.effective_user.first_name} 💻✨", reply_markup=get_main_menu())

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
            await update.message.reply_text("3️⃣ **هل تتعهد بالانضباط لتفادي الحرمان (20%)؟**\n(أجب بنعم)", parse_mode='Markdown')
            return
        elif step == 3:
            session['pledge_answer'] = text
            completed = load_json(INTERROGATIONS_FILE)
            if session['stu_num'] not in completed: completed[session['stu_num']] = []
            completed[session['stu_num']].append(session['subject'])
            save_json(INTERROGATIONS_FILE, completed)
            
            report = f"🚨 **تعهد (إنذار 15%)** 🚨\n👤 **المتدرب:** {session['stu_nam']} ({session['stu_num']})\n📖 **المادة:** {session['subject']}\n❓ **العذر:** {session['excuse_answer']}\n✍️ **الإقرار:** {session['pledge_answer']}"
            try: await context.bot.send_message(chat_id=GROUP_ID, text=report, parse_mode='Markdown')
            except: pass
            
            del interrogation_sessions[user_id]
            await update.message.reply_text("✅ **تم توثيق إقرارك للإدارة.**", reply_markup=get_main_menu(), parse_mode='Markdown')
            return

    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False
        await update.message.reply_text("🏠 **تم العودة للقائمة الرئيسية.**", reply_markup=get_main_menu())
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 **استعلام الغياب**\n👇 **أرسل رقمك التدريبي...**", parse_mode='Markdown')
        return

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'):
                await update.message.reply_text("⚠️ **قاعدة البيانات فارغة.**", parse_mode='Markdown')
                return

            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None
                has_deprivation = False
                
                m = f"🎓 **السجل الأكاديمي للغياب** 🎓\n{SEP}\n"
                m += f"👤 **المتدرب:** `{stu_nam}`\n"
                m += f"🔢 **الرقم التدريبي:** `{clean_text}`\n{SEP}\n"
                m += f"📊 **تفاصيل المقررات:**\n\n"
                
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    parsnt_no = str(r.get('parsnt_no', '')).replace('%', '').strip()
                    hrs = str(r.get('hrs', '')).strip()
                    
                    if raw_val == 'ح' or 'حرمان' in raw_val:
                        icon = "🔴 حرمان مؤكد"
                        display_val = f"**حرمان (ح)** {icon}"
                        has_deprivation = True
                        
                        extras = []
                        if parsnt_no and parsnt_no.lower() not in ['ح', 'nan', '', 'none']:
                            extras.append(f"بدون عذر: {parsnt_no}%")
                        if hrs and hrs.lower() not in ['nan', '', 'none', '0']:
                            extras.append(f"ساعات الغياب: {hrs} ساعة")
                            
                        if extras:
                            display_val += f"\n   ↳ 🔍 *التفاصيل:* {' | '.join(extras)}"
                            
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
                                if c_name_text not in completed_interrogations:
                                    subject_to_interrogate = c_name_text
                            else:
                                icon = "🟢 منتظم"
                                
                            display_val = f"**{val}%** {icon}"
                            
                            extras = []
                            if hrs and hrs.lower() not in ['nan', '', 'none', '0']:
                                extras.append(f"الغياب: {hrs} ساعة")
                                
                            if extras:
                                display_val += f" `({', '.join(extras)})`"
                                
                        except Exception:
                            display_val = f"**{raw_val}** ⚠️ (بيانات غير واضحة)"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    
                    m += f"📖 **{c_name_text}**\n"
                    m += f"▫️ النتيجة: {display_val}\n"
                    m += f"📅 التحديث: {day_val}\n\n"
                
                m += f"{SEP}\n💡 *الإنذار يبدأ عند 15%، والحرمان المؤكد عند 20%.*"

                if subject_to_interrogate:
                    interrogation_sessions[user_id] = {'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    warning_msg = f"⚠️ **تنبيه إداري قبل الحرمان!** ⚠️\nلقد وصلت غياباتك إلى مرحلة الخطر (15% فأكثر) في مقرر:\n**{subject_to_interrogate}**\n\n🛑 **للإطلاع على سجلك الكامل، يجب الإجابة أولاً:**\n1️⃣ هل تعلم أنك اقتربت من الحرمان؟"
                    await update.message.reply_text(warning_msg, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
                    return
                
                if has_deprivation: 
                    m += f"\n\n🛑 **تنبيه إداري هام:**\nأنت محروم في مقرر أو أكثر. نأمل مراجعة الإدارة."
                
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **الرقم التدريبي غير مسجل أو لا توجد غيابات.**", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ **حدث خطأ:** `{str(e)}`", parse_mode='Markdown')
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
    if text == "📘 دليل المتدرب الرسمي":
        if os.path.exists("trainee_guide.pdf"):
            await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 **دليل المتدرب الرسمي**", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ **عذراً، جاري تحديث ملف الدليل من قبل الإدارة.**", parse_mode='Markdown')
        return
    if text == "❓ الأسئلة الشائعة":
        faq_msg = f"❓ **الأسئلة الشائعة:**\n🔹 **متى يقع الحرمان؟** عند غياب (20%).\n🔹 **المكافأة؟** 800 ريال للمعاهد ותتوقف إذا قل المعدل عن 2.00.\n🔹 **درجة النجاح؟** 50 للمعاهد."
        await update.message.reply_text(faq_msg, parse_mode='Markdown')
        return
    if text == "🤖 المعلم الذكي (الدليل الشامل)":
        ai_sessions[user_id] = True
        await update.message.reply_text("🤖 **المعلم الذكي!**\n💬 **اكتب سؤالك...**", reply_markup=get_back_menu(), parse_mode='Markdown')
        return
    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم غير متصل.", reply_markup=get_back_menu())
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
            await update.message.reply_text(f"📝 رد المعلم الذكي:\n\n{response.text}", reply_markup=get_back_menu())
        except: pass
        return
    if text == "📬 الاقتراحات والشكاوى":
        feedback_sessions[user_id] = True
        await update.message.reply_text("📬 **اكتب رسالتك الآن...**", reply_markup=get_back_menu(), parse_mode='Markdown')
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
        reply_msg = f"{plans.get(text, 'جاري التحديث')}\n{SEP}\n🔗 **لتحميل المنهج اضغط الزر:**"
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
    if text == "🌐 أخبار التقنية":
        try:
            req = urllib.request.Request("https://www.tech-wd.com/wd/feed/", headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            root = ET.fromstring(response.read())
            news_msg = f"🌐 **الأخبار التقنية**\n{SEP}\n"
            for i, item in enumerate(root.findall('.//item')):
                if i >= 3: break
                news_msg += f"🔹 [{item.find('title').text}]({item.find('link').text})\n\n"
            await update.message.reply_text(news_msg, parse_mode='Markdown', disable_web_page_preview=True)
        except: pass
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

    if not ai_sessions.get(user_id):
        await update.message.reply_text("⚠️ **اختر من القائمة 👇**", reply_markup=get_main_menu())


async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ **جاري التحديث وسحب البيانات المخفية...**", parse_mode='Markdown')
            
            try:
                file = await context.bot.get_file(doc.file_id)
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    with open(temp_file, 'rb') as f:
                        raw_bytes = f.read()
                        
                    decoded_text = None
                    for enc in ['utf-8-sig', 'windows-1256', 'cp1256', 'utf-8']:
                        try:
                            decoded_text = raw_bytes.decode(enc)
                            if 'المتدرب' in decoded_text or 'المقرر' in decoded_text:
                                break
                        except Exception:
                            continue
                            
                    if not decoded_text:
                        raise Exception("فشل التعرف على لغة الملف.")
                        
                    parsed_data = []
                    reader = csv.reader(io.StringIO(decoded_text), delimiter=',', quotechar='"')
                    rows = list(reader)
                    
                    header = rows[0]
                    c_course, c_id, c_name, c_perc, c_perc_no, c_hrs = -1, -1, -1, -1, -1, -1
                    
                    for i, col in enumerate(header):
                        clean_col = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا').replace('"', '')
                        if 'اسمالمقرر' in clean_col: c_course = i
                        elif 'رقمالمتدرب' in clean_col: c_id = i
                        elif 'اسمالمتدرب' in clean_col: c_name = i
                        elif 'بعذروبدون' in clean_col and 'نسبه' in clean_col: c_perc = i
                        elif 'بدونعذر' in clean_col and 'نسبه' in clean_col and 'بعذروبدون' not in clean_col: c_perc_no = i
                        elif 'ساعات' in clean_col and 'بعذروبدون' in clean_col: c_hrs = i
                            
                    if c_id == -1 or c_course == -1:
                        if len(header) >= 26:
                            c_course, c_id, c_name, c_perc, c_perc_no, c_hrs = 14, 16, 17, 18, 22, 25
                        else:
                            raise Exception("لم يتم العثور على الأعمدة.")
                            
                    for row in rows[1:]:
                        if len(row) > max(c_course, c_id, c_name, c_perc):
                            stu_num_clean = "".join(filter(str.isdigit, str(row[c_id])))
                            if stu_num_clean: 
                                parsed_data.append({
                                    'c_nam': str(row[c_course]).strip(),
                                    'stu_num': stu_num_clean,
                                    'stu_nam': str(row[c_name]).strip(),
                                    'parsnt': str(row[c_perc]).strip(),
                                    'parsnt_no': str(row[c_perc_no]).strip() if c_perc_no != -1 and len(row) > c_perc_no else "",
                                    'hrs': str(row[c_hrs]).strip() if c_hrs != -1 and len(row) > c_hrs else "",
                                    'day': datetime.now().strftime("%Y-%m-%d")
                                })
                                
                    df_clean = pd.DataFrame(parsed_data)
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file)
                    
                else:
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                    
                await status_msg.edit_text(f"✅ **نجاح التحديث!**\n📊 **النتيجة:** تم حفظ `{records_count}` متدرب.", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

    if not update.message.caption: 
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 **عذر:**\n{update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ **تم الإرسال.**", parse_mode='Markdown')
    except: pass

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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النسخة المستقرة...")
    app.run_polling()

if __name__ == '__main__': 
    main()
