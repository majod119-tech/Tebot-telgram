import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        return await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        
    try:
        status_msg = await message.reply_text("⏳ جاري عمل مسح شامل لكل صفحات الملف ونقل البيانات... 🔍")
        
        # 1. تنزيل الملف القديم
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        
        # 2. فتح القالب الجديد المعتمد
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        
        # --- دالة 1: البحث عن ورقة (الخطة التدريبية) داخل الملف ---
        def get_plan_sheet(wb):
            best_sheet = wb.active
            max_score = 0
            for sheet in wb.worksheets:
                score = 0
                for r in range(1, 40):
                    for c in range(1, 15):
                        val = str(sheet.cell(row=r, column=c).value or "")
                        if "ساعات" in val or "أهداف" in val or "سبوع" in val or "موضوع" in val:
                            score += 1
                if score > max_score:
                    max_score = score
                    best_sheet = sheet
            return best_sheet

        ws_old = get_plan_sheet(wb_old)
        ws_new = get_plan_sheet(wb_new)

        # --- دالة 2: استخراج أماكن الأعمدة وسطر البداية ---
        def find_table_structure(ws):
            cols = {'week': 1, 'unit': 2, 'hours': 3, 'goals': 4, 'topics': 5}
            header_row = 4
            max_matches = 0
            
            for r in range(1, 40):
                matches = 0
                temp_cols = {}
                for c in range(1, ws.max_column + 1):
                    val = str(ws.cell(row=r, column=c).value or "").replace(" ", "")
                    if not val: continue
                    
                    if "سبوع" in val or "رقم" in val:
                        temp_cols['week'] = c; matches += 1
                    elif "اسم" in val or "وحد" in val:
                        temp_cols['unit'] = c; matches += 1
                    elif "ساعات" in val or "زمن" in val:
                        temp_cols['hours'] = c; matches += 1
                    elif "أهداف" in val or "هدف" in val:
                        temp_cols['goals'] = c; matches += 1
                    elif "موضوع" in val or "محتوى" in val or "مفردات" in val:
                        temp_cols['topics'] = c; matches += 1
                        
                if matches > max_matches:
                    max_matches = matches
                    cols = temp_cols
                    header_row = r
            return cols, header_row

        old_cols, old_header_row = find_table_structure(ws_old)
        new_cols, new_header_row = find_table_structure(ws_new)

        # --- دالة 3: استخراج وكتابة القيم بأمان (تخطي الدمج) ---
        def get_val(ws, r, c):
            if not c: return None
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
            return cell.value

        def write_safe(ws, r, c, val):
            if not c or val is None or str(val).strip() == "": return
            cell = ws.cell(row=r, column=c)
            for merged_range in ws.merged_cells.ranges:
                if cell.coordinate in merged_range:
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = val
                    return
            cell.value = val

        # --- 4. سحب البيانات من الملف القديم ---
        extracted_data = []
        for r in range(old_header_row + 1, ws_old.max_row + 1):
            week = get_val(ws_old, r, old_cols.get('week'))
            unit = get_val(ws_old, r, old_cols.get('unit'))
            hours = get_val(ws_old, r, old_cols.get('hours'))
            goals = get_val(ws_old, r, old_cols.get('goals'))
            topics = get_val(ws_old, r, old_cols.get('topics'))
            
            # إذا كل القيم فارغة، نتخطى السطر
            if not any([week, unit, hours, goals, topics]):
                continue
                
            extracted_data.append((week, unit, hours, goals, topics))

        if not extracted_data:
            raise Exception("لم أجد أي بيانات! تأكد أن الملف القديم يحتوي على جدول الخطة.")

        # --- 5. صب البيانات في القالب الجديد ---
        current_new_row = new_header_row + 1
        for data in extracted_data:
            write_safe(ws_new, current_new_row, new_cols.get('week') or 1, data[0])
            write_safe(ws_new, current_new_row, new_cols.get('unit') or 2, data[1])
            write_safe(ws_new, current_new_row, new_cols.get('hours') or 3, data[2])
            write_safe(ws_new, current_new_row, new_cols.get('goals') or 4, data[3])
            write_safe(ws_new, current_new_row, new_cols.get('topics') or 5, data[4])
            current_new_row += 1

        # --- 6. الحفظ والإرسال ---
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            msg = f"🎉 تم النقل بنجاح!\n"
            msg += f"📄 سحبت البيانات من صفحة: [{ws_old.title}]\n"
            msg += f"📝 كتبتها في القالب صفحة: [{ws_new.title}]\n"
            msg += f"✅ عدد الصفوف المنقولة: {len(extracted_data)} صف."
            await message.reply_document(document=doc, caption=msg)
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}")
        context.user_data['waiting_for_plan'] = False
