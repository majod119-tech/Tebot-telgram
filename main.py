import os, io, time, random, urllib.request, json, requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd
import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# 🔴 استدعاء قاعدة البيانات ومستثنيات الأخطاء 🔴
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# 🔴 استدعاء الملفات المنفصلة 🔴
from admin_features import ADMIN_ID, admin_command, db_status_command, backup_command, broadcast_command, report_command, process_admin_excel, critical_cases_report
from menus import get_main_menu, get_cancel_menu, get_back_menu, get_plans_menu, get_openclaw_menu
from bot_settings import *

# 🌟 استدعاء مصنع الإكسل 🌟
from excel_manager import convert_plan_file

# استدعاء محرك OpenClaw 
try:
    from ai_service import ask_openclaw_api
except ImportError:
    def ask_openclaw_api(text): return "⚠️ محرك OpenClaw غير متصل حالياً."

try:
    from config.tips import TECH_TIPS
except ImportError:
    TECH_TIPS = ["💡 نصيحة تقنية: احرص دائماً على أخذ نسخة احتياطية لملفاتك."]

# --- الاتصال بقاعدة البيانات (محصن ضد أخطاء Timeout و Kube) ---
db = None
client = None

if MONGO_URI:
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,   # تقليل مهلة البحث عن السيرفر لـ 5 ثوان لتفادي تعليق البوت
            connectTimeoutMS=10000,          # مهلة الاتصال الأولية 10 ثوان
            socketTimeoutMS=20000,           # مهلة نقل البيانات 20 ثانية
            maxPoolSize=50,                  # إدارة الاتصالات لتفادي استهلاك موارد الـ Kube Node
            minPoolSize=5,
            retryWrites=True,                # إعادة محاولة الكتابة تلقائياً عند تذبذب الشبكة
            retryReads=True                  # إعادة محاولة القراءة تلقائياً
        )
        # اختبار الاتصال الفعلي بالخادم
        client.admin.command('ping')
        db = client["computer_dept_db"] 
        print("✅ تم الاتصال بقاعدة البيانات بنجاح واستقرار!")
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"⚠️ تعذر الاتصال بـ MongoDB: {e}")
        print("💡 جاري تشغيل البوت بنظام ذاكرة الجلسات لحين عودة الاتصال...")
    except Exception as e:
        print(f"❌ خطأ غير متوقع في قاعدة البيانات: {e}")

# --- إعداد المعلم الذكي ---
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

def update_stat(cat):
    s = load_json(STATS_FILE)
    s[cat] = s.get(cat, 0) + 1
    save_json(STATS_FILE, s)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot Server Online.")

