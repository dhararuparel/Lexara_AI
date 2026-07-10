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


def verify_token(token: str):
    try:
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


