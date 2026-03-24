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
if not TOKEN:
    raise ValueError("❌ خطأ قاتل: TOKEN غير موجود في البيئة!")

MONGO_URI = os.getenv("MONGODB_URI")
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
TVTC_X_LINK = "https://x.com/tvtc_m_buraidah"

SCORES_FILE = "scores.json"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        trainees_collection = db["trainees"] 
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

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

EXCEL_CACHE = None
LAST_CACHE_TIME = 0
def get_excel_data():
    global EXCEL_CACHE, LAST_CACHE_TIME
    file_path = 'data.xlsx'
    if not os.path.exists(file_path): return None
    current_mtime = os.path.getmtime(file_path)
    if EXCEL_CACHE is None or current_mtime > LAST_CACHE_TIME:
        try:
            df = pd.read_excel(file_path, dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
            EXCEL_CACHE = df
            LAST_CACHE_TIME = current_mtime
        except: return None
    return EXCEL_CACHE

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
    "في البرمجة (بايثون): اشرح الجمل الشرطية (if, else, elif) وكيفية استخدامها. "
    "في مكونات الحاسب: اشرح كيفية تجميع الجهاز، وتثبيت Windows 10، وأساسيات استكشاف الأخطاء. "
    "في تطبيقات الحاسب المتقدمة: اشرح دوال Excel (ROUND, IF, AVERAGEIF) وقواعد بيانات Access. "
    "شجع الطالب دائماً، واستخدم تنسيقاً جميلاً."
)

PROMPT_SKILLS = (
    "أنت 'مستشار المهارات الوظيفية'. هدفك بناء (سجل مهارات شخصية) للمتدربين لرفع قابليتهم للتوظيف. "
    "اسأل المتدرب عن هواياته وماذا تعلم في المعهد، ثم صغ له نقاط قوة يكتبها في سيرته الذاتية. "
    "كن محفزاً جداً وأخبره أن خريج الحاسب الآلي مطلوب بقوة في سوق العمل السعودي ضمن رؤية 2030."
)

PROMPT_SUPPORT = (
    "أنت 'الدعم الفني' لمنصات التدريب (تقني، رايات). "
    "نصائحك: 1. نسيت كلمة المرور؟ يمكن استعادتها عبر البريد. 2. المصادقة الثنائية (MFA) تتم عبر البريد. "
    "3. لمعرفة الجدول ومواعيد الحضور في منصة تقني: اضغط أيقونة الحساب ثم التقويم. 4. لتنزيل الملفات: اختر المقرر ثم اسم الملف. "
    "أعطِ إجابات مرقمة بخطوات واضحة جداً."
)

user_states = {}

# ==========================================
# 3. القوائم التفاعلية (الواجهة الاحترافية)
# ==========================================
def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🤖 المستشار الأكاديمي", "👨‍🏫 المدرس الخصوصي"],
        ["💼 بناء سجل المهارات", "🛠️ الدعم الفني للمنصات"],
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        ["📚 الحقائب والخطط", "📘 دليل المتدرب"],
        ["📬 الاقتراحات والشكاوى", "🕹️ قسم الألعاب والتقنية"]
    ], resize_keyboard=True, is_persistent=True)

def get_admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 حالة قاعدة البيانات", "💾 سحب نسخة احتياطية"],
        ["📢 إرسال تعميم", "📈 تقرير التميز المؤسسي"],
        ["📥 تصدير كشوفات الإكسل", "🧠 تحليل الجودة بالذكاء الاصطناعي"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ], resize_keyboard=True, is_persistent=True)

def get_cancel_menu(): return ReplyKeyboardMarkup([["❌ إلغاء العملية"]], resize_keyboard=True)
def get_back_menu(): return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)
def get_pledge_step1_menu(): return ReplyKeyboardMarkup([["✅ نعم، أطلعت على نسبة الغياب"]], resize_keyboard=True)
def get_pledge_step2_menu(): return ReplyKeyboardMarkup([["🏥 عذر طبي", "👨‍👩‍👧‍👦 ظروف عائلية طارئة"], ["🚗 مشكلة في المواصلات", "⚙️ أعطال تقنية/أخرى"], ["❌ إلغاء العملية"]], resize_keyboard=True)
def get_pledge_step3_menu(): return ReplyKeyboardMarkup([["✍️ أقر وأتعهد بالانضباط للحفاظ على مستقبلي التدريبي"]], resize_keyboard=True)

