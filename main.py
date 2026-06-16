# -*- coding: utf-8 -*-
"""
نظام التسوية البنكية الآلية — الإصدار الثاني | FastAPI Backend v2
يضيف: مصادقة + صلاحيات (RBAC) + حفظ في قاعدة بيانات + سجل تسويات + اعتماد المشرف + سجل تدقيق.
"""
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import openpyxl
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from reconciliation import parse_ledger, parse_bank, reconcile
from report import build_report
from database import init_db, get_conn, log_action
from auth import login, current_user, require_role

app = FastAPI(title="نظام التسوية البنكية الآلية")
BASE = Path(__file__).parent
STATIC_DIR = BASE / "static"
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
init_db()

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _read(upload: UploadFile, parser, sheet=None):
    try:
        tmp = io.BytesIO(upload.file.read())
        return parser(tmp, sheet) if sheet is not None else parser(tmp)
    except Exception as e:
        raise HTTPException(400, f"تعذّر قراءة الملف {upload.filename}: {e}")


# ───────────── الواجهة ─────────────
@app.get("/", response_class=HTMLResponse)
def home():
    login_file = STATIC_DIR / "login.html"
    if login_file.exists():
        return login_file.read_text(encoding="utf-8")
    return "<h1>Error: login.html not found</h1>"

@app.get("/app", response_class=HTMLResponse)
def app_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>Error: index.html not found</h1>"


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


@app.delete("/runs/{run_id}")
async def delete_run(run_id: int, user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close(); raise HTTPException(404, "التسوية غير موجودة")
    conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
    conn.commit(); conn.close()
    log_action(user["id"], user["username"], "delete", f"حذف التسوية #{run_id}")
    return {"ok": True}


@app.patch("/runs/{run_id}")
async def update_run(run_id: int, payload: dict, user: dict = Depends(require_role("admin"))):
    allowed = {"ledger_name", "bank_name", "sheet", "status"}
    data = {k: v for k, v in payload.items() if k in allowed and v is not None}
    if not data:
        raise HTTPException(400, "لا توجد بيانات للتعديل")

    conn = get_conn()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close(); raise HTTPException(404, "التسوية غير موجودة")

    updates = []
    params = []
    if "ledger_name" in data:
        updates.append("ledger_name = ?")
        params.append(data["ledger_name"])
    if "bank_name" in data:
        updates.append("bank_name = ?")
        params.append(data["bank_name"])
    if "sheet" in data:
        updates.append("sheet = ?")
        params.append(data["sheet"])
    if "status" in data:
        new_status = data["status"].lower()
        if new_status not in {"draft", "approved"}:
            conn.close(); raise HTTPException(400, "الحالة غير صالحة")
        if new_status == "approved":
            updates.append("status = 'approved'")
            updates.append("approved_by = ?")
            updates.append("approved_at = ?")
            params.extend((user["id"], datetime.utcnow().isoformat()))
        else:
            updates.append("status = 'draft'")
            updates.append("approved_by = NULL")
            updates.append("approved_at = NULL")
    if not updates:
        conn.close(); raise HTTPException(400, "لا توجد حقول صالحة للتعديل")

    query = f"UPDATE runs SET {', '.join(updates)} WHERE id=?"
    params.append(run_id)
    conn.execute(query, tuple(params))
    conn.commit(); conn.close()
    log_action(user["id"], user["username"], "update", f"تعديل التسوية #{run_id}")
    return {"ok": True}


# ───────────── سجل التدقيق (admin) ─────────────
@app.get("/audit")
async def audit(user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return {"audit": [dict(x) for x in rows]}


# ───────────── سندات الصرف (الأرشيف) ─────────────
@app.post("/vouchers")
async def create_voucher(
    voucher_no: str = Form(None),
    voucher_date: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("ر.ع"),
    beneficiary: str = Form(...),
    description: str = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(current_user),
):
    file_path = None
    file_name = None
    if file and file.filename:
        ext = Path(file.filename).suffix
        if ext.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            raise HTTPException(400, "صيغة الملف غير مدعومة (PDF أو صورة فقط)")
        safe_name = f"{uuid.uuid4().hex}{ext}"
        contents = await file.read()
        (UPLOAD_DIR / safe_name).write_bytes(contents)
        file_path = safe_name
        file_name = file.filename

    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO vouchers(voucher_no,voucher_date,amount,currency,beneficiary,
           description,file_path,file_name,created_by,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (voucher_no, voucher_date, amount, currency, beneficiary, description,
         file_path, file_name, user["id"], datetime.utcnow().isoformat()))
    voucher_id = cur.lastrowid
    conn.commit(); conn.close()
    log_action(user["id"], user["username"], "voucher_create", f"إضافة سند #{voucher_id}")
    return {"ok": True, "id": voucher_id}


@app.get("/vouchers")
async def list_vouchers(
    q: str = None, date_from: str = None, date_to: str = None,
    amount_min: float = None, amount_max: float = None, status: str = None,
    user: dict = Depends(current_user),
):
    conn = get_conn()
    sql = """SELECT v.*, u.full_name creator FROM vouchers v
             JOIN users u ON u.id=v.created_by WHERE 1=1"""
    params = []
    if q:
        sql += " AND (v.voucher_no LIKE ? OR v.beneficiary LIKE ? OR v.description LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if date_from:
        sql += " AND v.voucher_date >= ?"; params.append(date_from)
    if date_to:
        sql += " AND v.voucher_date <= ?"; params.append(date_to)
    if amount_min is not None:
        sql += " AND v.amount >= ?"; params.append(amount_min)
    if amount_max is not None:
        sql += " AND v.amount <= ?"; params.append(amount_max)
    if status:
        sql += " AND v.status = ?"; params.append(status)
    sql += " ORDER BY v.id DESC LIMIT 200"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"vouchers": [dict(x) for x in rows]}


@app.get("/vouchers/{voucher_id}/file")
async def get_voucher_file(voucher_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)).fetchone()
    conn.close()
    if not v or not v["file_path"]:
        raise HTTPException(404, "لا يوجد ملف مرفق لهذا السند")
    path = UPLOAD_DIR / v["file_path"]
    if not path.exists():
        raise HTTPException(404, "الملف غير موجود على الخادم")
    return FileResponse(path, filename=v["file_name"])


@app.patch("/vouchers/{voucher_id}")
async def update_voucher_status(
    voucher_id: int, payload: dict, user: dict = Depends(require_role("supervisor"))
):
    new_status = (payload or {}).get("status")
    if new_status not in {"draft", "approved", "cancelled"}:
        raise HTTPException(400, "حالة غير صالحة")
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)).fetchone()
    if not v:
        conn.close(); raise HTTPException(404, "السند غير موجود")
    conn.execute("UPDATE vouchers SET status=? WHERE id=?", (new_status, voucher_id))
    conn.commit(); conn.close()
    log_action(user["id"], user["username"], "voucher_update",
               f"تحديث حالة السند #{voucher_id} إلى {new_status}")
    return {"ok": True}


@app.delete("/vouchers/{voucher_id}")
async def delete_voucher(voucher_id: int, user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)).fetchone()
    if not v:
        conn.close(); raise HTTPException(404, "السند غير موجود")
    conn.execute("DELETE FROM vouchers WHERE id=?", (voucher_id,))
    conn.commit(); conn.close()
    if v["file_path"]:
        (UPLOAD_DIR / v["file_path"]).unlink(missing_ok=True)
    log_action(user["id"], user["username"], "voucher_delete", f"حذف السند #{voucher_id}")
    return {"ok": True}


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
