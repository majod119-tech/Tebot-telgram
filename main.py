import os
import io
import requests
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
from pymongo import MongoClient

# 🔴 استدعاء ملف أدوات الإدارة 🔴
from admin_features import (
    ADMIN_ID, admin_command, db_status_command, backup_command, 
    broadcast_command, report_command, process_admin_excel
)

# 🔴 استدعاء ملف الأزرار والقوائم 🔴
from menus import (
    get_main_menu, get_cancel_menu, get_back_menu, get_plans_menu, 
    get_games_menu, get_pledge_step1_menu, get_pledge_step2_menu, get_pledge_step3_menu
)

# 🔴 استدعاء ملف الإعدادات 🔴
from bot_settings import *

# 🔴 استدعاء النصائح من مجلد config 🔴
try:
    from config.tips import TECH_TIPS
except ImportError:
    # نسخة احتياطية لو كان الملف فيه مشكلة
    TECH_TIPS = ["💡 نصيحة: احرص دائماً على أخذ نسخة احتياطية لملفاتك."] 


# --- 🌟 الاتصال بقاعدة البيانات السحابية (MongoDB) ---
MONGO_URI = os.getenv("MONGODB_URI")
OPENCLAW_URL = "https://openclaw-server-2j6r.onrender.com/api/chat" 
db = None

try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        trainees_collection = db["trainees"] 
        print("✅ تم الاتصال بعقل البوت السحابي (MongoDB) بنجاح!")
    else:
        print("⚠️ تحذير: لم يتم العثور على رابط MONGODB_URI في متغيرات البيئة.")
except Exception as e:
    print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")

# --- 🌟 استدعاء مكتبة الصور للختم الآلي ---
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def load_json(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: return {}
    return {}

def save_json(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

try:
    from questions_bank import QUESTIONS
except Exception as e:
    QUESTIONS = [{"q": "ما هو عنوان الـ IP لـ (Localhost)؟", "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"], "answer": 1}]

TECH_TIPS = [
    "💡 نصيحة أمنية: استخدم مفتاحي (Win + L) لقفل جهازك فوراً عند الابتعاد عنه.",
    "🛡️ نصيحة تقنية: احرص دائماً على تحديث نظام التشغيل لديك لسد الثغرات.",
    "🚀 نصيحة برمجية: التنسيق والمسافات البادئة في لغة بايثون هي أساس عمل الكود."
]

# --- 🌟 إعدادات النظام ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-1003701324722" 
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"
SEP = "━━━━━━━━━━━━━━"
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
        except: pass
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

AI_KNOWLEDGE = (
    "أنت 'المساعد الرقمي'، مساعد ذكي ورسمي لقسم الحاسب الآلي في المعهد الصناعي الثانوي ببريدة. "
    "مهمتك الإجابة على جميع استفسارات المستخدمين بشكل مبسط، ودي، ومختصر جداً.\n"
    f"رابط الحقائب التدريبية: {DRIVE_LINK}).\n"
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                ai_model = genai.GenerativeModel(m.name.replace('models/', ''), generation_config={"temperature": 0.2})
                break
    except: pass

user_states = {}
active_challenges = {}

# --- 🌟 القوائم التفاعلية 🌟 ---

# --- 🌟 أوامر عن المبادرة 🌟 ---
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    msg = f"🏆 **نبذة عن المبادرة (جائزة التميز بمنطقة القصيم)** 🏆\n{SEP}\nابتكار تقني يخدم منظومة التدريب..."
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- 🌟 دالة البداية 🌟 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    
    user = update.effective_user
    user_id = str(user.id)
    first_name = user.first_name
    username = user.username

    stats = load_json(STATS_FILE)
    if user_id not in stats.get("users_list", []): 
        stats.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, stats)
    
    if user_id in user_states: del user_states[user_id]
    
    welcome_prefix = f"أهلاً بك يا {first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
    
    try:
        if db is not None:
            existing_user = db["trainees"].find_one({"telegram_id": user_id})
            if not existing_user:
                new_trainee = {
                    "telegram_id": user_id, "name": first_name, "username": username,
                    "role": "student", "absence_percentage": 0, "pledges_count": 0, "join_date": datetime.now()
                }
                db["trainees"].insert_one(new_trainee)
                welcome_prefix = f"🎉 أهلاً بك يا {first_name}! تم فتح ملف إلكتروني لك بنجاح في النظام.\n{SEP}\n"
            else:
                pledges = existing_user.get("pledges_count", 0)
                welcome_prefix = f"أهلاً بعودتك يا {first_name}! (سجلك يحتوي على {pledges} تعهد).\n{SEP}\n"
    except Exception as e: pass

    welcome_msg = (welcome_prefix + "أنا نظامك الرقمي المتكامل. تم تصميمي لتوفير وقتك وتسهيل رحلتك التدريبية.\n\n👇 الرجاء اختيار الخدمة المطلوبة من القائمة السفلية:")
    try:
        if os.path.exists('IMG_1058.jpeg'): await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome_msg, reply_markup=get_main_menu())
        else: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome_msg, reply_markup=get_main_menu())

