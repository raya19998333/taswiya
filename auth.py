# -*- coding: utf-8 -*-
"""
طبقة المصادقة والصلاحيات | Auth & RBAC
- تجزئة كلمات المرور: PBKDF2-HMAC-SHA256 (مكتبة قياسية، بلا اعتماديات خارجية).
- الجلسات: رموز عشوائية تُخزَّن في قاعدة البيانات وتنتهي بعد 8 ساعات.
- الأدوار: admin > supervisor > entry.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, Depends
from database import get_conn

ITER = 200_000
SESSION_HOURS = 8
ROLE_RANK = {"entry": 1, "supervisor": 2, "admin": 3}


def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITER).hex()
    return h, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, password_hash)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    conn = get_conn()
    conn.execute("INSERT INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                 (token, user_id, now.isoformat(),
                  (now + timedelta(hours=SESSION_HOURS)).isoformat()))
    conn.commit()
    conn.close()
    return token


def login(username: str, password: str):
    conn = get_conn()
    u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not u or not verify_password(password, u["password_hash"], u["salt"]):
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غير صحيحة")
    token = create_session(u["id"])
    return token, dict(u)


def current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "مطلوب تسجيل الدخول")
    token = authorization.split(" ", 1)[1]
    conn = get_conn()
    s = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
    if not s or datetime.fromisoformat(s["expires_at"]) < datetime.utcnow():
        conn.close()
        raise HTTPException(401, "انتهت الجلسة، يرجى تسجيل الدخول مجدداً")
    u = conn.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
    conn.close()
    return dict(u)


def require_role(min_role: str):
    """تبعية تتحقق أن دور المستخدم لا يقل عن المطلوب."""
    def dep(user: dict = Depends(current_user)) -> dict:
        if ROLE_RANK.get(user["role"], 0) < ROLE_RANK[min_role]:
            raise HTTPException(403, "ليست لديك صلاحية لهذا الإجراء")
        return user
    return dep
