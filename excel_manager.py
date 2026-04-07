import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        return await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        
    try:
        status_msg = await message.reply_text("⏳ جاري النقل المباشر للبيانات... 🔍")
        
        # 1. تنزيل الملف القديم (البيانات الصافية)
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        ws_old = wb_old.active # لأنك خليته شيت واحد
        
        # 2. فتح القالب الجديد
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        
        # 3. توجيه البوت لصفحة "توصيف المقرر" في القالب الجديد
        ws_new = wb_new.active
        for sheet in wb_new.worksheets:
            if "توصيف" in sheet.title or "المقرر" in sheet.title or "خطة" in sheet.title:
                ws_new = sheet
                break

        # 4. دالة الكتابة الآمنة (عشان ما ينكسر دمج القالب)
        def write_safe(ws, r, c, val):
            if val is None or str(val).strip() == "": return
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = val
                    return
            cell.value = val

        # 5. السحب المباشر (لأن الملف القديم نظيف)
        extracted_data = []
        for r in range(1, ws_old.max_row + 1):
            # نقرأ الأعمدة من 1 إلى 5 بالترتيب
            week = ws_old.cell(row=r, column=1).value
            unit = ws_old.cell(row=r, column=2).value
            hours = ws_old.cell(row=r, column=3).value
            goals = ws_old.cell(row=r, column=4).value
            topics = ws_old.cell(row=r, column=5).value
            
            # لو السطر فاضي تماماً، نتجاهله
            if not any([week, unit, hours, goals, topics]):
                continue
                
            # لو السطر فيه عناوين بالغلط (مثل كلمة "ساعات" أو "أهداف")، نتجاهله
            row_text = str(week) + str(unit) + str(hours)
            if "ساعات" in row_text or "أهداف" in row_text or "سبوع" in row_text:
                continue
                
            extracted_data.append((week, unit, hours, goals, topics))

        # 6. تحديد سطر البداية في القالب الجديد (أول سطر بعد ترويسة الجودة)
        new_start_row = 5 # رقم افتراضي
        for r in range(1, 20):
            val = str(ws_new.cell(row=r, column=3).value or "")
            if "ساعات" in val or "زمن" in val:
                new_start_row = r + 1 # نبدأ الكتابة تحت العناوين مباشرة
                break

        # 7. صب البيانات في القالب
        current_new_row = new_start_row
        for data in extracted_data:
            write_safe(ws_new, current_new_row, 1, data[0])
            write_safe(ws_new, current_new_row, 2, data[1])
            write_safe(ws_new, current_new_row, 3, data[2])
            write_safe(ws_new, current_new_row, 4, data[3])
            write_safe(ws_new, current_new_row, 5, data[4])
            current_new_row += 1

        # 8. الحفظ والإرسال
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            await message.reply_document(
                document=doc, 
                caption=f"🎉 تم النقل المباشر بنجاح!\n✅ عدد الصفوف التي تم صبها: {len(extracted_data)} صف."
            )
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}")
        context.user_data['waiting_for_plan'] = False