def run_web_server():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), SimpleHandler).serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    first_name = update.effective_user.first_name

    s = load_json(STATS_FILE)
    if user_id not in s.get("users_list", []): 
        s.setdefault("users_list", []).append(user_id)
        save_json(STATS_FILE, s)
    
    if user_id in user_states: del user_states[user_id]
    context.user_data.clear() # تنظيف أي عمليات معلقة
    
    welcome = f"أهلاً بك يا {first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
    try:
        if db is not None:
            ex_user = db["trainees"].find_one({"telegram_id": user_id})
            if not ex_user:
                db["trainees"].insert_one({"telegram_id": user_id, "name": first_name, "role": "student", "join_date": datetime.now()})
            else: welcome = f"أهلاً بعودتك يا {first_name}!\n{SEP}\n"
    except: pass

    welcome += "أنا نظامك الرقمي المتكامل. 👇 الرجاء اختيار الخدمة المطلوبة:"
    try: await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    # --- الإلغاء العام ---
    if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
        if user_id in user_states: del user_states[user_id]
        context.user_data.clear() # مسح حالة انتظار الملفات
        return await update.message.reply_text("تم العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())

    # 🔴 --- نظام الغرفة المعزولة (OpenClaw) --- 🔴
    if user_id in user_states and user_states[user_id].get('flow') == 'openclaw_mode':
        if text == "❌ إنهاء محادثة الذكاء الاصطناعي":
            del user_states[user_id]
            from menus import get_admin_menu
            return await update.message.reply_text("✅ *تم إغلاق الغرفة المعزولة.*\nعدنا للوحة تحكم القسم.", parse_mode='Markdown', reply_markup=get_admin_menu())
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        ai_reply = ask_openclaw_api(text) 
        return await update.message.reply_text(f"🦞 *OpenClaw:*\n{ai_reply}", parse_mode='Markdown', reply_markup=get_openclaw_menu())

    # 🔴 --- أوامر الإدارة المتقدمة --- 🔴
    if user_id == ADMIN_ID:
        if "الحالات الحرجة" in text: return await critical_cases_report(update, context)
        if "حالة قاعدة البيانات" in text: return await db_status_command(update, context)
        if "سحب نسخة احتياطية" in text: return await backup_command(update, context)
        if "تقرير سير العملية" in text: return await report_command(update, context)
        
        # 🌟 زر تحويل الخطط التدريبية 🌟
        if text == "🔄 تحويل الخطط للقالب الجديد":
            context.user_data['waiting_for_plan'] = True # تفعيل حالة انتظار ملف الخطة
            return await update.message.reply_text("✅ ممتاز! أرسل لي الآن ملف الخطة (القديم) بصيغة Excel ليتم تحويله للقالب المعتمد.", reply_markup=get_cancel_menu())
        
        if text == "إرسال تعميم 📢":
            user_states[user_id] = {'flow': 'broadcast_msg'}
            return await update.message.reply_text("📢 *مرحباً سعادة رئيس القسم..*\nاكتب الآن نص التعميم الذي تريد إرساله لجميع المتدربين:", parse_mode='Markdown', reply_markup=get_cancel_menu())
            
        if text == "🦞 مساعد OpenClaw":
            user_states[user_id] = {'flow': 'openclaw_mode'}
            welcome_msg = "🦞 *مرحباً بك في غرفة OpenClaw المعزولة!*\n\nأنت الآن تتحدث معي مباشرة. لا توجد أوامر، فقط نقاش حر.\nاسألني أو تناقش معي، وللخروج اضغط على زر الإنهاء بالأسفل 👇"
            return await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=get_openclaw_menu())

    # 🔴 --- معالجة الحالات المستمرة --- 🔴
    if user_id in user_states:
        state = user_states[user_id]

        if state.get('flow') == 'broadcast_msg' and user_id == ADMIN_ID:
            users = load_json(STATS_FILE).get("users_list", [])
            await update.message.reply_text(f"🚀 جاري إرسال التعميم لـ {len(users)} متدرب...")
            count = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u, text=f"📢 *تعميم إداري من رئيس القسم:*\n{SEP}\n{text}", parse_mode='Markdown')
                    count += 1
                except: pass
            del user_states[user_id]
            return await update.message.reply_text(f"✅ تم إرسال التعميم بنجاح لـ {count} متدرب.", reply_markup=get_main_menu())

        if state.get('flow') == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل حالياً.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                res = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم الذكي:\n\n{res.text}", reply_markup=get_back_menu())
            except: return await update.message.reply_text("⚠️ خطأ تقني.", reply_markup=get_back_menu())

    # 🔴 --- الأزرار الأساسية المخففة --- 🔴
    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        return await update.message.reply_text("🤖 أنا جاهز، اكتب سؤالك...", reply_markup=get_back_menu())
    if text == "📚 الحقائب التدريبية": return await update.message.reply_text("📚 *رابط المقررات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 المستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🔗 المنصات الإلكترونية": return await update.message.reply_text("🌐 *المنصات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *حساب المعهد:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📄 الخطط التدريبية": return await update.message.reply_text("📄 *اختر الفصل:*", reply_markup=get_plans_menu(), parse_mode='Markdown')
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]: return await update.message.reply_text(f"{load_json('plans.json').get(text, 'جاري التحديث')}", parse_mode='Markdown')
    if text == "💡 نصيحة تقنية": return await update.message.reply_text(random.choice(TECH_TIPS))

    await update.message.reply_text("⚠️ الرجاء اختيار خدمة 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id, {})
    
    # استقبال ملف CSV لـ OpenClaw داخل الغرفة المعزولة
    if state.get('flow') == 'openclaw_mode' and update.message.document and update.message.document.file_name.endswith('.csv'):
        status_msg = await update.message.reply_text("⏳ جاري تحليل ملف رايات عبر الذكاء الاصطناعي...")
        await status_msg.edit_text("✅ استلمت الملف وسأقوم بتحليله.", parse_mode='Markdown')
        return

    # 🌟 توجيه ملف الخطة القديم لمصنع الإكسل إذا كان المدير ينتظر 🌟
    if context.user_data.get('waiting_for_plan') and update.message.document:
        return await convert_plan_file(update, context)

    # استقبال ملفات تحديث بيانات الإدارة
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.xls', '.csv')):
        return await process_admin_excel(update, context, db)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("db", db_status_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 تشغيل النظام (النسخة الخفيفة والسريعة)...")
    app.run_polling()

if __name__ == '__main__': main()