# ==========================================
# 4. معالجة الأوامر والعمليات
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    first_name = update.effective_user.first_name

    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_msg = f"أهلاً بك يا {first_name} في قسم الحاسب الآلي 💻✨\n{SEP}\nهنا تجد كل ما يخدم مسيرتك التدريبية، اختر الخدمة المطلوبة:"
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
            df = get_excel_data()
            if df is None: return await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
            return await update.message.reply_text(f"📊 *السجلات المؤتمتة:* {len(df)} سجل.", parse_mode='Markdown')
        if text == "📥 تصدير كشوفات الإكسل":
            await update.message.reply_text("⏳ جاري توليد الكشف...")
            try:
                df = get_excel_data()
                df['clean_parsnt'] = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce')
                w_df = df[(df['clean_parsnt'] >= 15) | (df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False))]
                export_df = w_df[['stu_num', 'stu_nam', 'c_nam', 'parsnt']]
                export_df.to_excel("Warnings.xlsx", index=False)
                await context.bot.send_document(chat_id=user_id, document=open("Warnings.xlsx", 'rb'))
            except: await update.message.reply_text("⚠️ خطأ بالتصدير.")
            return
        if text == "🧠 تحليل الجودة بالذكاء الاصطناعي":
            if not ai_model: return await update.message.reply_text("⚠️ الذكاء الاصطناعي غير مفعل.")
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            res = await ai_model.generate_content_async("قم بصياغة ملخص إداري من 3 نقاط لرفع نسبة رضا المتدربين عن تفعيل سجل المهارات الشخصية وقابلية التوظيف في قسم الحاسب.")
            return await update.message.reply_text(f"🧠 *توصيات الجودة:*\n\n{res.text}", parse_mode='Markdown')

    # 🔵 توجيه الذكاء الاصطناعي (الشخصيات)
    if user_id in user_states and user_states[user_id].get('flow', '').startswith('ai_'):
        if text == "🔙 الرجوع للقائمة الرئيسية":
            del user_states[user_id]
            return await update.message.reply_text("تم العودة 🏠", reply_markup=get_main_menu())
        
        if not ai_model: return await update.message.reply_text("⚠️ الخدمة قيد التحديث.", reply_markup=get_main_menu())
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        flow_type = user_states[user_id]['flow']
        if flow_type == 'ai_advisor': prompt = PROMPT_ADVISOR
        elif flow_type == 'ai_tutor': prompt = PROMPT_TUTOR
        elif flow_type == 'ai_skills': prompt = PROMPT_SKILLS
        elif flow_type == 'ai_support': prompt = PROMPT_SUPPORT
        
        try:
            res = await ai_model.generate_content_async(f"{prompt}\nسؤال المتدرب: {text}")
            return await update.message.reply_text(res.text, reply_markup=get_back_menu(), parse_mode='Markdown')
        except: return await update.message.reply_text("⚠️ خطأ تقني مؤقت.", reply_markup=get_back_menu())

    # 🔵 معالجة التعهدات والأعذار
    if user_id in user_states:
        state = user_states[user_id]
        if text == "❌ إلغاء العملية" or text == "🔙 الرجوع للقائمة الرئيسية":
            del user_states[user_id]
            return await update.message.reply_text("تم الإلغاء 🏠", reply_markup=get_main_menu())
        if state.get('flow') == 'pledge':
            step = state['step']
            if step == 1:
                user_states[user_id]['step'] = 2
                return await update.message.reply_text("2️⃣ اختر العذر الرئيسي لكثرة غياباتك:", reply_markup=get_pledge_step2_menu())
            elif step == 2:
                user_states[user_id]['excuse'] = text
                user_states[user_id]['step'] = 3
                return await update.message.reply_text("3️⃣ الإقرار النهائي:", reply_markup=get_pledge_step3_menu())
            elif step == 3:
                completed = load_json(INTERROGATIONS_FILE)
                completed.setdefault(state['stu_num'], []).append(state['subject'])
                save_json(INTERROGATIONS_FILE, completed)
                doc = f"📄 **وثيقة تعهد إلكتروني**\nأقر المتدرب/ {state['stu_nam']}\nالمقرر/ {state['subject']}\nالعذر/ {state['excuse']}\n✅ مُعتمد | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                try: await context.bot.send_message(chat_id=GROUP_ID, text=doc, parse_mode='Markdown')
                except: pass
                del user_states[user_id]
                return await update.message.reply_text(f"✅ تم التوثيق.\n\n{doc}", parse_mode='Markdown', reply_markup=get_main_menu())
        if state.get('flow') == 'feedback':
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 شكوى/مقترح:\nالنص: {text}")
                del user_states[user_id]
                return await update.message.reply_text("✅ تم الإرسال للإدارة.", reply_markup=get_main_menu())
            except: pass

    # 🟢 أزرار القائمة الرئيسية للمتدربين
    if text == "🤖 المستشار الأكاديمي":
        user_states[user_id] = {'flow': 'ai_advisor'}
        return await update.message.reply_text("🤖 أنا المستشار الأكاديمي. تفضل، ما هو استفسارك عن الأنظمة أو اللوائح؟", reply_markup=get_back_menu())
    
    if text == "👨‍🏫 المدرس الخصوصي":
        user_states[user_id] = {'flow': 'ai_tutor'}
        return await update.message.reply_text("👨‍🏫 أهلاً بك! أنا جاهز لشرح (البرمجة، مكونات الحاسب، وتطبيقات Office). ماذا تريد أن تذاكر اليوم؟", reply_markup=get_back_menu())
    
    if text == "💼 بناء سجل المهارات":
        user_states[user_id] = {'flow': 'ai_skills'}
        return await update.message.reply_text("💼 خطوتك الأولى للوظيفة تبدأ من هنا! شاركني: ما هي البرامج أو المهارات التي تعلمتها بالمعهد حتى الآن؟", reply_markup=get_back_menu())
    
    if text == "🛠️ الدعم الفني للمنصات":
        user_states[user_id] = {'flow': 'ai_support'}
        return await update.message.reply_text("🛠️ واجهتك مشكلة في منصة (تقني) أو (رايات)؟ اكتب لي المشكلة وسأعطيك الحل.", reply_markup=get_back_menu())

    if text == "📝 رفع الغياب والأعذار":
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 ارفق صورة العذر الطبي واكتب رقمك التدريبي في الوصف.", reply_markup=get_cancel_menu())

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        return await update.message.reply_text("📬 اكتب رسالتك وسوف تصل بسرية...", reply_markup=get_cancel_menu())

    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي الآن...")
    if text == "📚 الحقائب والخطط": return await update.message.reply_text("📚 *مكتبة القسم:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول للحقائب", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "📘 دليل المتدرب": 
        if os.path.exists("trainee_guide.pdf"): return await update.message.reply_document(document=open("trainee_guide.pdf", 'rb'), caption="📘 *دليل المتدرب*", parse_mode='Markdown')
        else: return await update.message.reply_text("⚠️ الملف غير متوفر حالياً.")

    # 🟢 الاستعلام بالرقم التدريبي
    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        try:
            df = get_excel_data()
            if df is None: return await update.message.reply_text("⚠️ قاعدة البيانات غير متوفرة.")
            res = df[df['stu_num'] == clean_text]
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                comps = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subj = None; has_dep = False
                m = f"🎓 *السجل الأكاديمي*\n👤 {stu_nam}\n🔢 {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    c = str(r.get('c_nam', '')).strip()
                    val_str = str(r.get('parsnt', '0')).replace('%', '').strip()
                    if val_str in ['ح', 'ط'] or 'حرمان' in val_str: d = "*حرمان* 🔴"; has_dep = True
                    else:
                        try:
                            v = float(val_str)
                            if v >= 20: d = f"*{v}%* 🔴"; has_dep = True
                            elif v >= 15: d = f"*{v}%* ⚠️"; subj = c if c not in comps else None
                            else: d = f"*{v}%* 🟢"
                        except: d = f"*{val_str}* ⚠️"
                    m += f"📖 {c}\n▫️ {d}\n\n"
                await update.message.reply_text(m, parse_mode='Markdown')

                if subj:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subj}
                    return await update.message.reply_text(f"⚠️ تجاوزت 15% في: *{subj}*\n🛑 النظام مغلق لإكمال التعهد!", parse_mode='Markdown', reply_markup=get_pledge_step1_menu())
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: pass
        return

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.csv')):
        msg = await update.message.reply_text("⏳ جاري التحديث...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            await file.download_to_drive("data.xlsx")
            global EXCEL_CACHE; EXCEL_CACHE = None 
            await msg.edit_text("✅ تم تحديث قاعدة البيانات بنجاح!")
        except: await msg.edit_text("⚠️ فشل التحديث.")
        return

    if update.message.photo or update.message.document:
        cap = str(update.message.caption or "")
        stu_id = ''.join(filter(str.isdigit, cap))
        if len(stu_id) < 5: return await update.message.reply_text("🛑 ارفق الصورة واكتب رقمك التدريبي في الوصف.")
            
        msg = await update.message.reply_text("⏳ جاري الفحص...")
        try:
            if update.message.photo and HAS_PIL:
                file = await context.bot.get_file(update.message.photo[-1].file_id)
                img_io = io.BytesIO()
                await file.download_to_memory(img_io)
                img = Image.open(img_io)
                
                txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
                ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id}", fill="white")
                txt_img = txt_img.resize((img.width, int(img.width * 50 / 1000)))
                img.paste(txt_img, (0, img.height - txt_img.height)) 
                
                out = io.BytesIO()
                img.save(out, format='JPEG')
                out.seek(0)
                await context.bot.send_photo(chat_id=GROUP_ID, photo=out, caption=f"📥 عذر طبي | رقم: {stu_id}")
            if user_id in user_states: del user_states[user_id]
            await msg.edit_text("✅ تم إرسال العذر للإدارة.")
        except: await msg.edit_text("⚠️ خطأ بالمعالجة.")

def background_tasks(): pass
def run_web_server(): pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("admin", admin_gateway))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    print("🚀 تشغيل النظام V4.0 (واجهة المتدربين المتطورة)...")
    app.run_polling()

if __name__ == '__main__': main()