# --- 🌟 العمليات المنطقية 🌟 ---
async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 

    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    trans_table = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean_text = text.translate(trans_table).strip()
        # 🔴 ربط أزرار الإدارة النصية بالأوامر 🔴
    if user_id == ADMIN_ID:
        if text == "حالة قاعدة البيانات 📊" or text == "حالة قاعدة البيانات":
            return await db_status_command(update, context)
        if text == "سحب نسخة احتياطية 💾" or text == "سحب نسخة احتياطية":
            return await backup_command(update, context)
        if text == "تقرير سير العملية الأسبوعية 📑" or text == "تقرير سير العملية الأسبوعية":
            return await report_command(update, context)


    if text == "🦞 مساعد OpenClaw":
        if user_id != ADMIN_ID: return
        user_states[user_id] = {'flow': 'openclaw'}
        msg = ("🦞 **مرحباً بك في وحدة OpenClaw الاستشارية!**\n\n• **لتحديث القاعدة:** أرسل ملف (رايات) بصيغة CSV هنا مباشرة.\n• **للتحليل:** اكتب (حلل رايات).\n• **للتنظيف:** اكتب (تفريغ رايات).\n\nأنا جاهز لخدمتك يا مدير.")
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_back_menu())
        return

    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            await update.message.reply_text("تم العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())
            return

        if state['flow'] == 'openclaw':
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            try:
                payload = {"message": text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                reply = response.json().get("response", "حدث خطأ في الاتصال.")
                await update.message.reply_text(reply, parse_mode='Markdown')
            except Exception as e: await update.message.reply_text(f"⚠️ خطأ: {str(e)}")
            return

        if state['flow'] == 'pledge':
            step = state['step']
            if step == 1:
                user_states[user_id]['aware'] = text
                user_states[user_id]['step'] = 2
                return await update.message.reply_text("2️⃣ *فضلاً، اختر العذر الرئيسي لكثرة غياباتك من القائمة بالأسفل:*\n(أو يمكنك كتابة عذرك يدوياً)", parse_mode='Markdown', reply_markup=get_pledge_step2_menu())
            
            elif step == 2:
                if len(text) < 4: return await update.message.reply_text("⚠️ العذر غير واضح، اختر من الأزرار بالأسفل أو اكتب عذراً مفصلاً:", reply_markup=get_pledge_step2_menu())
                user_states[user_id]['excuse'] = text
                user_states[user_id]['step'] = 3
                return await update.message.reply_text("3️⃣ *الإقرار النهائي:*\nهل تتعهد بالانضباط والالتزام لتفادي الحرمان النهائي (20%) وطي القيد؟\n*(اضغط على زر التعهد بالأسفل)*", parse_mode='Markdown', reply_markup=get_pledge_step3_menu())
            
            elif step == 3:
                if "تعهد" not in text and "أقر" not in text and "نعم" not in text:
                    return await update.message.reply_text("⚠️ لم يتم قبول إقرارك!\nيرجى الضغط على زر الإقرار بالأسفل للموافقة:", reply_markup=get_pledge_step3_menu())
                
                completed = load_json(INTERROGATIONS_FILE)
                completed.setdefault(state['stu_num'], []).append(state['subject'])
                save_json(INTERROGATIONS_FILE, completed)
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                official_document = f"🏛️ **المؤسسة العامة للتدريب التقني والمهني**\n📍 **المعهد الصناعي الثانوي ببريدة - قسم الحاسب**\n{SEP}\n📄 **وثيقة تعهد إلكتروني بالانضباط الأكاديمي**\nأقر وأتعهد أنا المتدرب / **{state['stu_nam']}**\nالرقم التدريبي / **{state['stu_num']}**\nبشأن المقرر التدريبي / **{state['subject']}**\nبأنني اطلعت على نسبة غيابي التي بلغت حد (الإنذار)، وأتعهد بالانضباط التام.\n📝 **العذر المُسجل للمتدرب:** {state['excuse']}\n✅ **حالة الاعتماد:** (مُعتمد ومُوقع إلكترونياً من قبل المتدرب)\n⏱️ **تاريخ وتوثيق الاعتماد:** {timestamp}\n{SEP}"
                try: await context.bot.send_message(chat_id=GROUP_ID, text=official_document, parse_mode='Markdown')
                except Exception as e: pass 
                
                del user_states[user_id]
                await update.message.reply_text(official_document, parse_mode='Markdown')
                await update.message.reply_text("✅ *تم توثيق إقرارك رسمياً ورفع نسخة للإدارة.*\nاحرص على الحضور لتفادي طي القيد.", parse_mode='Markdown', reply_markup=get_main_menu())
                return

        if state['flow'] == 'feedback':
            if len(text) < 15: return await update.message.reply_text("⚠️ الرسالة قصيرة جداً!\nالرجاء كتابة رسالتك بالتفصيل (أكثر من 15 حرف) لكي نأخذها بجدية.", reply_markup=get_cancel_menu())
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 *شكوى/مقترح:*\nالمرسل: {update.effective_user.first_name}\nالنص: {text}", parse_mode='Markdown')
                del user_states[user_id]
                return await update.message.reply_text("✅ تم إرسال رسالتك للإدارة بسرية تامة.", reply_markup=get_main_menu())
            except Exception as e: 
                del user_states[user_id]
                return await update.message.reply_text("⚠️ حدث خطأ أثناء إرسال الشكوى. يرجى المحاولة لاحقاً.", reply_markup=get_main_menu())

        if state['flow'] == 'ai':
            if not ai_model:
                del user_states[user_id]
                return await update.message.reply_text("⚠️ المعلم غير متصل حالياً.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                response = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم الذكي:\n\n{response.text}", reply_markup=get_back_menu())
            except: return await update.message.reply_text("⚠️ خطأ تقني بالذكاء الاصطناعي.", reply_markup=get_back_menu())

        if state['flow'] == 'excuse':
            return await update.message.reply_text("⚠️ هذا نص! الرجاء إرسال (صورة أو ملف PDF) للعذر الطبي مع كتابة رقمك في الوصف الخاص بالصورة.", reply_markup=get_cancel_menu())

    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        msg = "📝 *نظام رفع الأعذار:*\nالرجاء إرفاق (صورة العذر) الآن، ويجب كتابة (رقمك واسمك) في خانة الوصف (Caption).\n\n⚠️ *تُقبل الأعذار الرسمية والطبية فقط بعد الغياب خلال 3 إلى 5 أيام.*"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        msg = "📬 *صندوق الإدارة:*\nاكتب رسالتك، اقتراحك، أو شكواك الآن بالتفصيل وسوف تصل للإدارة بسرية تامة...\n\n*(نرجو إرفاق اسم المتدرب والرقم التدريبي إذا لزم الأمر للتواصل معك)*"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_cancel_menu())
        return

    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        await update.message.reply_text("🤖 *المعلم الذكي!*\n💬 أنا جاهز، اكتب أي سؤال تقني أو إداري وسأجيبك فوراً...", parse_mode='Markdown', reply_markup=get_back_menu())
        return

    if text == "📊 استعلام الغياب":
        msg = "🔎 *استعلام عن نسبة الغياب (تُحدث أسبوعياً)*\n👇 أرسل رقمك التدريبي الآن (أرقام فقط)..."
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text == "📚 الحقائب التدريبية": 
        msg = "📚 *هذا رابط المقررات التدريبية لقسم الحاسب الآلي في المعهد الصناعي الثانوي:*"
        return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 الدخول للمستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
        
    if text == "🔗 المنصات الإلكترونية": 
        kb = [[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")]]
        return await update.message.reply_text("🌐 *المنصات الإلكترونية للتدريب:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
    if text == "📍 موقع القسم": return await update.message.reply_text("📍 *موقع المعهد الصناعي الثانوي ببريدة:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *حساب المعهد في موقع X:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 حساب منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📄 الخطط التدريبية": return await update.message.reply_text("📄 *اختر الفصل لمعرفة المقررات:*", reply_markup=get_plans_menu(), parse_mode='Markdown')

    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'): return await update.message.reply_text("⚠️ قاعدة البيانات فارغة.")

            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                completed_interrogations = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                subject_to_interrogate = None
                has_deprivation = False
                
                m = f"🎓 *السجل الأكاديمي للغياب*\n{SEP}\n👤 *المتدرب:* {stu_nam}\n🔢 *الرقم التدريبي:* {clean_text}\n{SEP}\n"
                for _, r in res.iterrows():
                    c_name_text = str(r.get('c_nam', 'غير معروف')).strip()
                    raw_val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    if raw_val == 'nan' or raw_val == '': raw_val = '0'
                    if raw_val == 'ح' or 'حرمان' in raw_val:
                        display_val = "*حرمان (ح)* 🔴"
                        has_deprivation = True
                    elif raw_val == 'ط' or 'طي' in raw_val:
                        display_val = "*طي قيد (ط)* ⚫"
                        has_deprivation = True
                    else:
                        try:
                            val = float(raw_val)
                            if val >= 20: icon, has_deprivation = "🔴 حرمان", True
                            elif val >= 15:
                                icon = "⚠️ إنذار"
                                if c_name_text not in completed_interrogations: subject_to_interrogate = c_name_text
                            else: icon = "🟢 منتظم"
                            display_val = f"*{val}%* {icon}"
                        except: display_val = f"*{raw_val}* ⚠️"
                    m += f"📖 *{c_name_text}*\n▫️ النتيجة: {display_val}\n\n"

                await update.message.reply_text(m, parse_mode='Markdown')

                if subject_to_interrogate:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': subject_to_interrogate}
                    warning_msg = f"⚠️ *تنبيه إداري عاجل!*\nالغياب في مقرر: *{subject_to_interrogate}* وصل لمرحلة الخطر.\n🛑 *النظام مغلق حتى تُكمل الإقرار!*"
                    return await update.message.reply_text(warning_msg, parse_mode='Markdown', reply_markup=get_pledge_step1_menu())
            else: await update.message.reply_text("❌ الرقم التدريبي غير مسجل أو لا توجد غيابات.")
        except Exception as e: pass
        return

    if text == "❓ الأسئلة الشائعة": return await update.message.reply_text("🏛️ *اللوائح والأنظمة التدريبية...*", parse_mode='Markdown')
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]: return await update.message.reply_text(f"{load_json('plans.json').get(text, 'جاري التحديث')}", parse_mode='Markdown')
    if text == "💡 نصيحة تقنية": return await update.message.reply_text(random.choice(TECH_TIPS))
    if text == "🕹️ قسم الألعاب والإضافات": return await update.message.reply_text("🕹️ *قسم الترفيه والإضافات:*", reply_markup=get_games_menu(), parse_mode='Markdown')
        
    await update.message.reply_text("⚠️ الرجاء اختيار خدمة من الأسفل 👇", reply_markup=get_main_menu())

# --- 🌟 محرك رفع الملفات 🌟 ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id, {})
    
    # 🔴 معالجة ملفات رايات لـ OpenClaw (الجديد) 🔴
    if state.get('flow') == 'openclaw':
        if update.message.document and update.message.document.file_name.endswith('.csv'):
            status_msg = await update.message.reply_text("⏳ جاري تحميل البيانات وإرسالها لـ OpenClaw...")
            try:
                file = await context.bot.get_file(update.message.document.file_id)
                in_memory = io.BytesIO()
                await file.download_to_memory(in_memory)
                csv_text = in_memory.getvalue().decode('utf-8')
                
                payload = {"message": "حفظ_بيانات_رايات\n" + csv_text}
                response = requests.post(OPENCLAW_URL, json=payload, timeout=60)
                await status_msg.edit_text(response.json().get("response", "تم استلام الرد."), parse_mode='Markdown')
            except Exception as e: await status_msg.edit_text(f"⚠️ خطأ: {str(e)}")
        return

    # 🔵 توجيه ملفات الإدارة (الإكسل والتقارير) لملف الإدارة الخارجي 🔵
    if user_id == ADMIN_ID and update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(('.xlsx', '.xls', '.csv')):
            await process_admin_excel(update, context, db) # 👈 يتم استدعاؤه من admin_features.py
            return

    # 🔵 الختم الآلي للأعذار 🔵
    if update.message.photo or update.message.document:
        caption_text = update.message.caption
        stu_id = ''.join(filter(str.isdigit, str(caption_text)))
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض: وصف غير مكتمل!*\nيجب كتابة *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
            
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري الختم الآلي والإرسال...")
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if update.message.photo and HAS_PIL:
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                in_memory_img = io.BytesIO()
                await file.download_to_memory(in_memory_img)
                in_memory_img.seek(0)
                
                img = Image.open(in_memory_img)
                txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
                ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id} | DATE: {timestamp}", fill="white")
                txt_img = txt_img.resize((img.size[0], int(img.size[0] * 50 / 1000)))
                img.paste(txt_img, (0, img.size[1] - txt_img.height)) 
                
                output = io.BytesIO()
                img.save(output, format='JPEG')
                output.seek(0)
                await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 *عذر مختوم:*\n{caption_text}\n⏱️ {timestamp}", parse_mode='Markdown')
            else: await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 *عذر مرفق:*\n{caption_text}\n{timestamp}", parse_mode='Markdown')
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الختم والإرسال للإدارة بنجاح.*", parse_mode='Markdown')
        except Exception as e: await status_msg.edit_text(f"⚠️ خطأ فني مباشر من السيرفر:\n`{str(e)}`", parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ans_"):
        try:
            actual_question = QUESTIONS[int(query.data.split("_")[1])]
            m = "🎉 *إجابة صحيحة!*" if int(query.data.split("_")[2]) == actual_question["answer"] else f"❌ *خاطئة!*"
            await query.edit_message_text(f"❓ *تحدي الأسبوع:*\n{actual_question['q']}\n{SEP}\n{m}", parse_mode='Markdown')
        except: pass

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
    Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    # 🔴 استدعاء الأوامر الإدارية من الملف الخارجي 🔴
    app.add_handler(CommandHandler("admin", admin_command)) 
    app.add_handler(CommandHandler("db", db_status_command)) 
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("report", report_command))
    
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("start", start))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 تشغيل النظام (النسخة الاحترافية المقسمة)...")
    app.run_polling()

if __name__ == '__main__': 
    main()
