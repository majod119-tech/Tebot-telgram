import os
import io
import base64
import requests
import pandas as pd
import json
import random
import time
import asyncio
from datetime import datetime
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient

# ==========================================
# 1. إعدادات النظام الأساسية
# ==========================================
TOKEN = os.environ.get("TOKEN") 
if not TOKEN: raise ValueError("❌ خطأ قاتل: TOKEN غير موجود في البيئة!")

MONGO_URI = os.getenv("MONGODB_URI")
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

# الاتصال بقاعدة البيانات السحابية (MongoDB)
try:
    client = MongoClient(MONGO_URI)
    db = client["computer_dept_db"] 
    trainees_collection = db["trainees"] # لحفظ ربط حسابات التليجرام
    records_collection = db["academic_records"] # لحفظ بيانات الغياب (بديل الإكسل)
    print("✅ تم الاتصال بـ MongoDB بنجاح!")
except Exception as e: print(f"DB Error: {e}")

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except: HAS_PIL = False

def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: pass
    return {}
def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

# ==========================================
# 2. عقول الذكاء الاصطناعي (الشخصيات المستقلة)
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''), generation_config={"temperature": 0.3})
                break
    except: pass

PROMPT_ADVISOR = (
    "أنت 'المستشار الأكاديمي' لقسم الحاسب في المعهد الصناعي الثانوي ببريدة. "
    "أجب بودية واختصار. الغياب: إنذار عند 15% وحرمان عند 20%. الأعذار تقبل خلال 3 إلى 5 أيام. "
    "المكافأة: 800 ريال وتتوقف إذا نزل المعدل عن 2.00. الاجتياز: 50 درجة."
)

PROMPT_TUTOR = (
    "أنت 'المدرس الخصوصي' لمقررات قسم الحاسب. مهمتك شرح المناهج بطريقة بسيطة وأمثلة. "
    "في البرمجة (بايثون): اشرح الجمل الشرطية وكيفية استخدامها. "
    "في مكونات الحاسب: اشرح كيفية تجميع الجهاز، وتثبيت Windows 10. "
    "في تطبيقات الحاسب المتقدمة: اشرح دوال Excel وقواعد بيانات Access. "
    "شجع الطالب دائماً، واستخدم تنسيقاً جميلاً."
)

PROMPT_SUPPORT = (
    "أنت 'الدعم الفني' لمنصات التدريب (تقني، رايات). "
    "نصائحك: 1. نسيت كلمة المرور؟ استعادتها عبر البريد. 2. المصادقة الثنائية (MFA) تتم عبر البريد. "
    "أعطِ إجابات مرقمة بخطوات واضحة جداً."
)

user_states = {}

# ==========================================
# 3. القوائم التفاعلية
# ==========================================
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المستشار الأكاديمي", "👨‍🏫 المدرس الخصوصي"],
        ["📊 استعلام الغياب (بوابتي)", "🛠️ الدعم الفني للمنصات"],
        ["📝 رفع الغياب والأعذار", "📚 الحقائب والخطط"],
        ["📘 دليل المتدرب", "📬 الاقتراحات والشكاوى"]
    ], resize_keyboard=True, is_persistent=True)

