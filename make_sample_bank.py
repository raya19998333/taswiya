# -*- coding: utf-8 -*-
"""يولّد كشف بنك تجريبياً من دفتر الخزينة (دفعة واحدة لكل مرجع) مع حقن حالات للاختبار."""
import sys, random
from collections import defaultdict
import openpyxl
from reconciliation import parse_ledger

random.seed(7)
ledger_path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/__خزينة_الرواتب_2026.xlsx"
sheet = sys.argv[2] if len(sys.argv) > 2 else "يناير"
out = sys.argv[3] if len(sys.argv) > 3 else "كشف_بنك_تجريبي.xlsx"

led = [e for e in parse_ledger(ledger_path, sheet) if e.ref and e.amount < 0]
by_ref = defaultdict(float)
date_of = {}
for e in led:
    by_ref[e.ref] += abs(e.amount)
    date_of.setdefault(e.ref, e.txn_date)

rows = [(ref, date_of[ref], -round(t, 3), f"دفعة {ref}") for ref, t in by_ref.items()]
# حقن: حذف مرجعين، إضافة رسوم بنكية، تغيير مبلغ دفعة
random.shuffle(rows)
rows = rows[2:]
rows += [("B602990001", date_of[led[0].ref], -45.5, "رسوم خدمات بنكية"),
         ("B602990002", date_of[led[0].ref], -12.0, "عمولة تحويل")]
rows[5] = (rows[5][0], rows[5][1], round(rows[5][2] + 250, 3), rows[5][3])

wb = openpyxl.Workbook(); ws = wb.active; ws.title = "BankStatement"
ws.append(["المرجع", "التاريخ", "المبلغ", "البيان"])
for r in rows:
    ws.append(list(r))
wb.save(out)
print(f"تم إنشاء كشف بنك تجريبي: {out}  ({len(rows)} حركة)")
