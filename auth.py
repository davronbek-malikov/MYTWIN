from __future__ import annotations
import asyncio
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import bcrypt as _bcrypt
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

import config
from database.db import get_pool
from utils.logger import logger

_serial = URLSafeTimedSerializer(config.SECRET_KEY)

# ── Password ──────────────────────────────────────────────────────────────

def hash_password(p: str) -> str:
    return _bcrypt.hashpw(p.encode(), _bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

# ── Session cookie ────────────────────────────────────────────────────────

def create_session(user_id: int) -> str:
    return _serial.dumps(user_id, salt="session")

def verify_session(token: str, max_age: int = 86400 * 7) -> int | None:
    try:
        return _serial.loads(token, salt="session", max_age=max_age)
    except (SignatureExpired, BadSignature, Exception):
        return None

# ── DB helpers ────────────────────────────────────────────────────────────

async def any_user_exists() -> bool:
    try:
        from database.db import init_db
        await init_db()          # ensure auth_users table exists
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM auth_users")
            return (row["cnt"] if row else 0) > 0
    except Exception:
        return False             # table missing → allow signup

async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM auth_users WHERE email = $1", email.lower())
        return dict(row) if row else None

async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM auth_users WHERE id = $1", user_id)
        return dict(row) if row else None

async def create_user(email: str, password: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchrow("SELECT id FROM auth_users WHERE email = $1", email.lower())
        if exists:
            raise ValueError("Email already registered")
        row = await conn.fetchrow(
            "INSERT INTO auth_users (email, password_hash) VALUES ($1,$2) RETURNING *",
            email.lower(), hash_password(password),
        )
        return dict(row)

async def change_password(user_id: int, old_pw: str, new_pw: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT password_hash FROM auth_users WHERE id = $1", user_id)
        if not row or not verify_password(old_pw, row["password_hash"]):
            return False
        await conn.execute(
            "UPDATE auth_users SET password_hash = $1 WHERE id = $2",
            hash_password(new_pw), user_id,
        )
        return True

# ── Password reset ────────────────────────────────────────────────────────

async def create_reset_token(email: str) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM auth_users WHERE email = $1", email.lower())
        if not row:
            logger.warning(f"Password reset requested for unknown email: {email}")
            return None
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        await conn.execute(
            "UPDATE auth_users SET reset_token=$1, reset_expiry=$2 WHERE email=$3",
            token, expiry, email.lower(),
        )
        logger.info(f"Reset token created for: {email}")
        return token

async def verify_reset_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM auth_users WHERE reset_token=$1 AND reset_expiry > NOW()", token
        )
        return dict(row) if row else None

async def apply_reset(token: str, new_pw: str) -> bool:
    user = await verify_reset_token(token)
    if not user:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE auth_users SET password_hash=$1, reset_token=NULL, reset_expiry=NULL WHERE id=$2",
            hash_password(new_pw), user["id"],
        )
    return True

# ── Gmail email sender ────────────────────────────────────────────────────

async def send_reset_email(to: str, reset_url: str) -> None:
    if not config.GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_APP_PASSWORD not set in .env")
    sender = config.ADMIN_EMAIL
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "My Twin — Password Reset"
    msg["From"] = f"My Twin <{sender}>"
    msg["To"] = to
    html = f"""<div style="font-family:'DM Sans',sans-serif;max-width:480px;margin:40px auto;padding:40px;
    background:#fff;border-radius:16px;border:1px solid #e2e8f0;box-shadow:0 4px 16px rgba(0,0,0,0.08)">
    <div style="font-size:32px;margin-bottom:12px">🤖</div>
    <h2 style="color:#0f172a;font-size:22px;margin-bottom:8px">Reset your password</h2>
    <p style="color:#475569;font-size:15px;line-height:1.6;margin-bottom:24px">
      Click below to reset your My Twin password. This link expires in <strong>1 hour</strong>.
    </p>
    <a href="{reset_url}" style="display:inline-block;padding:13px 28px;background:#0ea5e9;color:#fff;
    border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">Reset Password →</a>
    <p style="color:#94a3b8;font-size:12px;margin-top:24px">If you didn't request this, ignore this email.</p>
    </div>"""
    msg.attach(MIMEText(html, "html"))
    def _send():
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
            s.login(sender, config.GMAIL_APP_PASSWORD)
            s.sendmail(sender, to, msg.as_string())

    await asyncio.to_thread(_send)