def get_admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 حالة قاعدة البيانات", "📢 إرسال تعميم"],
        ["🧠 تحليل الجودة بالذكاء الاصطناعي", "🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)
def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_pledge_step1_menu(): return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب وأتعهد بالانضباط"]], resize_keyboard=True)

# ==========================================
# 4. معالجة الأوامر والعمليات
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    first_name = update.effective_user.first_name
    welcome_msg = f"أهلاً بك يا {first_name} في قسم الحاسب الآلي 💻✨\n{SEP}\nتم تصميم هذا النظام لخدمتك، اختر الخدمة المطلوبة:"
    await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

async def admin_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_ID:
        await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة القيادة 🛡️", reply_markup=get_admin_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    text = update.message.text.strip()[:500] 
    user_id = str(update.effective_user.id)
    clean_text = text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')).strip()

    # 🔴 أوامر الإدارة
    if user_id == ADMIN_ID:
        if text == "📊 حالة قاعدة البيانات":
            count = records_collection.count_documents({})
            students_count = len(records_collection.distinct("stu_num"))
            return await update.message.reply_text(f"📊 *إحصائيات السحابة:*\nإجمالي السجلات: {count}\nعدد المتدربين: {students_count}", parse_mode='Markdown')
        
        if text == "📢 إرسال تعميم":
            user_states[user_id] = {'flow': 'broadcast'}
            return await update.message.reply_text("📢 أرسل نص التعميم الآن:", reply_markup=get_cancel_menu())

    # 🔵 توجيه الذكاء الاصطناعي
    if user_id in user_states and user_states[user_id].get('flow', '').startswith('ai_'):
        if text == "🔙 الرجوع للقائمة الرئيسية":
            del user_states[user_id]
            return await update.message.reply_text("تم العودة 🏠", reply_markup=get_main_menu())
        
        if not ai_model: return await update.message.reply_text("⚠️ الخدمة قيد التحديث.", reply_markup=get_main_menu())
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        prompt = PROMPT_ADVISOR if user_states[user_id]['flow'] == 'ai_advisor' else (PROMPT_TUTOR if user_states[user_id]['flow'] == 'ai_tutor' else PROMPT_SUPPORT)
        try:
            res = await ai_model.generate_content_async(f"{prompt}\nسؤال المتدرب: {text}")
            return await update.message.reply_text(res.text, reply_markup=get_back_menu(), parse_mode='Markdown')
        except: return await update.message.reply_text("⚠️ خطأ تقني مؤقت.", reply_markup=get_back_menu())

    # 🔵 العمليات المستمرة (تعهد وإلغاء)
    if user_id in user_states:
        state = user_states[user_id]
        if text == "❌ إلغاء العملية" or text == "🔙 الرجوع للقائمة الرئيسية":
            del user_states[user_id]
            return await update.message.reply_text("تم الإلغاء 🏠", reply_markup=get_main_menu())
            
        if state.get('flow') == 'pledge':
            if "تعهد" in text or "نعم" in text:
                doc = f"📄 **تعهد انضباط آلي**\nرقم: {state['stu_num']}\nالمقرر: {state['subject']}\nتم الموافقة إلكترونياً ✅"
                try: await context.bot.send_message(chat_id=GROUP_ID, text=doc, parse_mode='Markdown')
                except: pass
                del user_states[user_id]
                return await update.message.reply_text("✅ تم تسجيل إقرارك بالانضباط في النظام.", reply_markup=get_main_menu())

    # 🟢 أزرار القائمة الرئيسية
    if text == "🤖 المستشار الأكاديمي":
        user_states[user_id] = {'flow': 'ai_advisor'}
        return await update.message.reply_text("🤖 تفضل، ما هو استفسارك عن الأنظمة؟", reply_markup=get_back_menu())
    
    if text == "👨‍🏫 المدرس الخصوصي":
        user_states[user_id] = {'flow': 'ai_tutor'}
        return await update.message.reply_text("👨‍🏫 ماذا تريد أن تذاكر اليوم؟", reply_markup=get_back_menu())
    
    if text == "🛠️ الدعم الفني للمنصات":
        user_states[user_id] = {'flow': 'ai_support'}
        return await update.message.reply_text("🛠️ واجهتك مشكلة في (تقني) أو (رايات)؟ اشرحها لي.", reply_markup=get_back_menu())

    if text == "📝 رفع الغياب والأعذار":
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 ارفق صورة العذر واكتب رقمك التدريبي في الوصف.", reply_markup=get_cancel_menu())

    # 🔒 نظام الاستعلام والمصادقة الصامتة
    if text == "📊 استعلام الغياب (بوابتي)": 
        user_record = trainees_collection.find_one({"telegram_id": user_id})
        if user_record:
            # المتدرب مسجل مسبقاً، اجلب بياناته فوراً
            stu_num = user_record["trainee_id"]
            return await fetch_and_send_academic_record(update, user_id, stu_num)
        else:
            return await update.message.reply_text("🔒 *مرحباً بك!*\nهذه أول مرة تستخدم فيها بوابة الاستعلام.\nلربط حسابك التليجرام بسجلك الأكاديمي بشكل آمن، **الرجاء إرسال رقمك التدريبي الآن:**", parse_mode='Markdown')

    if clean_text.isdigit() and len(clean_text) > 4: 
        # محاولة ربط الحساب
        existing_link = trainees_collection.find_one({"trainee_id": clean_text})
        if existing_link and existing_link["telegram_id"] != user_id:
            return await update.message.reply_text("⚠️ هذا الرقم التدريبي مرتبط بحساب تليجرام آخر. يرجى مراجعة إدارة القسم.")
        
        if not existing_link:
            # ربط جديد
            trainees_collection.insert_one({"telegram_id": user_id, "trainee_id": clean_text})
            await update.message.reply_text("✅ *تم ربط حسابك بنجاح!* لن تحتاج لإدخال رقمك مستقبلاً.", parse_mode='Markdown')
        
        return await fetch_and_send_academic_record(update, user_id, clean_text)

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# دالة جلب السجل الأكاديمي من MongoDB
async def fetch_and_send_academic_record(update, user_id, stu_num):
    await update.message.reply_chat_action(action=ChatAction.TYPING)
    records = list(records_collection.find({"stu_num": stu_num}))
    if not records:
        return await update.message.reply_text("⚠️ لم يتم العثور على بيانات حالية لك. سيتم التحديث قريباً من الإدارة.")
    
    stu_nam = records[0]['stu_nam']
    m = f"🎓 *السجل الأكاديمي*\n👤 {stu_nam}\n🔢 {stu_num}\n{SEP}\n"
    needs_pledge = None
    
    for r in records:
        c = r['c_nam']
        val_str = str(r['parsnt']).replace('%', '').strip()
        if val_str in ['ح', 'ط'] or 'حرمان' in val_str: d = "*حرمان* 🔴"
        else:
            try:
                v = float(val_str)
                if v >= 20: d = f"*{v}%* 🔴 (محروم)"
                elif v >= 15: 
                    d = f"*{v}%* ⚠️ (إنذار)"
                    needs_pledge = c
                else: d = f"*{v}%* 🟢"
            except: d = f"*{val_str}* ⚠️"
        m += f"📖 {c}\n▫️ الغياب: {d}\n\n"
    
    await update.message.reply_text(m, parse_mode='Markdown')
    if needs_pledge:
        user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': stu_num, 'stu_nam': stu_nam, 'subject': needs_pledge}
        await update.message.reply_text(f"⚠️ تجاوزت خطر 15% في: *{needs_pledge}*\n🛑 يرجى الموافقة على التعهد بالأسفل:", parse_mode='Markdown', reply_markup=get_pledge_step1_menu())

# ==========================================
# 7. محرك تحديث البيانات ورادار الخميس
# ==========================================
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    
    # 🔴 تحديث رايات (الخميس) وتفعيل الرادار
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.csv')):
        msg = await update.message.reply_text("⏳ جاري رفع البيانات إلى السحابة (MongoDB) وتفعيل رادار التنبيهات...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            temp_file = "temp_rayat.csv"
            await file.download_to_drive(temp_file)
            
            with open(temp_file, 'rb') as f: raw_bytes = f.read()
            best_enc = 'utf-8'
            for enc in ['utf-8', 'windows-1256', 'cp1256']:
                try: text = raw_bytes.decode(enc); best_enc = enc; break
                except: pass
            
            df = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
            
            col_map = {'c_course': 14, 'c_id': 16, 'c_name': 17, 'c_perc': 18}
            for i, col in enumerate(df.columns):
                c = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا')
                if 'اسمالمقرر' in c: col_map['c_course'] = i
                elif 'رقمالمتدرب' in c: col_map['c_id'] = i
                elif 'اسمالمتدرب' in c: col_map['c_name'] = i
                elif 'نسبه' in c: col_map['c_perc'] = i

            # مسح البيانات القديمة لضخ الجديدة
            records_collection.delete_many({})
            alerts_sent = 0
            
            for _, r in df.iterrows():
                t_id = str(r.iloc[col_map['c_id']]).replace('.0', '').replace('%', '').strip()
                if len(t_id) < 5: continue
                c_name = str(r.iloc[col_map['c_course']]).strip()
                absence = str(r.iloc[col_map['c_perc']]).strip()
                t_name = str(r.iloc[col_map['c_name']]).strip()
                
                # حفظ في القاعدة
                records_collection.insert_one({"stu_num": t_id, "stu_nam": t_name, "c_nam": c_name, "parsnt": absence})
                
                # 📡 رادار التنبيهات الذكي
                try:
                    abs_val = float(absence.replace('%', ''))
                    if abs_val >= 15:
                        linked_user = trainees_collection.find_one({"trainee_id": t_id})
                        if linked_user:
                            tg_id = linked_user["telegram_id"]
                            alert_msg = f"🚨 *تنبيه أكاديمي عاجل* 🚨\n\nأهلاً بك، نود إشعارك بأن نسبة غيابك في مقرر: *{c_name}* قد وصلت إلى *{absence}*.\n\n⚠️ يرجى الانضباط فوراً لتفادي طي القيد."
                            await context.bot.send_message(chat_id=tg_id, text=alert_msg, parse_mode='Markdown')
                            alerts_sent += 1
                except: pass

            os.remove(temp_file)
            await msg.edit_text(f"✅ *تم التحديث بنجاح!*\nتم ضخ البيانات في السحابة.\n📡 الرادار الآلي: تم إرسال ({alerts_sent}) رسالة تنبيه للمتدربين المهددين بالحرمان.", parse_mode='Markdown')
        except Exception as e: 
            await msg.edit_text(f"⚠️ فشل التحديث: {e}")
        return

def background_tasks(): pass
def run_web_server(): pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    print("🚀 تشغيل النظام V5.0 (نسخة الاعتماد المؤسسي وقواعد البيانات)...")
    app.run_polling()

if __name__ == '__main__': main()
