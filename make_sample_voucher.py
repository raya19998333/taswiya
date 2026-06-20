# -*- coding: utf-8 -*-
"""ينشئ سند صرف يحاكي نظام Cheque Management - وزارة الصحة."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display

OUT = Path(__file__).parent / "sample_voucher.png"

def ar(text):
    return get_display(arabic_reshaper.reshape(str(text)))

W, H = 1000, 720
img = Image.new("RGB", (W, H), "#FFFFFF")
draw = ImageDraw.Draw(img)

reg_fonts  = ["C:/Windows/Fonts/calibri.ttf",  "C:/Windows/Fonts/arial.ttf",  "C:/Windows/Fonts/tahoma.ttf"]
bold_fonts = ["C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/tahomabd.ttf"]
reg_path   = next((f for f in reg_fonts  if Path(f).exists()), None)
bold_path  = next((f for f in bold_fonts if Path(f).exists()), None)

def fr(s): return ImageFont.truetype(reg_path  or bold_path, s) if reg_path or bold_path else ImageFont.load_default()
def fb(s): return ImageFont.truetype(bold_path or reg_path,  s) if bold_path or reg_path else ImageFont.load_default()

BLUE   = "#1F4E78"
LBLUE  = "#BDD7EE"
GRAY   = "#F2F2F2"
LGRAY  = "#D9D9D9"
RED    = "#C00000"
BLACK  = "#222222"

# ═══ رأس الصفحة ═══
draw.rectangle([0, 0, W, 75], fill=BLUE)
draw.text((W//2, 22), ar("وزارة الصحة - سلطنة عُمان"), font=fb(18), fill="white", anchor="mm")
draw.text((W//2, 52), "MINISTRY OF HEALTH - SULTANATE OF OMAN", font=fr(13), fill=LBLUE, anchor="mm")

# ═══ عنوان السند ═══
draw.rectangle([0, 75, W, 110], fill=LGRAY)
draw.text((W//2, 92), ar("سند صرف نقدي / إلكتروني"), font=fb(16), fill=BLUE, anchor="mm")
draw.text((330, 92), "ELECTRONIC PAYMENT (ePay) VOUCHER", font=fr(11), fill="#555555", anchor="mm")

# ═══ حدود خارجية ═══
draw.rectangle([15, 115, W-15, H-15], outline=BLUE, width=2)

# ═══ دالة رسم حقل ═══
def field(x, y, w, h, label_ar, label_en, value, value_color=BLUE):
    draw.rectangle([x, y, x+w, y+h], outline=LGRAY, width=1)
    draw.text((x+w-8, y+7), ar(label_ar), font=fr(10), fill="#777777", anchor="rm")
    draw.text((x+8,   y+7), label_en,     font=fr(9),  fill="#999999")
    draw.text((x+w//2, y+h//2+4), ar(value) if any('؀' <= c <= 'ۿ' for c in str(value)) else value,
              font=fb(13), fill=value_color, anchor="mm")

# ═══ صف 1: هوية السند + رقم المستند + التاريخ ═══
y0 = 120
field(20,  y0, 200, 55, "هوية السند",   "Voucher ID",   "VCH-2025-004821")
field(220, y0, 260, 55, "رقم المستند",  "Document No.", "31245", RED)
field(480, y0, 230, 55, "تاريخ المستند","Document Date","2025-06-15")
field(710, y0, 275, 55, "نوع السند",    "Voucher Type", "وزارة المالية")

# ═══ صف 2: بنك + رقم الشيك + تاريخ الشيك + تاريخ الإيداع ═══
y1 = y0 + 55
field(20,  y1, 235, 55, "البنك",          "Bank",         "بنك مسقط")
field(255, y1, 200, 55, "رقم الحساب",    "Account No.",  "BM-0044-2025")
field(455, y1, 200, 55, "رقم الشيك",     "Cheque No.",   "CHQ-884421")
field(655, y1, 165, 55, "تاريخ الشيك",   "Cheque Date",  "2025-06-15")
field(820, y1, 165, 55, "تاريخ الإيداع", "Deposit Date", "2025-06-16")

# ═══ جدول التفاصيل ═══
y2 = y1 + 60
draw.rectangle([20, y2, W-20, y2+28], fill=BLUE)
headers = [
    (ar("الرقم الوظيفي"), "Staff No.",    75),
    (ar("الاسم"),          "Name",        200),
    (ar("البنك"),          "Bank",        130),
    (ar("رقم الحساب"),    "Account",     155),
    (ar("نوع المستند"),   "Doc Type",    120),
    (ar("المبلغ"),         "Amount",      110),
    (ar("ملاحظات"),        "Notes",       165),
]
x_cur = 20
col_widths = [h[2] for h in headers]
for (h_ar, h_en, cw) in headers:
    draw.text((x_cur + cw//2, y2+14), h_ar, font=fb(10), fill="white", anchor="mm")
    x_cur += cw

# ═══ صفوف البيانات ═══
rows = [
    ("10045231", "أحمد بن سالم الراشدي",   "بنك مسقط",   "BM-7712-01", "ePay", "350.000", ""),
    ("10038822", "فاطمة بنت خالد النبهاني", "بنك ظفار",   "DH-4421-09", "ePay", "420.500", ""),
    ("10051104", "محمد بن علي الحارثي",     "بنك عُمان",  "BO-1133-22", "ePay", "479.500", ""),
]
row_h = 42
for ri, (sno, name, bank, acc, dtype, amt, note) in enumerate(rows):
    ry = y2 + 28 + ri * row_h
    bg = "#FFFFFF" if ri % 2 == 0 else "#F7FBFF"
    draw.rectangle([20, ry, W-20, ry+row_h], fill=bg, outline=LGRAY, width=1)
    cells = [sno, name, bank, acc, dtype, amt, note]
    x_cur = 20
    for ci, (val, cw) in enumerate(zip(cells, col_widths)):
        cell_val = ar(val) if any('؀' <= c <= 'ۿ' for c in val) else val
        color = RED if ci == 5 else BLACK
        draw.text((x_cur + cw//2, ry + row_h//2), cell_val, font=fr(11), fill=color, anchor="mm")
        x_cur += cw

# ═══ إجماليات ═══
y3 = y2 + 28 + len(rows) * row_h + 5
draw.rectangle([20, y3, W-20, y3+38], fill="#EFF7FF", outline=BLUE, width=1)
draw.text((W-30,    y3+19), ar("إجمالي المبلغ المدفوع:"),          font=fb(12), fill=BLUE, anchor="rm")
draw.text((W-310,   y3+19), "1,250.000 " + ar("ر.ع"),              font=fb(14), fill=RED,  anchor="mm")
draw.text((490,     y3+19), ar("المبلغ بالكلمات: ألف ومئتان وخمسون ريالاً عُمانياً فقط لا غير"),
          font=fr(11), fill="#333333", anchor="mm")

# ═══ التوقيعات ═══
y4 = y3 + 50
sigs = [(130, "المحاسب\nAccountant"), (W//2, "المشرف\nSupervisor"), (W-130, "المدير المالي\nFinance Manager")]
for sx, label in sigs:
    draw.rectangle([sx-80, y4, sx+80, y4+55], outline=LGRAY, width=1)
    draw.line([sx-65, y4+40, sx+65, y4+40], fill="#666666", width=1)
    lines = label.split("\n")
    draw.text((sx, y4+46), ar(lines[0]), font=fr(11), fill="#444444", anchor="mm")

# ═══ تذييل ═══
draw.rectangle([0, H-30, W, H], fill=LGRAY)
draw.text((W//2, H-15),
          ar("هذا السند محرر آلياً | نظام إدارة الشيكات | وزارة الصحة | 2025"),
          font=fr(10), fill="#666666", anchor="mm")
draw.text((30, H-15), "Printed: 2025-06-15  08:46", font=fr(9), fill="#999999", anchor="lm")
draw.text((W-30, H-15), "Page 1/1", font=fr(9), fill="#999999", anchor="rm")

img.save(OUT, "PNG", dpi=(150, 150))
print("Done: " + str(OUT))
