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
أنت المعلم الذكي الرسمي لقسم الحاسب الآلي وتقنية المعلومات في المعهد الصناعي الثانوي ببريدة.
- الغياب والحرمان: إنذار 15% وحرمان 20%.
- المكافأة: 800 ريال.
- درجات النجاح: 50 للمعاهد.
- الحقائب: {DRIVE_LINK}
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
    """أداة سريّة للمدير للتحقق من حفظ البيانات فعلياً"""
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
    welcome_msg = f"أهلاً بك يا {update.effective_user.first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n👇 **اختر الخدمة:**"
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()

    if text in ["🔙 الرجوع للقائمة الرئيسية", "📚 الحقائب التدريبية", "📄 الخطط التدريبية", "📊 استعلام الغياب", "📝 رفع الغياب والأعذار", "🔗 المنصات الإلكترونية", "📅 التقويم التدريبي", "📰 أخبار القسم والمعهد", "📍 موقع القسم", "❓ الأسئلة الشائعة", "📘 دليل المتدرب الرسمي", "📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والإضافات"]:
        ai_sessions[user_id] = False

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 **تم العودة للقائمة الرئيسية.**", reply_markup=get_main_menu())
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 **استعلام الغياب**\n👇 **أرسل رقمك التدريبي...**", parse_mode='Markdown')
        return

    # 🌟 محرك البحث الكاسح (لا يفلت منه أي رقم) 🌟
    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'):
                await update.message.reply_text("⚠️ **قاعدة البيانات فارغة.** (الرجاء من الإدارة إرسال ملف رايات أولاً).", parse_mode='Markdown')
                return

            df = pd.read_excel('data.xlsx', dtype=str)
            df.columns = df.columns.astype(str).str.strip()
            
            # تنظيف أرقام المتدربين في قاعدة البيانات أثناء البحث لمطابقتها مع إدخال المستخدم
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                m = f"✅ **السجل لـ:** `{stu_nam}`{SEP}"
                
                for _, r in res.iterrows():
                    raw_val = str(r.get('parsnt', '0')).strip()
                    if re.match(r'^\d{4}-\d{2}-\d{2}', raw_val):
                        y, month, d = raw_val.split()[0].split('-')
                        raw_val = f"{d}.{month}"
                    try:
                        val = float(raw_val)
                        icon = "🔴 حرمان" if val >= 20 else ("⚠️ إنذار" if val >= 15 else "🟢 منتظم")
                        display_val = f"%{val} {icon}"
                    except Exception:
                        val = 0.0
                        display_val = f"{raw_val} ⚠️"
                    
                    day_val = str(r.get('day', 'غير محدد')).replace(' 00:00:00', '').strip()
                    m += f"📖 {r['c_nam']}: {display_val}\n📅 تاريخ التحديث: {day_val}\n\n"
                
                await update.message.reply_text(m, parse_mode='Markdown')
            else: 
                await update.message.reply_text("❌ **الرقم التدريبي غير مسجل أو لا يوجد غياب.**", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ **حدث خطأ برمجي:** `{str(e)}`", parse_mode='Markdown')
        return

    # باقي الأوامر السريعة
    if text == "📚 الحقائب التدريبية": 
        await update.message.reply_text("📚 **الحقائب:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول", url=DRIVE_LINK)]]), parse_mode='Markdown')
        return
        
    if not ai_sessions.get(user_id):
        await update.message.reply_text("⚠️ **الرجاء اختيار خدمة من الأسفل 👇**", reply_markup=get_main_menu())

# --- 🌟 محرك سحب ملفات رايات المطلق (خالٍ من العيوب 100%) 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            status_msg = await update.message.reply_text("⏳ **جاري فك تشفير ملف رايات وتفريغ البيانات...**", parse_mode='Markdown')
            
            try:
                file = await context.bot.get_file(doc.file_id)
                
                if doc.file_name.endswith('.csv'):
                    temp_file = "temp_rayat.csv"
                    await file.download_to_drive(temp_file)
                    
                    # 🌟 هنا السر: نقرأ الملف بمحرك بايثون للبحث التلقائي عن الفواصل، مع تجاهل أي سطور تالفة
                    df_raw = None
                    for enc in ['cp1256', 'windows-1256', 'utf-8-sig', 'utf-8']:
                        try:
                            # نطلب من باندا قراءة الملف وعناوينه
                            temp_df = pd.read_csv(temp_file, encoding=enc, dtype=str, sep=None, engine='python')
                            # إذا تمكن من فصله لأكثر من 15 عمود، فهذا هو الترميز الصحيح حتماً!
                            if len(temp_df.columns) > 15:
                                df_raw = temp_df
                                break
                        except Exception:
                            continue
                    
                    if df_raw is None:
                        raise Exception("الملف يحتوي على تشفير غير معروف.")

                    # 🌟 الخطة العمياء المطلقة: أخذ الأعمدة بأرقامها مباشرة بناءً على ملفك الذي أرسلته 🌟
                    # بناءً على ملفك: 14=المقرر، 16=رقم المتدرب، 17=اسم المتدرب، 18=النسبة
                    cols = list(df_raw.columns)
                    if len(cols) < 19:
                        raise Exception(f"ملف رايات ناقص، عدد الأعمدة الحالي هو {len(cols)}")

                    df_clean = pd.DataFrame()
                    df_clean['c_nam'] = df_raw[cols[14]]
                    df_clean['stu_num'] = df_raw[cols[16]]
                    df_clean['stu_nam'] = df_raw[cols[17]]
                    df_clean['parsnt'] = df_raw[cols[18]]
                    
                    # الغسيل الكيميائي لأرقام الطلاب لضمان نجاح البحث
                    df_clean['stu_num'] = df_clean['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                    df_clean = df_clean[df_clean['stu_num'] != ''] # مسح الصفوف التي لا تحتوي أرقام
                    
                    df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
                    df_clean.to_excel("data.xlsx", index=False)
                    records_count = len(df_clean)
                    os.remove(temp_file) 
                    
                else:
                    await file.download_to_drive("data.xlsx")
                    df_clean = pd.read_excel('data.xlsx')
                    records_count = len(df_clean)
                    
                await status_msg.edit_text(f"✅ **تم اختراق رايات بنجاح!**\n📊 **النتيجة:** حفظ `{records_count}` سجل طالب نقي.\n*(يمكنك الآن تجربة البحث، أو كتابة /db للتأكد)* 🚀", parse_mode='Markdown')
            except Exception as e:
                await status_msg.edit_text(f"⚠️ **فشل التحديث:** `{e}`", parse_mode='Markdown')
            return

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("db", db_status_command)) # 🌟 أمر سري لك كمدير 🌟
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تشغيل النسخة المطلقة...")
    app.run_polling()

if __name__ == '__main__': 
    main()
