import os
import pandas as pd
import json
import random
import time
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. سيرفر الويب ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running perfectly!")
    def log_message(self, format, *args): pass 

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. الإعدادات ---
TOKEN = os.environ.get("TOKEN") 
GROUP_ID = "-5193577198"
TELEGRAM_CONTACT_LINK = "https://t.me/majod119"
DRIVE_LINK = "https://ethaqplus.tvtc.gov.sa/index.php/s/koN36W6iSHM8bnL"

# --- 🌟 إعداد الذكاء الاصطناعي (بنظام الاكتشاف التلقائي) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ai_model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        selected_model_name = None
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                selected_model_name = m.name.replace('models/', '') 
                if 'flash' in selected_model_name.lower():
                    break
                    
        if selected_model_name:
            ai_model = genai.GenerativeModel(selected_model_name)
            print(f"✅ تم تفعيل المعلم الذكي بنجاح على موديل: {selected_model_name}")
        else:
            ai_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini Init Error: {e}")
        ai_model = genai.GenerativeModel('gemini-1.5-flash')

ai_sessions = {}

# --- 3. بنك الأسئلة والنقاط ---
QUESTIONS = [
    {
        "q": "ما هو عنوان الـ IP الذي يُعرف بـ (Localhost) ويستخدم لاختبار كرت الشبكة؟",
        "options": ["192.168.1.1", "127.0.0.1", "8.8.8.8", "255.255.255.0"],
        "answer": 1 
    },
    {
        "q": "أي من المكونات التالية يعتبر 'العقل المدبر' للحاسب الآلي؟",
        "options": ["القرص الصلب (HDD)", "الذاكرة العشوائية (RAM)", "المعالج (CPU)", "اللوحة الأم"],
        "answer": 2
    },
    {
        "q": "في نظام لينكس (Linux)، ما هو الأمر المستخدم لعرض قائمة الملفات في المجلد الحالي؟",
        "options": ["cd", "ls", "pwd", "mkdir"],
        "answer": 1
    },
    {
        "q": "أي من أنواع الكيابل التالية يوفر أعلى سرعة لنقل البيانات؟",
        "options": ["الكيابل المحورية (Coaxial)", "الألياف الضوئية (Fiber Optic)", "المزدوجة المجدولة (UTP)", "خطوط الهاتف"],
        "answer": 1
    }
]

SCORES_FILE = "scores.json"
TIME_LIMIT = 15 
active_challenges = {} 

def load_scores():
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f)

