import os
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# --- 1. إعداد خادم الويب (لكي لا يتوقف في Render) ---
app = Flask('')
@app.route('/')
def home():
    return "البوت يعمل بنجاح!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- 2. إعداد كود البوت ---
# سيقوم Render بقراءة التوكن من إعدادات Environment Variables التي وضعناها سابقاً
TOKEN = os.environ.get("TOKEN") 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك! 📊\nأرسل **رقم المدرب** لمعرفة نسبة الغياب.")

async def search_trainer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    
    try:
        # قراءة ملف البيانات
        df = pd.read_csv('data.csv')
        
        # ⚠️ تنبيه: قم بتغيير هذه الأسماء لتطابق الأعمدة في ملفك تماماً
        col_id = 'رقم المدرب'    
        col_absence = 'نسبة الغياب'
        col_name = 'اسم المدرب' 
        
        # توحيد نوع البيانات كنصوص لتجنب أخطاء البحث
        df[col_id] = df[col_id].astype(str)
        
        # البحث عن الرقم داخل العمود
        result = df[df[col_id] == user_input]
        
        if not result.empty:
            # إذا وجد الرقم، يستخرج البيانات
            absence_rate = result.iloc[0][col_absence]
            trainer_name = result.iloc[0][col_name] 
            
            reply_message = f"👤 المدرب: {trainer_name}\n📊 نسبة الغياب: {absence_rate}"
        else:
            reply_message = "❌ عذراً، لم أتمكن من العثور على رقم المدرب هذا. تأكد من الرقم وحاول مجدداً."
            
    except FileNotFoundError:
        reply_message = "⚠️ خطأ: ملف البيانات (data.csv) غير موجود."
    except KeyError as e:
        reply_message = f"⚠️ خطأ في أسماء الأعمدة. تأكد أن العمود المسمى {e} موجود في الملف."
    except Exception as e:
        reply_message = "⚠️ حدث خطأ غير متوقع أثناء البحث."
        print(f"Error: {e}")

    await update.message.reply_text(reply_message)

def main():
    # تشغيل السيرفر في خلفية لكي يعمل مع البوت في نفس الوقت
    t = Thread(target=run_flask)
    t.start()

    # تشغيل البوت
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_trainer))
    
    application.run_polling()

if __name__ == '__main__':
    main()
