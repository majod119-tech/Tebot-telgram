import pandas as pd
import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # التأكد من أن المرفق ملف
    if not message.document:
        await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        return
        
    try:
        await message.reply_text("⏳ جاري تحليل الخطة ونقل البيانات للقالب الجديد... ثواني بس.")
        
        # 1. تحميل الملف القديم من التيليجرام
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        # 2. قراءة البيانات
        df_old = pd.read_excel(old_file_path)
        
        # 3. فتح قالب الجودة المعتمد (من مجلد data)
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        ws_new = wb_new.active 
        
        # 4. النقل (تأكد من مطابقة أسماء الأعمدة لملفك القديم)
        start_row = 5 # الصف اللي يبدأ منه الجدول في قالبك الجديد
        
        for index, row in df_old.iterrows():
            current_row = start_row + index
            ws_new.cell(row=current_row, column=1).value = row.get("رقم الوحدة", "")
            ws_new.cell(row=current_row, column=2).value = row.get("اسم الوحدة", "")
            ws_new.cell(row=current_row, column=3).value = row.get("الساعات التدريبية", "")
            ws_new.cell(row=current_row, column=4).value = row.get("الأهداف التفصيلية", "")
            ws_new.cell(row=current_row, column=5).value = row.get("موضوعات التدريب", "")

        # 5. حفظ وإرسال
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            await message.reply_document(document=doc, caption="🎉 تم الانتهاء بنجاح!\nالخطة المحدثة جاهزة ومطابقة لقالب وكالة الجودة 100%.")
            
        # تنظيف السيرفر
        os.remove(old_file_path)
        os.remove(output_filename)
        
        # إنهاء حالة انتظار الملف
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}\nتأكد من اسم قالب الجودة وأسماء الأعمدة.")
        context.user_data['waiting_for_plan'] = False
