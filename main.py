import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

# --- 3. تصميم القوائم ---
def get_main_menu():
    keyboard = [
        ["📰 أخبار القسم والمعهد"], 
        ["📊 استعلام الغياب", "📍 موقع القسم"],
        ["📚 الحقائب التدريبية", "📄 الخطط التدريبية"],
        ["🔗 منصة تقني ورايات", "📅 التقويم التدريبي"],
        ["📝 رفع الغياب والأعذار", "👨‍🏫 تواصل مع رئيس القسم"]
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

# --- 4. المهام والمنطق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"أهلاً بك {update.effective_user.first_name} في بوت قسم الحاسب 💻✨\nاختر من القائمة أدناه 👇",
        reply_markup=get_main_menu()
    )

async def handle_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # --- أزرار التنقل ---
    if text == "🔙 الرجوع للقائمة الرئيسية":
        await update.message.reply_text("🏠 تم العودة للقائمة الرئيسية:", reply_markup=get_main_menu())
        return

    if text == "📄 الخطط التدريبية":
        await update.message.reply_text("📄 **الخطط التدريبية لدبلوم الحاسب الآلي:**\nاختر الفصل التدريبي المطلوب 👇", reply_markup=get_plans_menu(), parse_mode='Markdown')
        return

    # --- قسم الأخبار ---
    if text == "📰 أخبار القسم والمعهد":
        news_msg = (
            "📰 **أحدث إعلانات القسم والمعهد:**\n\n"
            "🔔 **إعلان هام:**\n"
            "🔸 *الأسبوع القادم (الأسبوع 6 و 7) سيكون موعداً لاختبارات الفترة الأولى. نتمنى لجميع المتدربين التوفيق والنجاح.*\n\n"
            "📱 **حساب المعهد الصناعي الثانوي ببريدة على منصة X:**\n"
            "🔗 [اضغط هنا لزيارة حساب المعهد](https://x.com/tvtc_m_buraidah?s=21)\n\n"
            "*(تنبيه: سيتم تحديث الأخبار هنا بشكل دوري)*"
        )
        await update.message.reply_text(news_msg, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    # --- الخطط الفرعية ---
    term_plans = {
        "1️⃣ الفصل الأول": "📚 **مقررات الفصل التدريبي الأول:**\n🔹 ثقافة إسلامية 1\n🔹 لغة إنجليزية 1\n🔹 رياضيات 1\n🔹 فيزياء\n🔹 التربية البدنية 1\n🔹 لغة عربية 1\n🔹 أساسيات الحاسب الآلي\n🔹 مدخل إلى مهارات القرن 21\n🔹 السلامة والصحة المهنية",
        "2️⃣ الفصل الثاني": "📚 **مقررات الفصل التدريبي الثاني:**\n🔹 سلوك مهني\n🔹 لغة عربية 2\n🔹 لغة إنجليزية 2\n🔹 رياضيات 2\n🔹 التربية البدنية 2\n🔹 ثقافة إسلامية 2\n🔹 ورش تأسيسية\n🔹 تطبيقات الحاسب الآلي\n🔹 مهارات التواصل والتعاون\n🔹 التفكير الناقد والإبداعي",
        "3️⃣ الفصل الثالث": "📚 **مقررات الفصل التدريبي الثالث:**\n🔹 ثقافة إسلامية 3\n🔹 الرسم الهندسي\n🔹 بحث ومصادر المعلومات\n🔹 رياضيات 3\n🔹 لغة إنجليزية 3\n🔹 أجهزة وقياس\n🔹 أساسيات الكهرباء\n🔹 أساسيات الإلكترونيات\n🔹 تطبيقات مفتوحة المصدر",
        "4️⃣ الفصل الرابع": "📚 **مقررات الفصل التدريبي الرابع:**\n🔹 مقدمة في ريادة الأعمال\n🔹 تقنيات الانترنت\n🔹 مكونات الحاسب 1\n🔹 لغة برمجة 1\n🔹 أساسيات الشبكات\n🔹 رسم الشبكات بالحاسب\n🔹 أساسيات نظام لينكس\n🔹 أنشطة مهنية",
        "5️⃣ الفصل الخامس": "📚 **مقررات الفصل التدريبي الخامس:**\n🔹 مكونات الحاسب 2\n🔹 صيانة الأجهزة الكفية\n🔹 لغة برمجة 2\n🔹 تمديد الكيابل النحاسية\n🔹 شبكات الحاسب\n🔹 نظام تشغيل الشبكة 1\n🔹 مشاريع إنتاجية\n🔹 أنشطة مهنية 2",
        "6️⃣ الفصل السادس": "📚 **مقررات الفصل التدريبي السادس:**\n🔹 مبادئ قواعد البيانات\n🔹 طرفيات الحاسب\n🔹 مهارات صيانة الحاسب\n🔹 تمديد كيابل الألياف الضوئية\n🔹 نظام تشغيل الشبكة 2\n🔹 تدريب إنتاجي\n🔹 أنشطة مهنية 3",
        "🖥️ برامج فصلية (إدخال بيانات)": "📚 **البرامج القصيرة (فصل تدريبي واحد):**\n\n🔹 **برنامج إدخال البيانات ومعالجة النصوص**\nيُعد هذا البرنامج دورة مستقلة عن خطة الدبلوم، ويهدف لإكساب المتدرب مهارات إدخال البيانات بسرعة ودقة."
    }

    if text in term_plans:
        reply_content = f"{term_plans[text]}\n\n🔗 **لتحميل الحقائب التدريبية:**\n{DRIVE_LINK}"
        await update.message.reply_text(reply_content, parse_mode='Markdown', disable_web_page_preview=True)
        return

    # --- الروابط والأقسام الثابتة ---
    if text == "🔗 منصة تقني ورايات":
        msg = "🌐 **أهم الروابط التدريبية:**\n\n🔹 منصة تقني:\nhttps://tvtclms.edu.sa\n\n🔹 بوابة رايات:\nhttps://rayat.tvtc.gov.sa"
        await update.message.reply_text(msg, reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return

    if text == "📍 موقع القسم":
        await update.message.reply_text("📍 [موقع القسم على الخريطة](http://maps.google.com/?q=Buraydah)", reply_markup=get_back_menu(), parse_mode='Markdown')
        return
    
    if text == "📚 الحقائب التدريبية":
        await update.message.reply_text(f"📚 **المستودع الشامل للحقائب التدريبية:**\n{DRIVE_LINK}", reply_markup=get_back_menu(), parse_mode='Markdown', disable_web_page_preview=True)
        return
    
    if text == "📅 التقويم التدريبي":
        if os.path.exists('calendar.jpg'):
            await update.message.reply_photo(photo=open('calendar.jpg', 'rb'), caption="📅 التقويم المعتمد", reply_markup=get_back_menu())
        else:
            await update.message.reply_text("⚠️ ملف التقويم `calendar.jpg` مفقود من السيرفر.", reply_markup=get_back_menu())
        return
    
    if text == "👨‍🏫 تواصل مع رئيس القسم":
        await update.message.reply_text(f"👨‍🏫 للتواصل المباشر والخاص:\n🔗 {TELEGRAM_CONTACT_LINK}", reply_markup=get_back_menu())
        return

    # --- خدمات الغياب والأعذار ---
    if text == "📊 استعلام الغياب":
        await update.message.reply_text("🔎 أرسل **رقمك التدريبي** الآن للبحث في السجلات..", reply_markup=get_back_menu())
        return

    if text == "📝 رفع الغياب والأعذار":
        await update.message.reply_text("📝 **تعليمات هامة:**\nأرسل صورة العذر واكتب رقمك التدريبي في خانة (الوصف / Caption).", reply_markup=get_back_menu())
        return

    # --- منطق البحث في الإكسل (مع الرد الذكي للتحفيز) ---
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
                
                max_absence = 0 # متغير لحفظ أعلى نسبة غياب للطالب
                
                for _, row in result.iterrows():
                    val = float(row['parsnt'])
                    if val > max_absence:
                        max_absence = val # تحديث أعلى نسبة
                        
                    icon = "🔴 حرمان" if val >= 20 else ("⚠️ تنبيه" if val >= 15 else "🟢 منتظم")
                    msg += f"📖 {row['c_nam']}: %{val} {icon}\n"
                
                # إضافة الرد الذكي والتحفيزي بناءً على أعلى نسبة غياب
                msg += "\n💡 <b>رسالة القسم:</b>\n"
                if max_absence == 0:
                    msg += "🌟 أداء مثالي! القسم يفتخر بانتظامك والتزامك التام، استمر يا بطل ولا تتراجع."
                elif max_absence < 15:
                    msg += "🟢 وضعك سليم ومنتظم، لكن احرص على عدم زيادة غيابك لضمان التفوق والنجاح."
                elif max_absence < 20:
                    msg += "⚠️ تنبيه هام! لقد اقتربت من حافة الحرمان في بعض المواد. مستقبلك أهم، ننتظر التزامك."
                else:
                    msg += "🔴 للأسف وصلت لنسبة الحرمان. نأمل منك مراجعة إدارة القسم فوراً لمعالجة وضعك الأكاديمي."

                await update.message.reply_text(msg, parse_mode='HTML', reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ عذراً، الرقم التدريبي غير مسجل لدينا.", reply_markup=get_back_menu())
        except Exception as e:
            if 'status_msg' in locals(): await status_msg.delete()
            print(f"Excel Error: {e}")
            await update.message.reply_text("⚠️ حدث خطأ أثناء قراءة ملف `data.xlsx`. تأكد من سلامة الملف.", reply_markup=get_back_menu())
        return

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text("⚠️ عذراً، يجب كتابة (رقمك التدريبي) في وصف الصورة قبل الإرسال.", reply_markup=get_back_menu())
        return
    
    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 عذر جديد:\nالبيانات: {update.message.caption}")
        await update.message.copy(chat_id=GROUP_ID)
        await update.message.reply_text("✅ تم استلام عذرك بنجاح وتوجيهه للمسؤول.", reply_markup=get_main_menu())
    except Exception as e:
        print(f"Group Error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ. تأكد أن البوت مضاف كمشرف (Admin) في مجموعة الأرشيف.", reply_markup=get_main_menu())

# --- 7. التشغيل ---
def main():
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logic))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_docs))
    
    print("🚀 تم تشغيل البوت بكل ميزاته بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
