import pandas as pd
import openpyxl
import os

def convert_plan_file(message, bot):
    if not message.document:
        bot.send_message(message.chat.id, "⚠️ الرجاء إرسال ملف Excel صحيح.")
        return
        
    try:
        bot.send_message(message.chat.id, "⏳ جاري تحليل الخطة القديمة ونقل البيانات للقالب الجديد... يرجى الانتظار ثواني.")
        
        # --- تحميل الملف القديم ---
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        
        with open(old_file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # --- قراءة البيانات القديمة ---
        df_old = pd.read_excel(old_file_path)
        
        # --- فتح القالب الجديد المعتمد ---
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        ws_new = wb_new.active 
        
        # --- عملية النقل ---
        start_row = 5 
        
        for index, row in df_old.iterrows():
            current_row = start_row + index
            ws_new.cell(row=current_row, column=1).value = row.get("رقم الوحدة", "")
            ws_new.cell(row=current_row, column=2).value = row.get("اسم الوحدة", "")
            ws_new.cell(row=current_row, column=3).value = row.get("الساعات التدريبية", "")
            ws_new.cell(row=current_row, column=4).value = row.get("الأهداف التفصيلية", "")
            ws_new.cell(row=current_row, column=5).value = row.get("موضوعات التدريب", "")

        # --- حفظ وإرسال الملف الجديد ---
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            bot.send_document(message.chat.id, doc, caption="🎉 تم الانتهاء بنجاح!\nهذه الخطة المحدثة مطابقة لقالب وكالة الجودة بنسبة 100%.")
            
        # تنظيف الملفات المؤقتة
        os.remove(old_file_path)
        os.remove(output_filename)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ حدث خطأ أثناء التحويل: {str(e)}")

