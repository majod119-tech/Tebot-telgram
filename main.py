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
                    
                    # 🌟 هنا الحل الساحق: قراءة الملف بالفواصل القياسية (,) وتجربة الترميزات الصحيحة
                    df_raw = None
                    for enc in ['utf-8-sig', 'windows-1256', 'utf-8', 'cp1256']:
                        try:
                            # نحدد أن الفاصل هو فاصلة (,) وليس فراغات عشوائية
                            temp_df = pd.read_csv(temp_file, encoding=enc, dtype=str, sep=',')
                            if len(temp_df.columns) >= 19:
                                df_raw = temp_df
                                break
                        except Exception:
                            pass
                    
                    if df_raw is None:
                        raise Exception("فشل في تفكيك أعمدة الملف، تأكد من تصدير رايات بشكل صحيح.")

                    df_clean = pd.DataFrame()
                    
                    # 🌟 نبحث عن الأعمدة بالاسم الدقيق الموجود في ملفك لضمان عدم الخطأ 🌟
                    try:
                        c_course = next(c for c in df_raw.columns if 'اسم المقرر' in str(c))
                        c_id = next(c for c in df_raw.columns if 'رقم المتدرب' in str(c))
                        c_name = next(c for c in df_raw.columns if 'اسم المتدرب' in str(c))
                        c_perc = next(c for c in df_raw.columns if 'نسبة الغياب بعذر وبدون' in str(c))
                        
                        df_clean['c_nam'] = df_raw[c_course]
                        df_clean['stu_num'] = df_raw[c_id]
                        df_clean['stu_nam'] = df_raw[c_name]
                        df_clean['parsnt'] = df_raw[c_perc]
                    except StopIteration:
                        # 🌟 الخطة العمياء بناءً على ترتيب رايات الحقيقي 🌟
                        df_clean['c_nam'] = df_raw.iloc[:, 14]
                        df_clean['stu_num'] = df_raw.iloc[:, 16]
                        df_clean['stu_nam'] = df_raw.iloc[:, 17]
                        df_clean['parsnt'] = df_raw.iloc[:, 18]

                    # 🌟 تنظيف الأرقام: سحب الأرقام فقط ومسح الفراغات 🌟
                    df_clean['stu_num'] = df_clean['stu_num'].astype(str).apply(lambda x: ''.join(filter(str.isdigit, x)))
                    df_clean = df_clean[df_clean['stu_num'] != ''] # حذف أي سطر فارغ
                    
                    df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file) 
                    
                else:
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                    
                await status_msg.edit_text(f"✅ **نجاح التحديث من رايات!**\n📊 **النتيجة:** حفظ `{records_count}` سجل.\n*(اكتب /db للتأكد من الأرقام، أو جرب البحث)* 🚀", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) # 🌟 الأمر السري 🌟
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تشغيل النسخة المخصصة لملفات رايات...")
    app.run_polling()

if __name__ == '__main__': 
    main()