# --- 4. تصميم القوائم (الواجهة الجديدة والمريحة) ---
def get_main_menu():
    keyboard = [
        # السطر الأول: الذكاء الاصطناعي
        ["🤖 المعلم الذكي (اسألني)"], 
        # السطر الثاني: المواد الأكاديمية
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        # السطر الثالث: شؤون المتدربين
        ["📊 استعلام الغياب", "📝 رفع الغياب والأعذار"],
        # السطر الرابع: الترفيه والتنافس
        ["🎮 تحدي الأسبوع", "🏆 بطل الأسبوع"], 
        # السطر الخامس: أدوات المعهد
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        # السطر السادس: معلومات عامة
        ["📰 أخبار القسم والمعهد", "📍 موقع القسم"],
        # السطر السابع: الدعم والمساندة
        ["👨‍🏫 تواصل مع رئيس القسم"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_plans_menu():
    keyboard = [
        ["1️⃣ الفصل الأول", "2️⃣ الفصل الثاني"],
        ["3️⃣ الفصل الثالث", "4️⃣ الفصل الرابع"],
        ["5️⃣ الفصل الخامس", "6️⃣ الفصل السادس"],
        ["🖥️ برامج فصلية (إدخال بيانات)"],
        ["🔙 الرجوع للقائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_menu():
    return ReplyKeyboardMarkup([["🔙 الرجوع للقائمة الرئيسية"]], resize_keyboard=True)

# --- 5. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_sessions[str(update.effective_user.id)] = False
    await update.message.reply_text(
        f"أهلاً بك {update.effective_user.first_name} في بوت قسم الحاسب 💻✨\nاختر من القائمة أدناه 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    known_commands = [
        "🔙 الرجوع للقائمة الرئيسية", "📊 استعلام الغياب", "📍 موقع القسم", 
        "📚 الحقائب التدريبية", "📄 الخطط التدريبية", "🔗 منصة تقني ورايات", 
        "📅 التقويم التدريبي", "📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم",
        "🎮 تحدي الأسبوع", "🏆 بطل الأسبوع", "📰 أخبار القسم والمعهد", "🤖 المعلم الذكي (اسألني)"
    ]

    if text in known_commands and text != "🤖 المعلم الذكي (اسألني)":
        ai_sessions[user_id] = False

    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    # --- 🤖 نظام المعلم الذكي ---
    if text == "🤖 المعلم الذكي (اسألني)":
        ai_sessions[user_id] = True
        welcome_ai = (
            "🤖 **أهلاً بك في خدمة المعلم الذكي!**\n\n"
            "أنا هنا لمساعدتك. اسألني عن أي موضوع في الشبكات، البرمجة، مكونات الحاسب، قواعد البيانات، أو صيانة الأجهزة.\n"
            "💬 **اكتب سؤالك التقني الآن...**\n\n"
            "*(للخروج من هذه الخدمة، اضغط على زر الرجوع للقائمة الرئيسية)*"
        )
        await update.message.reply_text(welcome_ai, reply_markup=get_back_menu(), parse_mode='Markdown')
        return

    if ai_sessions.get(user_id) == True:
        if not ai_model:
            await update.message.reply_text("⚠️ المعلم الذكي غير متصل حالياً. تأكد من إعدادات المفتاح في السيرفر.", reply_markup=get_back_menu())
            return
            
        status_msg = await update.message.reply_text("⏳ أقرأ سؤالك وأبحث عن أفضل إجابة...")
        try:
            prompt = (
                f"أنت معلم حاسب وتقنية معلومات في معهد صناعي ثانوي بالسعودية. "
                f"أجب على سؤال المتدرب التالي بأسلوب مبسط، عملي ومشجع. "
                f"السؤال: {text}"
            )
            response = await ai_model.generate_content_async(prompt)
            await status_msg.delete()
            try:
                await update.message.reply_text(response.text, parse_mode='Markdown', reply_markup=get_back_menu())
            except:
                await update.message.reply_text(response.text, reply_markup=get_back_menu())
        except Exception as e:
            await status_msg.delete()
            print(f"Gemini API Error: {e}")
            error_msg = f"⚠️ واجهت مشكلة فنية!\nالسبب: `{str(e)}`\n\nسنقوم بمعالجة هذا الخلل قريباً."
            await update.message.reply_text(error_msg, parse_mode='Markdown', reply_markup=get_back_menu())
        return

    # --- باقي الخدمات ---
    if text == "🎮 تحدي الأسبوع":
        scores = load_scores()
        user_data = scores.get(user_id, {"answered": []})
        answered_questions = user_data.get("answered", [])
        available_questions = [i for i in range(len(QUESTIONS)) if i not in answered_questions]
        
        if not available_questions:
            await update.message.reply_text("🎉 لقد أنهيت جميع التحديات المتاحة حالياً! بانتظار تحديث الأسئلة 💪.", reply_markup=get_back_menu())
            return
            
        q_idx = random.choice(available_questions)
        question_data = QUESTIONS[q_idx]
        
        keyboard = []
        for i, opt in enumerate(question_data["options"]):
            keyboard.append([InlineKeyboardButton(opt, callback_data=f"ans_{q_idx}_{i}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        active_challenges[user_id] = time.time()
        
        challenge_msg = f"❓ **تحدي الأسبوع:**\n\n⚠️ **تنبيه:** أمامك {TIME_LIMIT} ثانية فقط للإجابة!\n\n🔸 {question_data['q']}"
        await update.message.reply_text(challenge_msg, reply_markup=reply_markup, parse_mode='Markdown')
        return

    if text == "🏆 بطل الأسبوع":
        scores = load_scores()
        valid_scores = {uid: data for uid, data in scores.items() if data.get("score", 0) > 0}
        if not valid_scores:
            await update.message.reply_text("📉 لم يحصل أي متدرب على نقاط حتى الآن. شارك لتكون الأول!", reply_markup=get_back_menu())
            return
            
        sorted_scores = sorted(valid_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        top_student_id, top_student_data = sorted_scores[0]
        
        leaderboard_msg = f"🏆 **بطل قسم الحاسب لهذا الأسبوع:**\n\n🥇 **{top_student_data['name']}**\n🌟 الرصيد: {top_student_data['score']} نقطة\n\n"
        if len(sorted_scores) > 1:
            leaderboard_msg += "🎖️ **بقية لوحة الشرف:**\n"
            for i, (uid, data) in enumerate(sorted_scores[1:5], start=2): 
                leaderboard_msg += f"{i}. {data['name']} ({data['score']} نقطة)\n"
            
        await update.message.reply_text(leaderboard_msg, parse_mode='Markdown', reply_markup=get_back_menu())
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 **الخطط التدريبية لدبلوم الحاسب الآلي:**\nاختر الفصل التدريبي 👇", reply_markup=get_plans_menu(), parse_mode='Markdown')
        return

    if text == "📰 أخبار القسم والمعهد":
        news_msg = "📰 **أحدث إعلانات المعهد:**\n\n🔸 *الأسبوع 6 و 7 موعد اختبارات الفترة الأولى.*\n🔗 [حساب المعهد على X](https://x.com/tvtc_m_buraidah?s=21)"
        await update.message.reply_text(news_msg, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    term_plans = {
        "1️⃣ الفصل الأول": "📚 **مقررات الفصل التدريبي الأول:**\n🔹 ثقافة إسلامية 1\n🔹 لغة إنجليزية 1\n🔹 رياضيات 1\n🔹 فيزياء\n🔹 التربية البدنية 1\n🔹 لغة عربية 1\n🔹 أساسيات الحاسب الآلي\n🔹 مدخل إلى مهارات القرن 21\n🔹 السلامة والصحة المهنية",
        "2️⃣ الفصل الثاني": "📚 **مقررات الفصل التدريبي الثاني:**\n🔹 سلو مهني\n🔹 لغة عربية 2\n🔹 لغة إنجليزية 2\n🔹 رياضيات 2\n🔹 التربية البدنية 2\n🔹 ثقافة إسلامية 2\n🔹 ورش تأسيسية\n🔹 تطبيقات الحاسب الآلي\n🔹 مهارات التواصل والتعاون\n🔹 التفكير الناقد والإبداعي",
        "3️⃣ الفصل الثالث": "📚 **مقررات الفصل التدريبي الثالث:**\n🔹 ثقافة إسلامية 3\n🔹 الرسم الهندسي\n🔹 بحث ومصادر المعلومات\n🔹 رياضيات 3\n🔹 لغة إنجليزية 3\n🔹 أجهزة وقياس\n🔹 أساسيات الكهرباء\n🔹 أساسيات الإلكترونيات\n🔹 تطبيقات مفتوحة المصدر",
        "4️⃣ الفصل الرابع": "📚 **مقررات الفصل التدريبي الرابع:**\n🔹 مقدمة في ريادة الأعمال\n🔹 تقنيات الانترنت\n🔹 مكونات الحاسب 1\n🔹 لغة برمجة 1\n🔹 أساسيات الشبكات\n🔹 رسم الشبكات بالحاسب\n🔹 أساسيات نظام لينكس\n🔹 أنشطة مهنية",
        "5️⃣ الفصل الخامس": "📚 **مقررات الفصل التدريبي الخامس:**\n🔹 مكونات الحاسب 2\n🔹 صيانة الأجهزة الكفية\n🔹 لغة برمجة 2\n🔹 تمديد الكيابل النحاسية\n🔹 شبكات الحاسب\n🔹 نظام تشغيل الشبكة 1\n🔹 مشاريع إنتاجية\n🔹 أنشطة مهنية 2",
        "6️⃣ الفصل السادس": "📚 **مقررات الفصل التدريبي السادس:**\n🔹 مبادئ قواعد البيانات\n🔹 طرفيات الحاسب\n🔹 مهارات صيانة الحاسب\n🔹 تمديد كيابل الألياف الضوئية\n🔹 نظام تشغيل الشبكة 2\n🔹 تدريب إنتاجي\n🔹 أنشطة مهنية 3",
        "🖥️ برامج فصلية (إدخال بيانات)": "📚 **البرامج القصيرة:**\n🔹 **برنامج إدخال البيانات ومعالجة النصوص**"
    }

    if text in term_plans:
        await update.message.reply_text(f"{term_plans[text]}\n\n🔗 **لتحميل الحقائب:**\n{DRIVE_LINK}", parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "🔗 منصة تقني ورايات":
        await update.message.reply_text("🌐 **روابط هامة:**\n🔹 تقني: https://tvtclms.edu.sa\n🔹 رايات: https://rayat.tvtc.gov.sa", reply_markup=get_back_menu(), disable_web_page_preview=True)
        return

    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 موقع القسم:\nhttp://maps.google.com/?q=Buraydah", reply_markup=get_back_menu())
        return
    
    if text == "📚 الحقائب التدريبية":
        await update.message.reply_text(f"📚 **المستودع:**\n{DRIVE_LINK}", reply_markup=get_back_menu(), disable_web_page_preview=True)
        return
    
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'): await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), reply_markup=get_back_menu())
        else: await update.message.reply_text("⚠️ ملف التقويم مفقود.", reply_markup=get_back_menu())
        return
    
    if text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text(f"👨‍🏫 تواصل مباشر:\n🔗 {TELEGRAM_CONTACT_LINK}", reply_markup=get_back_menu())
        return

    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل **رقمك التدريبي** الآن للبحث..", reply_markup=get_back_menu())
        return

    if text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **تعليمات:** أرسل صورة العذر واكتب رقمك التدريبي في الوصف.", reply_markup=get_back_menu())
        return

    if text.isdigit():
        status_msg = await update.message.reply_text("⏳ جاري البحث...")
        try:
            df = pd.read_excel('data.xlsx')
            df.columns = df.columns.astype(str).str.strip()
            result = df[df['stu_num'].astype(str).str.strip() == text]
            await status_msg.delete()
            
            if not result.empty:
                name = result.iloc[0]['stu_nam']
                msg = f"✅ <b>النتائج لـ:</b> <code>{name}</code>\n━━━━━━━━━━━━━━\n"
                max_absence = 0 
                for _, row in result.iterrows():
                    val = float(row['parsnt'])
                    if val > max_absence: max_absence = val 
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ تنبيه" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 {row['c_nam']}: %{val} {icon}\n"
                
                msg += "\n💡 <b>رسالة القسم:</b>\n"
                if max_absence == 0: msg += "🌟 أداء مثالي! القسم يفتخر بانتظامك والتزامك التام، استمر يا بطل."
                elif max_absence < 15: msg += "🟢 وضعك سليم ومنتظم، لكن احرص على عدم زيادة غيابك."
                elif max_absence < 20: msg += "⚠️ تنبيه هام! لقد اقتربت من حافة الحرمان، مستقبلك أهم."
                else: msg += "🔴 للأسف وصلت لنسبة الحرمان. نأمل مراجعة إدارة القسم فوراً."
                await update.message.reply_text(msg, parse_mode='HTML', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ الرقم غير مسجل لدينا.", reply_markup=get_back_menu())
        except:
            if 'status_msg' in locals(): await status_msg.delete()
            await update.message.reply_text("⚠️ خطأ في قراءة ملف `data.xlsx`.", reply_markup=get_back_menu())
        return

    await update.message.reply_text("⚠️ عذراً، لم أتعرف على طلبك. الرجاء استخدام الأزرار المتاحة 👇", reply_markup=get_main_menu())

# --- معالجة إجابات التحدي ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    
    data = query.data
    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name
    
    if data.startswith("ans_"):
        start_time = active_challenges.get(user_id)
        if not start_time:
            await query.edit_message_text("❌ انتهت صلاحية هذا التحدي أو أنك قمت بالإجابة مسبقاً.")
            return
            
        time_taken = time.time() - start_time
        del active_challenges[user_id] 
        
        parts = data.split("_")
        q_idx = int(parts[1])
        selected_ans = int(parts[2])
        question_data = QUESTIONS[q_idx]
        correct_ans = question_data["answer"]
        
        scores = load_scores()
        if user_id not in scores: scores[user_id] = {"name": user_name, "score": 0, "answered": []}
        if q_idx not in scores[user_id].get("answered", []): scores[user_id].setdefault("answered", []).append(q_idx)
            
        if time_taken > TIME_LIMIT:
            result_text = f"⏳ **انتهى الوقت!**\nاستغرقت {int(time_taken)} ثانية (الحد الأقصى {TIME_LIMIT} ثانية).\nمما يعني أنك بحثت عن الإجابة 😉.\n\nالإجابة الصحيحة كانت: {question_data['options'][correct_ans]}"
            save_scores(scores)
        else:
            if selected_ans == correct_ans:
                scores[user_id]["score"] += 10 
                save_scores(scores)
                result_text = f"🎉 **إجابة صحيحة يا {user_name}!**\nأجبت خلال {int(time_taken)} ثواني وكسبت 10 نقاط 🌟\nرصيدك الحالي: {scores[user_id]['score']} نقطة."
            else:
                save_scores(scores)
                result_text = f"❌ **إجابة خاطئة!**\nالإجابة الصحيحة هي: {question_data['options'][correct_ans]}\nحاول التعويض في التحدي القادم 💪"
            
        await query.edit_message_text(text=f"❓ **تحدي الأسبوع:**\n{question_data['q']}\n\n{result_text}", parse_mode='Markdown')

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ عذراً، يجب كتابة (رقمك التدريبي) في وصف الصورة قبل الإرسال.", reply_markup=get_back_menu())
        return
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد:\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للمسؤول.", reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text("⚠️ حدث خطأ. تأكد أن البوت مضاف كمشرف في مجموعة الأرشيف.", reply_markup=get_main_menu())

def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(CallbackQueryHandler(button_callback)) 
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 البوت يعمل الآن بالتصميم الجديد لقوائم العرض...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()