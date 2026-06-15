# -*- coding: utf-8 -*-
"""
نظام التسوية البنكية الآلية — الإصدار الثاني | FastAPI Backend v2
يضيف: مصادقة + صلاحيات (RBAC) + حفظ في قاعدة بيانات + سجل تسويات + اعتماد المشرف + سجل تدقيق.
"""
import io
from datetime import datetime
from pathlib import Path
import openpyxl
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from reconciliation import parse_ledger, parse_bank, reconcile
from report import build_report
from database import init_db, get_conn, log_action
from auth import login, current_user, require_role

app = FastAPI(title="نظام التسوية البنكية الآلية")
BASE = Path(__file__).parent
init_db()


def _read(upload: UploadFile, parser, sheet=None):
    try:
        tmp = io.BytesIO(upload.file.read())
        return parser(tmp, sheet) if sheet is not None else parser(tmp)
    except Exception as e:
        raise HTTPException(400, f"تعذّر قراءة الملف {upload.filename}: {e}")


# ───────────── الواجهة ─────────────
@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "login.html").read_text(encoding="utf-8")

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


# ───────────── المصادقة ─────────────
@app.post("/login")
async def do_login(username: str = Form(...), password: str = Form(...)):
    token, u = login(username, password)
    log_action(u["id"], u["username"], "login", "تسجيل دخول")
    return {"token": token, "user": {"username": u["username"], "role": u["role"],
                                     "full_name": u["full_name"]}}


@app.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"username": user["username"], "role": user["role"], "full_name": user["full_name"]}


# ───────────── أوراق الملف ─────────────
@app.post("/sheets")
async def sheets(file: UploadFile = File(...), user: dict = Depends(current_user)):
    wb = openpyxl.load_workbook(io.BytesIO(file.file.read()), read_only=True)
    return {"sheets": wb.sheetnames}


# ───────────── تشغيل المطابقة + الحفظ ─────────────
@app.post("/reconcile")
async def do_reconcile(
    ledger: UploadFile = File(...), bank: UploadFile = File(...),
    ledger_sheet: str = Form(...), bank_sheet: str = Form(None),
    user: dict = Depends(current_user),
):
    led = _read(ledger, parse_ledger, ledger_sheet)
    bnk = _read(bank, parse_bank, bank_sheet or None)
    if not led:
        raise HTTPException(400, "لا توجد قيود في ورقة الخزينة المختارة.")
    result = reconcile(led, bnk)
    run_id = _save_run(user, ledger.filename, bank.filename, ledger_sheet, result)
    log_action(user["id"], user["username"], "reconcile",
               f"تشغيل تسوية #{run_id} ({ledger_sheet})")
    result["run_id"] = run_id
    result["status"] = "draft"
    return JSONResponse(result)


def _save_run(user, ledger_name, bank_name, sheet, result) -> int:
    s = result["summary"]
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO runs(created_by,created_at,ledger_name,bank_name,sheet,
           matched,amount_diff,ledger_only,bank_only,duplicates,matched_total,status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?, 'draft')""",
        (user["id"], datetime.utcnow().isoformat(), ledger_name, bank_name, sheet,
         s["matched"], s["amount_diff"], s["ledger_only"], s["bank_only"],
         s["duplicates"], s["matched_total"]))
    run_id = cur.lastrowid
    for cat in ("matched", "amount_diff", "ledger_only", "bank_only"):
        for b in result[cat]:
            conn.execute(
                """INSERT INTO run_items(run_id,category,ref,ledger_total,bank_total,diff,description)
                   VALUES(?,?,?,?,?,?,?)""",
                (run_id, cat, b["ref"], b["ledger_total"], b["bank_total"], b["diff"], b["description"]))
    for e in result["duplicates"]:
        conn.execute(
            """INSERT INTO run_items(run_id,category,ref,description,employee,txn_date,amount)
               VALUES(?,?,?,?,?,?,?)""",
            (run_id, "duplicates", e["ref"], e["description"], e["employee"],
             e["txn_date"], e["amount"]))
    conn.commit()
    conn.close()
    return run_id


# ───────────── سجل التسويات ─────────────
@app.get("/runs")
async def list_runs(user: dict = Depends(current_user)):
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.*, u.full_name creator, a.full_name approver
           FROM runs r JOIN users u ON u.id=r.created_by
           LEFT JOIN users a ON a.id=r.approved_by
           ORDER BY r.id DESC LIMIT 100""").fetchall()
    conn.close()
    return {"runs": [dict(x) for x in rows]}


@app.get("/runs/{run_id}")
async def get_run(run_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close(); raise HTTPException(404, "التسوية غير موجودة")
    items = conn.execute("SELECT * FROM run_items WHERE run_id=?", (run_id,)).fetchall()
    conn.close()
    grouped = {}
    for it in items:
        grouped.setdefault(it["category"], []).append(dict(it))
    return {"run": dict(run), "items": grouped}


# ───────────── اعتماد المشرف (RBAC) ─────────────
@app.post("/runs/{run_id}/approve")
async def approve(run_id: int, user: dict = Depends(require_role("supervisor"))):
    conn = get_conn()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close(); raise HTTPException(404, "التسوية غير موجودة")
    if run["status"] == "approved":
        conn.close(); raise HTTPException(400, "التسوية معتمدة مسبقاً")
    conn.execute("UPDATE runs SET status='approved', approved_by=?, approved_at=? WHERE id=?",
                 (user["id"], datetime.utcnow().isoformat(), run_id))
    conn.commit(); conn.close()
    log_action(user["id"], user["username"], "approve", f"اعتماد التسوية #{run_id}")
    return {"ok": True, "status": "approved"}


# ───────────── سجل التدقيق (admin) ─────────────
@app.get("/audit")
async def audit(user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return {"audit": [dict(x) for x in rows]}


# ───────────── تقرير Excel ─────────────
@app.post("/report")
async def report(
    ledger: UploadFile = File(...), bank: UploadFile = File(...),
    ledger_sheet: str = Form(...), bank_sheet: str = Form(None),
    user: dict = Depends(current_user),
):
    led = _read(ledger, parse_ledger, ledger_sheet)
    bnk = _read(bank, parse_bank, bank_sheet or None)
    data = build_report(reconcile(led, bnk))
    log_action(user["id"], user["username"], "export", "تصدير تقرير Excel")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reconciliation_report.xlsx"})
