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
from pymongo import MongoClient

# 🔴 استدعاء الملفات المنفصلة 🔴
from admin_features import ADMIN_ID, admin_command, db_status_command, backup_command, broadcast_command, report_command, process_admin_excel
from menus import get_main_menu, get_cancel_menu, get_back_menu, get_plans_menu, get_games_menu, get_pledge_step1_menu
from bot_settings import *
from student_excuses import process_pledge_step, process_excuse_document # 👈 المحرك الجديد للأعذار

try:
    from config.tips import TECH_TIPS
except ImportError:
    TECH_TIPS = ["💡 نصيحة تقنية: احرص دائماً على أخذ نسخة احتياطية لملفاتك."]

# 🔴 استدعاء الخدمات الإضافية 🔴
from extra_features import process_extra_features

# --- الاتصال بقاعدة البيانات ---
db = None
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client["computer_dept_db"] 
        print("✅ تم الاتصال بقاعدة البيانات بنجاح!")
except Exception as e: print(f"❌ خطأ بقاعدة البيانات: {e}")

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

def auto_reset_scores():
    while True:
        try:
            now = datetime.now()
            if now.weekday() == 6: 
                s = load_json(STATS_FILE)
                if s.get("last_reset_date") != now.strftime("%Y-%m-%d"):
                    save_json(SCORES_FILE, {}) 
                    s["last_reset_date"] = now.strftime("%Y-%m-%d") 
                    save_json(STATS_FILE, s)
        except: pass
        time.sleep(3600)

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
    
    welcome = f"أهلاً بك يا {first_name} في المساعد الذكي لقسم الحاسب الآلي 💻✨\n{SEP}\n"
    try:
        if db is not None:
            ex_user = db["trainees"].find_one({"telegram_id": user_id})
            if not ex_user:
                db["trainees"].insert_one({"telegram_id": user_id, "name": first_name, "role": "student", "pledges_count": 0, "join_date": datetime.now()})
            else: welcome = f"أهلاً بعودتك يا {first_name}! (سجلك يحتوي على {ex_user.get('pledges_count', 0)} تعهد).\n{SEP}\n"
    except: pass

    welcome += "أنا نظامك الرقمي المتكامل. 👇 الرجاء اختيار الخدمة المطلوبة:"
    try: await update.message.reply_photo(photo=open('IMG_1058.jpeg', 'rb'), caption=welcome, reply_markup=get_main_menu())
    except: await update.message.reply_text(welcome, reply_markup=get_main_menu())

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    clean_text = text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')).strip()
    
        # توجيه الخدمات الإضافية للملف المختص
    if text in ["📅 التقويم التدريبي", "🎮 تحدي الأسبوع", "🏆 بطل الأسبوع", "🌐 أخبار التقنية"]:
        return await process_extra_features(update, text)

    # داخل دالة handle_logic في main.py

    if user_id == ADMIN_ID:
        # زر الكشف الجديد
        if "الحالات الحرجة" in text:
            return await critical_cases_report(update, context)
            
        # زر التعميم
        if text == "إرسال تعميم 📢":
            user_states[user_id] = {'flow': 'broadcast_msg'}
            return await update.message.reply_text("📢 *مرحباً سعادة رئيس القسم..*\nاكتب الآن نص التعميم الذي تريد إرساله لجميع المتدربين:", parse_mode='Markdown', reply_markup=get_cancel_menu())

    # معالجة حالة إرسال التعميم
    if user_id in user_states and user_states[user_id].get('flow') == 'broadcast_msg':
        if text == "❌ إلغاء العملية":
            del user_states[user_id]
            return await update.message.reply_text("تم إلغاء التعميم.", reply_markup=get_main_menu())
            
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

    
    if user_id == ADMIN_ID:
        if "حالة قاعدة البيانات" in text: return await db_status_command(update, context)
        if "سحب نسخة احتياطية" in text: return await backup_command(update, context)
        if "تقرير سير العملية" in text: return await report_command(update, context)
        if text == "🦞 مساعد OpenClaw":
            user_states[user_id] = {'flow': 'openclaw'}
            return await update.message.reply_text("🦞 **وحدة OpenClaw:**\nأرسل ملف CSV للتحليل.", parse_mode='Markdown', reply_markup=get_back_menu())

    if user_id in user_states:
        state = user_states[user_id]
        if text in ["❌ إلغاء العملية", "🔙 الرجوع للقائمة الرئيسية"]:
            del user_states[user_id]
            return await update.message.reply_text("تم العودة للقائمة الرئيسية 🏠", reply_markup=get_main_menu())

        if state['flow'] == 'openclaw':
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            try:
                res = requests.post(OPENCLAW_URL, json={"message": text}, timeout=60)
                await update.message.reply_text(res.json().get("response", "تم."), parse_mode='Markdown')
            except Exception as e: await update.message.reply_text(f"⚠️ خطأ: {str(e)}")
            return

        # 🔴 توجيه الإقرارات للمحرك المنفصل 🔴
        if state['flow'] == 'pledge':
            return await process_pledge_step(update, context, user_id, text, state, user_states)

        if state['flow'] == 'feedback':
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"💡 *شكوى/مقترح:*\nالمرسل: {update.effective_user.first_name}\nالنص: {text}", parse_mode='Markdown')
                del user_states[user_id]; return await update.message.reply_text("✅ تم إرسال رسالتك للإدارة.", reply_markup=get_main_menu())
            except: del user_states[user_id]; return await update.message.reply_text("⚠️ حدث خطأ.", reply_markup=get_main_menu())

        if state['flow'] == 'ai':
            if not ai_model: return await update.message.reply_text("⚠️ المعلم غير متصل حالياً.", reply_markup=get_main_menu())
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            update_stat("ai_questions") 
            try:
                res = await ai_model.generate_content_async(f"{AI_KNOWLEDGE}\nسؤال: {text}")
                return await update.message.reply_text(f"📝 رد المعلم الذكي:\n\n{res.text}", reply_markup=get_back_menu())
            except: return await update.message.reply_text("⚠️ خطأ تقني.", reply_markup=get_back_menu())

        if state['flow'] == 'excuse': return await update.message.reply_text("⚠️ الرجاء إرسال (صورة العذر) مع كتابة رقمك.", reply_markup=get_cancel_menu())

    if text == "📝 رفع الغياب والأعذار": 
        user_states[user_id] = {'flow': 'excuse'}
        return await update.message.reply_text("📝 الرجاء إرفاق (صورة العذر) مع كتابة رقمك بالوصف.", reply_markup=get_cancel_menu())
    if text == "📬 الاقتراحات والشكاوى":
        user_states[user_id] = {'flow': 'feedback'}
        return await update.message.reply_text("📬 اكتب رسالتك بالتفصيل...", reply_markup=get_cancel_menu())
    if text == "🤖 المعلم الذكي":
        user_states[user_id] = {'flow': 'ai'}
        return await update.message.reply_text("🤖 أنا جاهز، اكتب سؤالك...", reply_markup=get_back_menu())
    if text == "📊 استعلام الغياب": return await update.message.reply_text("🔎 أرسل رقمك التدريبي (أرقام فقط)...")
    if text == "📚 الحقائب التدريبية": return await update.message.reply_text("📚 *رابط المقررات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 المستودع", url=DRIVE_LINK)]]), parse_mode='Markdown')
    if text == "🔗 المنصات الإلكترونية": return await update.message.reply_text("🌐 *المنصات:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رايات", url="https://rayat.tvtc.gov.sa")], [InlineKeyboardButton("تقني", url="https://tvtclms.edu.sa")]]), parse_mode='Markdown')
    if text == "📍 موقع القسم": return await update.message.reply_text("📍 *الموقع:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗺️ خرائط جوجل", url="http://googleusercontent.com/maps.google.com/3")]]), parse_mode='Markdown')
    if text == "📰 أخبار القسم والمعهد": return await update.message.reply_text("📰 *حساب المعهد:*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 منصة X", url=TVTC_X_LINK)]]), parse_mode='Markdown')
    if text == "📄 الخطط التدريبية": return await update.message.reply_text("📄 *اختر الفصل:*", reply_markup=get_plans_menu(), parse_mode='Markdown')
    if clean_text.isdigit() and len(clean_text) > 4: 
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            if not os.path.exists('data.xlsx'): return await update.message.reply_text("⚠️ القاعدة فارغة.")
            df = pd.read_excel('data.xlsx', dtype=str)
            df['stu_num'] = df['stu_num'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True) 
            res = df[df['stu_num'] == clean_text]
            if not res.empty:
                stu_nam = res.iloc[0]['stu_nam']
                m = f"🎓 *السجل الأكاديمي*\n👤 *المتدرب:* {stu_nam}\n🔢 *الرقم:* {clean_text}\n{SEP}\n"
                sj_interrogate = None
                comp = load_json(INTERROGATIONS_FILE).get(clean_text, [])
                for _, r in res.iterrows():
                    c_name = str(r.get('c_nam', '')).strip()
                    val = str(r.get('parsnt', '0')).replace('%', '').strip()
                    if val in ['ح', 'ط'] or 'حرمان' in val: d_val = f"*{val}* 🔴"
                    else:
                        try:
                            v = float(val)
                            if v >= 20: d_val = f"*{v}%* 🔴 حرمان"
                            elif v >= 15: 
                                d_val = f"*{v}%* ⚠️ إنذار"
                                if c_name not in comp: sj_interrogate = c_name
                            else: d_val = f"*{v}%* 🟢"
                        except: d_val = f"*{val}* ⚠️"
                    m += f"📖 *{c_name}*\n▫️ {d_val}\n\n"
                await update.message.reply_text(m, parse_mode='Markdown')
                if sj_interrogate:
                    user_states[user_id] = {'flow': 'pledge', 'step': 1, 'stu_num': clean_text, 'stu_nam': stu_nam, 'subject': sj_interrogate}
                    return await update.message.reply_text(f"⚠️ *تنبيه!*\nالغياب بمقرر: *{sj_interrogate}* وصل لمرحلة الخطر.\n🛑 *النظام مغلق حتى تُكمل الإقرار!*", parse_mode='Markdown', reply_markup=get_pledge_step1_menu())
            else: await update.message.reply_text("❌ الرقم غير مسجل.")
        except: pass
        return
    if text == "❓ الأسئلة الشائعة": return await update.message.reply_text("🏛️ *اللوائح والأنظمة التدريبية...*", parse_mode='Markdown')
    if text in ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني", "3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع", "5️⃣ الفصل الخامس", "6️⃣ الفصل السادس", "🖥️ برامج فصلية"]: return await update.message.reply_text(f"{load_json('plans.json').get(text, 'جاري التحديث')}", parse_mode='Markdown')
    if text == "💡 نصيحة تقنية": return await update.message.reply_text(random.choice(TECH_TIPS))
    if text == "🕹️ قسم الألعاب والإضافات": return await update.message.reply_text("🕹️ *القسم الترفيهي:*", reply_markup=get_games_menu(), parse_mode='Markdown')
    await update.message.reply_text("⚠️ الرجاء اختيار خدمة 👇", reply_markup=get_main_menu())

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id, {})
    
    if state.get('flow') == 'openclaw' and update.message.document and update.message.document.file_name.endswith('.csv'):
        status_msg = await update.message.reply_text("⏳ جاري الإرسال لـ OpenClaw...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            in_mem = io.BytesIO(); await file.download_to_memory(in_mem)
            res = requests.post(OPENCLAW_URL, json={"message": "حفظ_بيانات_رايات\n" + in_mem.getvalue().decode('utf-8')}, timeout=60)
            await status_msg.edit_text(res.json().get("response", "تم."), parse_mode='Markdown')
        except Exception as e: await status_msg.edit_text(f"⚠️ خطأ: {e}")
        return

    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.xls', '.csv')):
        return await process_admin_excel(update, context, db)

    # 🔴 توجيه صور ومستندات الطلاب (الأعذار) للمحرك المنفصل 🔴
    if update.message.photo or update.message.document:
        return await process_excuse_document(update, context, user_states)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

def main():
    Thread(target=auto_reset_scores, daemon=True).start()
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
    print("🚀 تشغيل النظام (النسخة المعمارية النظيفة)...")
    app.run_polling()

if __name__ == '__main__': main()
