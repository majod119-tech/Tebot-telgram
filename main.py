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

    if text == "🔙 الرجوع للقائمة الرئيسية":
        ai_sessions[user_id] = False
        await update.message.reply_text("🏠 **القائمة الرئيسية.**", reply_markup=get_main_menu())
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
                m = f"✅ **السجل لـ:** `{stu_nam}`{SEP}"
                for _, r in res.iterrows():
                    raw_val = str(r.get('parsnt', '0')).strip()
                    try:
                        val = float(raw_val)
                        icon = "🔴 حرمان" if val >= 20 else ("⚠️ إنذار" if val >= 15 else "🟢 منتظم")
                        display_val = f"%{val} {icon}"
                    except: display_val = f"{raw_val} ⚠️"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    m += f"📖 {r['c_nam']}: {display_val}\n📅 التحديث: {day_val}\n\n"
                
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **الرقم التدريبي غير مسجل أو لا يوجد غياب.**", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ **حدث خطأ:** `{str(e)}`", parse_mode='Markdown')
        return

    if not ai_sessions.get(user_id):
        await update.message.reply_text("⚠️ **اختر من القائمة 👇**", reply_markup=get_main_menu())


# --- 🌟 محرك سحب ملفات رايات المبني على فكرتك (الفواصل ,) 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ **جاري تفكيك الملف عبر الفواصل (,) بناءً على الهندسة الجديدة...**", parse_mode='Markdown')
            
            try:
                file = await context.bot.get_file(doc.file_id)
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    # 1. قراءة الملف كنص خام للتأكد من الترميز
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
                        raise Exception("فشل التعرف على لغة الملف. الرجاء التأكد من ترميز الملف.")
                        
                    # 2. تطبيق الفكرة: التفكيك الحرفي بناءً على الفاصلة (,) وتجاهل علامات التنصيص (")
                    parsed_data = []
                    reader = csv.reader(io.StringIO(decoded_text), delimiter=',', quotechar='"')
                    rows = list(reader)
                    
                    if len(rows) < 2:
                        raise Exception("الملف فارغ أو لا يحتوي على بيانات مقسمة بفواصل.")
                        
                    header = rows[0]
                    
                    # 3. تحديد أرقام الأعمدة من خلال البحث داخل الفواصل
                    c_course, c_id, c_name, c_perc = -1, -1, -1, -1
                    
                    for i, col in enumerate(header):
                        clean_col = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا').replace('"', '')
                        if 'اسمالمقرر' in clean_col: c_course = i
                        elif 'رقمالمتدرب' in clean_col: c_id = i
                        elif 'اسمالمتدرب' in clean_col: c_name = i
                        elif 'نسبهالغياب' in clean_col or 'اجمالينسبه' in clean_col: c_perc = i
                            
                    # 4. خطة الحماية: إذا لم يجد العناوين، نستخدم أرقام أعمدة رايات القياسية
                    if c_id == -1 or c_course == -1:
                        if len(header) >= 19:
                            c_course, c_id, c_name, c_perc = 14, 16, 17, 18
                        else:
                            raise Exception(f"لم يتم العثور على الفواصل المطلوبة. عدد الأعمدة هو {len(header)}")
                            
                    # 5. سحب البيانات وتخزينها
                    for row in rows[1:]:
                        # نضمن أن السطر طويل بما يكفي وبه فواصل كافية
                        if len(row) > max(c_course, c_id, c_name, c_perc):
                            stu_num_clean = "".join(filter(str.isdigit, str(row[c_id])))
                            if stu_num_clean: # إذا الخلية تحتوي على رقم فعلاً
                                parsed_data.append({
                                    'c_nam': str(row[c_course]).strip(),
                                    'stu_num': stu_num_clean,
                                    'stu_nam': str(row[c_name]).strip(),
                                    'parsnt': str(row[c_perc]).strip(),
                                    'day': datetime.now().strftime("%Y-%m-%d")
                                })
                                
                    if not parsed_data:
                        raise Exception("تمت قراءة الفواصل، لكن جميع أرقام الطلاب كانت فارغة!")
                        
                    # 6. الحفظ كإكسل لكي يقرأه البوت
                    df_clean = pd.DataFrame(parsed_data)
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file)
                    
                else:
                    # إذا كان ملف Excel جاهز
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                    
                await status_msg.edit_text(f"✅ **نجاح التحديث بقوة الفواصل!**\n📊 **النتيجة:** تم حفظ `{records_count}` متدرب بنجاح.\n*(اكتب الأمر /db الآن للتأكد)* 🚀", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) 
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تشغيل النسخة المبنية على تفكيك الفواصل (المدمرة)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
