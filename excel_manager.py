import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        return await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        
    try:
        status_msg = await message.reply_text("⏳ جاري سحب البيانات من الأعمدة النشطة... 🔍")
        
        # 1. تنزيل الملف القديم
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        
        # 2. تحديد الصفحة اللي فيها بيانات فعلية (لتفادي الصفحات الفارغة)
        ws_old = wb_old.active
        max_data = 0
        for sheet in wb_old.worksheets:
            cells_with_data = 0
            for r in range(1, min(50, sheet.max_row + 1)):
                for c in range(1, min(20, sheet.max_column + 1)):
                    if sheet.cell(row=r, column=c).value:
                        cells_with_data += 1
            if cells_with_data > max_data:
                max_data = cells_with_data
                ws_old = sheet

        # 3. 🎯 القناص: اكتشاف الأعمدة اللي فيها بيانات وتجاهل الهوامش الفارغة
        used_columns = []
        for c in range(1, ws_old.max_column + 1):
            count = 0
            for r in range(1, min(50, ws_old.max_row + 1)):
                if ws_old.cell(row=r, column=c).value:
                    count += 1
            if count >= 3: # إذا العمود فيه 3 قيم على الأقل، نعتبره عمود بيانات
                used_columns.append(c)
        
        if len(used_columns) < 4:
            raise Exception("الملف يبدو فارغاً أو الأعمدة غير مكتملة.")
        
        col_week = used_columns[0]
        col_unit = used_columns[1]
        col_hours = used_columns[2]
        col_goals = used_columns[3]
        col_topics = used_columns[4] if len(used_columns) > 4 else used_columns[3]

        # 4. فتح القالب الجديد وتوجيهه لصفحة توصيف المقرر
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        
        ws_new = wb_new.active
        for sheet in wb_new.worksheets:
            if "توصيف" in sheet.title or "المقرر" in sheet.title or "خطة" in sheet.title:
                ws_new = sheet
                break

        # 5. دالة الكتابة الآمنة لتخطي دمج الخلايا
        def write_safe(ws, r, c, val):
            if val is None or str(val).strip() == "": return
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = val
                    return
            cell.value = val

        # 6. السحب
        extracted_data = []
        for r in range(1, ws_old.max_row + 1):
            week = ws_old.cell(row=r, column=col_week).value
            unit = ws_old.cell(row=r, column=col_unit).value
            hours = ws_old.cell(row=r, column=col_hours).value
            goals = ws_old.cell(row=r, column=col_goals).value
            topics = ws_old.cell(row=r, column=col_topics).value if len(used_columns) > 4 else ""
            
            if not any([week, unit, hours, goals, topics]):
                continue
                
            # تجاهل أي سطور فيها عناوين باقية
            row_text = str(week) + str(unit) + str(hours)
            if "ساعات" in row_text or "أهداف" in row_text or "سبوع" in row_text or "رئيس" in row_text:
                continue
                
            extracted_data.append((week, unit, hours, goals, topics))

        if not extracted_data:
            raise Exception("لم أجد بيانات صالحة للنقل. تأكد من الملف.")

        # 7. تحديد سطر البداية في القالب الجديد
        new_start_row = 5
        for r in range(1, 20):
            val = str(ws_new.cell(row=r, column=3).value or "")
            if "ساعات" in val or "زمن" in val:
                new_start_row = r + 1
                break

        # 8. صب البيانات
        current_new_row = new_start_row
        for data in extracted_data:
            write_safe(ws_new, current_new_row, 1, data[0])
            write_safe(ws_new, current_new_row, 2, data[1])
            write_safe(ws_new, current_new_row, 3, data[2])
            write_safe(ws_new, current_new_row, 4, data[3])
            write_safe(ws_new, current_new_row, 5, data[4])
            current_new_row += 1

        # 9. الحفظ والإرسال
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            await message.reply_document(
                document=doc, 
                caption=f"🎉 تم النقل بنجاح!\n✅ عدد الصفوف المضافة: {len(extracted_data)}\n📄 تم سحب الأعمدة بذكاء."
            )
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}")
        context.user_data['waiting_for_plan'] = False
