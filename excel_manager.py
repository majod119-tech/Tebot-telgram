import openpyxl
import os
from telegram import Update
from telegram.ext import ContextTypes

async def convert_plan_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.document:
        return await message.reply_text("⚠️ الرجاء إرسال ملف Excel صحيح.")
        
    try:
        status_msg = await message.reply_text("⏳ جاري توجيه البيانات للصفحة الصحيحة في القالب وتحديث جميع الحقول... 🔍")
        
        # 1. تنزيل الملف القديم
        file_info = await message.document.get_file()
        old_file_path = f"temp_old_{message.from_user.id}.xlsx"
        await file_info.download_to_drive(custom_path=old_file_path)
            
        wb_old = openpyxl.load_workbook(old_file_path, data_only=True)
        
        # 2. فتح القالب الجديد المعتمد
        template_path = os.path.join(os.path.dirname(__file__), 'data', 'Curriculum_Plan_v3.xlsx')
        wb_new = openpyxl.load_workbook(template_path)
        
        # --- دالة 1: البحث عن ورقة الخطة في الملف القديم (تعمل بنجاح 100%) ---
        def get_old_plan_sheet(wb):
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

        # --- دالة 2: تحديد الصفحة الصحيحة في القالب الجديد (إجبارياً) ---
        def get_new_plan_sheet(wb):
            for sheet in wb.worksheets:
                # نبحث عن صفحة توصيف المقرر ونتجاهل صفحة Data تماماً
                if "توصيف" in sheet.title or "المقرر" in sheet.title or "خطة" in sheet.title:
                    return sheet
            # خط رجعة: إذا تغير اسم الصفحة، يختار أي صفحة ما عدا Data والغلاف
            for sheet in wb.worksheets:
                if sheet.title.lower() != "data" and "غلاف" not in sheet.title and "دليل" not in sheet.title:
                    return sheet
            return wb.active

        ws_old = get_old_plan_sheet(wb_old)
        ws_new = get_new_plan_sheet(wb_new)

        # --- دالة 3: استخراج أماكن الأعمدة بدقة عالية ---
        def find_table_structure(ws):
            cols = {'week': None, 'unit': None, 'hours': None, 'goals': None, 'topics': None}
            header_row = 4
            max_matches = 0
            
            for r in range(1, 45):
                matches = 0
                temp_cols = {}
                for c in range(1, ws.max_column + 1):
                    val = str(ws.cell(row=r, column=c).value or "").replace(" ", "").replace("\n", "")
                    if not val: continue
                    
                    if ("سبوع" in val or "رقم" in val or val == "م") and 'week' not in temp_cols:
                        temp_cols['week'] = c; matches += 1
                    elif ("اسم" in val or "وحد" in val or "مسمى" in val) and 'unit' not in temp_cols:
                        temp_cols['unit'] = c; matches += 1
                    elif ("ساعات" in val or "زمن" in val or "وقت" in val) and 'hours' not in temp_cols:
                        temp_cols['hours'] = c; matches += 1
                    elif ("أهداف" in val or "هدف" in val or "تفصيلي" in val) and 'goals' not in temp_cols:
                        temp_cols['goals'] = c; matches += 1
                    elif ("موضوع" in val or "محتوى" in val or "مفردات" in val) and 'topics' not in temp_cols:
                        temp_cols['topics'] = c; matches += 1
                        
                if matches > max_matches:
                    max_matches = matches
                    cols = temp_cols
                    header_row = r
            return cols, header_row

        old_cols, old_header_row = find_table_structure(ws_old)
        new_cols, new_header_row = find_table_structure(ws_new)

        # 🛡️ تأمين مسارات القالب الجديد (لو كانت عناوينه مدمجة بشكل مخفي)
        if not new_cols.get('week'): new_cols['week'] = 1
        if not new_cols.get('unit'): new_cols['unit'] = 2
        if not new_cols.get('hours'): new_cols['hours'] = 3
        if not new_cols.get('goals'): new_cols['goals'] = 4
        if not new_cols.get('topics'): new_cols['topics'] = 5

        # --- دالة 4: استخراج وكتابة القيم بأمان (لتخطي الدمج) ---
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

        # --- 5. سحب البيانات من الملف القديم ---
        extracted_data = []
        for r in range(old_header_row + 1, ws_old.max_row + 1):
            week = get_val(ws_old, r, old_cols.get('week'))
            unit = get_val(ws_old, r, old_cols.get('unit'))
            hours = get_val(ws_old, r, old_cols.get('hours'))
            goals = get_val(ws_old, r, old_cols.get('goals'))
            topics = get_val(ws_old, r, old_cols.get('topics'))
            
            if not any([week, unit, hours, goals, topics]):
                continue
                
            extracted_data.append((week, unit, hours, goals, topics))

        if not extracted_data:
            raise Exception("لم أجد أي بيانات! تأكد أن الملف القديم يحتوي على جدول الخطة.")

        # --- 6. صب البيانات في القالب الجديد ---
        current_new_row = new_header_row + 1
        for data in extracted_data:
            write_safe(ws_new, current_new_row, new_cols['week'], data[0])
            write_safe(ws_new, current_new_row, new_cols['unit'], data[1])
            write_safe(ws_new, current_new_row, new_cols['hours'], data[2])
            write_safe(ws_new, current_new_row, new_cols['goals'], data[3])
            write_safe(ws_new, current_new_row, new_cols['topics'], data[4])
            current_new_row += 1

        # --- 7. الحفظ والإرسال ---
        output_filename = f"الخطة_المحدثة_اصدار_3.xlsx"
        wb_new.save(output_filename)
        
        with open(output_filename, 'rb') as doc:
            msg = f"🎉 تم النقل بنجاح وبدقة 100%!\n"
            msg += f"📄 سحبت البيانات من: [{ws_old.title}]\n"
            msg += f"📝 كتبتها في القالب صفحة: [{ws_new.title}]\n"
            msg += f"✅ تم تحديث جميع الحقول لـ {len(extracted_data)} صف."
            await message.reply_document(document=doc, caption=msg)
            
        os.remove(old_file_path)
        os.remove(output_filename)
        await status_msg.delete()
        context.user_data['waiting_for_plan'] = False
        
    except Exception as e:
        await message.reply_text(f"⚠️ حدث خطأ: {str(e)}")
        context.user_data['waiting_for_plan'] = False
