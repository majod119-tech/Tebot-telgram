import pandas as pd
import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        return
        
    try:
        status_msg = await message.reply_text("⏳ جاري عمل مسح شامل لكل صفحات الملف ونقل البيانات... ثواني 🔍")
        
        # 1. تحميل الملف القديم
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        
        # فتح القالب الجديد
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        
        # 🌟 1. دالة البحث عن الصفحة الصحيحة (تتجاهل الغلاف والأدلة) 🌟
        def get_target_sheet(wb):
            best_ws = wb.active
            max_score = 0
            for sheet in wb.worksheets:
                score = 0
                for r in range(1, 25):
                    for c in range(1, 15):
                        val = str(sheet.cell(row=r, column=c).value or "")
                        if "ساعات" in val or "أهداف" in val or "رقم" in val or "موضوع" in val:
                            score += 1
                if score > max_score:
                    max_score = score
                    best_ws = sheet
            return best_ws

        ws_old = get_target_sheet(wb_old)
        ws_new = get_target_sheet(wb_new)

        # 🌟 2. دالة استخراج أماكن الأعمدة الذكية 🌟
        def find_columns(ws):
            cols = {'num': 1, 'name': 2, 'hours': 3, 'goals': 4, 'topics': 5}
            header_row = 1
            max_matches = 0
            
            for r in range(1, 20):
                matches = 0
                temp_cols = {}
                for c in range(1, ws.max_column + 1):
                    val = str(ws.cell(row=r, column=c).value or "").strip()
                    if not val: continue
                    
                    if "رقم" in val or "سبوع" in val:
                        temp_cols['num'] = c; matches += 1
                    elif "اسم" in val or "مسمى" in val:
                        temp_cols['name'] = c; matches += 1
                    elif "ساعات" in val or "زمن" in val:
                        temp_cols['hours'] = c; matches += 1
                    elif "أهداف" in val or "هدف" in val:
                        temp_cols['goals'] = c; matches += 1
                    elif "موضوعات" in val or "محتوى" in val or "مفردات" in val:
                        temp_cols['topics'] = c; matches += 1
                        
                if matches > max_matches:
                    max_matches = matches
                    cols = temp_cols
                    header_row = r
            return cols, header_row

        old_cols, old_header_row = find_columns(ws_old)
        
        # تحديد سطر البداية للقالب الجديد
        new_header_row = 4
        for r in range(1, 20):
            for c in range(1, 10):
                val = str(ws_new.cell(row=r, column=c).value or "")
                if "ساعات" in val or "أهداف" in val:
                    new_header_row = r
                    break

        # 🌟 3. دوال القراءة والكتابة الآمنة (لتخطي الخلايا المدمجة) 🌟
        def write_safe(ws, r, c, val):
            if val is None or val == "": return
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = val
                    return
            cell.value = val

        def get_val(ws, r, c):
            if not c: return None
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
            return cell.value

        # 🔄 4. عملية سحب وصب البيانات 
        extracted_data = []
        for r in range(old_header_row + 1, ws_old.max_row + 1):
            num = get_val(ws_old, r, old_cols.get('num'))
            name = get_val(ws_old, r, old_cols.get('name'))
            hours = get_val(ws_old, r, old_cols.get('hours'))
            goals = get_val(ws_old, r, old_cols.get('goals'))
            topics = get_val(ws_old, r, old_cols.get('topics'))
            
            # تجاهل السطور الفارغة بالكامل
            if not num and not name and not hours and not goals and not topics:
                continue
                
            extracted_data.append((num, name, hours, goals, topics))

        if len(extracted_data) == 0:
            raise Exception("لم أجد أي بيانات! تأكد أن الملف القديم يحتوي على جدول خطة التدريب.")

        # صب البيانات في القالب الجديد (الأعمدة 1 إلى 5 حسب طلبك)
        current_new_row = new_header_row + 1
        for data in extracted_data:
            write_safe(ws_new, current_new_row, 1, data[0])
            write_safe(ws_new, current_new_row, 2, data[1])
            write_safe(ws_new, current_new_row, 3, data[2])
            write_safe(ws_new, current_new_row, 4, data[3])
            write_safe(ws_new, current_new_row, 5, data[4])
            current_new_row += 1

        # 💾 5. الحفظ والإرسال
        output_filename = f"الخطة_المحدثة_v3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            await message.reply_document(
                document=doc, 
                caption=f"🎉 تم النقل بنجاح!\nتم سحب ( {len(extracted_data)} ) صف من البيانات وصبها في قالب الجودة 100%."
            )
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}")
        context.user_data['waiting_for_plan'] = False
