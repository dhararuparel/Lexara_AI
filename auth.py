"""
Auth helpers — password hashing, JWT tokens, route decorator.
"""

import hashlib
import hmac
import base64
import json
import time
import os
from functools import wraps
from flask import request, jsonify
from database import get_user_by_id

SECRET = os.getenv("SECRET_KEY", "Lexara-secret-change-in-production")


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def check_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(h, hashlib.sha256((salt + password).encode()).hexdigest())
    except Exception:
        return False


def generate_token(user_id: int, email: str) -> str:
    payload = {"uid": user_id, "email": email, "exp": int(time.time()) + 72 * 3600}
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig  = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def is_token_blacklisted(token: str) -> bool:
    """
    Checks if a token has been blacklisted.
    Supports Redis (if REDIS_URL is configured) with fallback to database.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.Redis.from_url(redis_url)
            return r.exists(f"bl:{token_hash}") > 0
        except Exception:
            pass
            
    from database import _conn
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM token_blocklist WHERE token_hash = %s",
                    (token_hash,)
                )
                return cur.fetchone() is not None
    except Exception:
        pass
    return False


def blacklist_token(token: str, expires_at: int):
    """
    Blacklists a token until its expiration time.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    ttl = max(int(expires_at - time.time()), 0)
    if ttl <= 0:
        return
        
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.Redis.from_url(redis_url)
            r.setex(f"bl:{token_hash}", ttl, "1")
            return
        except Exception:
            pass
            
    from database import _conn
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS token_blocklist (
                        token_hash VARCHAR(64) PRIMARY KEY,
                        blacklisted_at TIMESTAMP DEFAULT NOW(),
                        expires_at TIMESTAMP
                    )
                """)
                import datetime
                exp_dt = datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                cur.execute("""
                    INSERT INTO token_blocklist (token_hash, expires_at)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (token_hash, exp_dt))
            conn.commit()
    except Exception:
        pass


def verify_token(token: str):
    try:
        if is_token_blacklisted(token):
            return None
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data + "=="))
        if payload["exp"] < time.time():
            return None
        return payload
    except Exception:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.cookies.get("token") or
            (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
        )
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        user = get_user_by_id(payload["uid"])
        if not user:
            return jsonify({"error": "User not found"}), 401
        return f(*args, current_user=user, **kwargs)
    decorated.requires_auth = True
    return decorated


