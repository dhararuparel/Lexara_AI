import os
import time
from functools import wraps
from flask import request, jsonify, current_app
from database import (
    get_auth_lockout_until,
    record_auth_failure,
    clear_auth_failures,
    check_sliding_window_rate_limit
)

SENSITIVE_AUTH_PATHS = {
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/forgot-password",
    "/api/auth/reset-password"
}

def get_ip():
    """Retrieves the client's actual IP address, respecting reverse proxy headers."""
    return request.remote_addr or "127.0.0.1"


def is_ip_blocked(ip) -> bool:
    """
    Checks if an IP is blocked due to excessive brute-force attempts.
    """
    from database import _conn
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT attempts, lockout_until FROM auth_failures WHERE key = %s",
                    (f"ip:{ip}",)
                )
                row = cur.fetchone()
                if row:
                    attempts, lockout_until = row
                    # Block IP if attempts >= 15 and lockout is still active
                    if attempts >= 15 and lockout_until:
                        if lockout_until.timestamp() > time.time():
                            return True
    except Exception:
        pass
    return False


def init_rate_limiter(app):
    """
    Registers before_request and after_request hooks to handle rate limiting globally.
    """
    
    @app.before_request
    def check_rate_limits():
        path = request.path
        
        # Bypass rate limiting for static assets and favicon
        if path.startswith("/static/") or path == "/favicon.ico":
            return None

        try:
            ip = get_ip()
            
            # 0. Global IP Block for Brute-Force Behavior
            if is_ip_blocked(ip):
                return jsonify({
                    "error": "Forbidden",
                    "message": "Access denied. Suspected brute-force activity detected from this IP address."
                }), 403

            if not app.config.get("RATE_LIMIT_ENABLED", True):
                return None
                
            # 1. Handle Sensitive Auth Routes (signup, login, password reset)
            # Check lockout first (before running the route)
            if path in SENSITIVE_AUTH_PATHS:
                email = None
                try:
                    if request.is_json:
                        data = request.get_json(silent=True) or {}
                        email = data.get("email", "").strip().lower() or None
                except Exception:
                    pass
                    
                keys = [f"ip:{ip}"]
                if email:
                    keys.append(f"email:{email}")
                    
                lockout_until = get_auth_lockout_until(keys)
                if lockout_until:
                    now_ts = time.time()
                    remaining = int(lockout_until.timestamp() - now_ts)
                    if remaining > 0:
                        return jsonify({
                            "error": f"Too many failed login attempts. Please try again in {remaining} seconds.",
                            "retry_after": remaining
                        }), 429
                return None  # Allow request to proceed to route
                
            # 2. Handle general endpoints (Public vs Authenticated)
            # Find matched view function
            view_func = None
            if request.endpoint:
                view_func = app.view_functions.get(request.endpoint)
                
            # Check if the view function is authenticated
            is_authenticated_route = False
            if view_func and getattr(view_func, "requires_auth", False):
                is_authenticated_route = True
                
            if is_authenticated_route:
                # Authenticated User Action limit
                # Look for session/token to extract user ID.
                user_id = None
                token = (
                    request.cookies.get("token") or
                    (request.headers.get("Authorization", "").replace("Bearer ", "") or None)
                )
                if token:
                    from auth import verify_token
                    payload = verify_token(token)
                    if payload:
                        user_id = payload.get("uid")
                        
                if user_id:
                    key = f"user:{user_id}"
                    limit = int(app.config.get("USER_LIMIT_MAX", 120))
                    window = int(app.config.get("USER_LIMIT_WINDOW_SECS", 60))
                else:
                    # Fallback to IP if token is invalid/missing (will be rejected by auth anyway, but limit it)
                    key = f"ip:{ip}"
                    limit = int(app.config.get("PUBLIC_LIMIT_MAX", 30))
                    window = int(app.config.get("PUBLIC_LIMIT_WINDOW_SECS", 60))
            else:
                # Public Endpoint limit
                key = f"ip:{ip}"
                limit = int(app.config.get("PUBLIC_LIMIT_MAX", 30))
                window = int(app.config.get("PUBLIC_LIMIT_WINDOW_SECS", 60))
                
            # Enforce rate limit
            if check_sliding_window_rate_limit(key, limit, window):
                return jsonify({
                    "error": "Too many requests. Please try again later.",
                    "retry_after": window
                }), 429
                
        except Exception as e:
            app.logger.error(f"Rate limiting check bypassed due to internal error: {e}")
            
        return None

    @app.after_request
    def log_auth_status(response):
        if not app.config.get("RATE_LIMIT_ENABLED", True):
            return response
            
        path = request.path
        if path in SENSITIVE_AUTH_PATHS:
            ip = get_ip()
            email = None
            try:
                if request.is_json:
                    data = request.get_json(silent=True) or {}
                    email = data.get("email", "").strip().lower() or None
            except Exception:
                pass
                
            keys = [f"ip:{ip}"]
            if email:
                keys.append(f"email:{email}")
                
            # Check success / failure based on status code
            try:
                if response.status_code in (200, 201, 204, 302):
                    clear_auth_failures(keys)
                else:
                    base = int(app.config.get("AUTH_BACKOFF_BASE_SECS", 5))
                    factor = int(app.config.get("AUTH_BACKOFF_FACTOR", 2))
                    max_secs = int(app.config.get("AUTH_BACKOFF_MAX_SECS", 3600))
                    record_auth_failure(keys, base, factor, max_secs)
            except Exception as e:
                app.logger.error(f"Failed to record auth status: {e}")
                
        return response


# ── Optional Decorators (Compatibility Fallback) ─────────────────────

def limit_auth(f):
    """
    Decorator for stricter rate limiting on authentication routes.
    Employs per-IP and per-account tracking with exponential backoff on failure.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        enabled = current_app.config.get("RATE_LIMIT_ENABLED", True)
        if not enabled:
            return f(*args, **kwargs)
            
        ip = get_ip()
        email = None
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                email = data.get("email", "").strip().lower() or None
        except Exception:
            pass
            
        keys = [f"ip:{ip}"]
        if email:
            keys.append(f"email:{email}")
            
        lockout_until = get_auth_lockout_until(keys)
        if lockout_until:
            now_ts = time.time()
            remaining = int(lockout_until.timestamp() - now_ts)
            if remaining > 0:
                return jsonify({
                    "error": f"Too many failed login attempts. Please try again in {remaining} seconds.",
                    "retry_after": remaining
                }), 429
                
        response = f(*args, **kwargs)
        
        status_code = 200
        if hasattr(response, "status_code"):
            status_code = response.status_code
        elif isinstance(response, tuple) and len(response) > 1:
            if isinstance(response[1], int):
                status_code = response[1]
                
        if status_code in (200, 201, 204, 302):
            clear_auth_failures(keys)
        else:
            base = int(current_app.config.get("AUTH_BACKOFF_BASE_SECS", 5))
            factor = int(current_app.config.get("AUTH_BACKOFF_FACTOR", 2))
            max_secs = int(current_app.config.get("AUTH_BACKOFF_MAX_SECS", 3600))
            record_auth_failure(keys, base, factor, max_secs)
            
        return response
    return decorated

def limit_public(f):
    """
    Decorator for moderate rate limiting on public endpoints.
    Tracks requests per-IP over a configurable sliding window.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        enabled = current_app.config.get("RATE_LIMIT_ENABLED", True)
        if not enabled:
            return f(*args, **kwargs)
            
        ip = get_ip()
        limit = int(current_app.config.get("PUBLIC_LIMIT_MAX", 30))
        window = int(current_app.config.get("PUBLIC_LIMIT_WINDOW_SECS", 60))
        
        key = f"ip:{ip}"
        if check_sliding_window_rate_limit(key, limit, window):
            return jsonify({
                "error": "Too many requests. Please try again later.",
                "retry_after": window
            }), 429
            
        return f(*args, **kwargs)
    return decorated

def limit_user(f):
    """
    Decorator for looser rate limiting on authenticated routes.
    Tracks requests per User ID.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        enabled = current_app.config.get("RATE_LIMIT_ENABLED", True)
        if not enabled:
            return f(*args, **kwargs)
            
        current_user = kwargs.get("current_user")
        if current_user and "id" in current_user:
            key = f"user:{current_user['id']}"
        else:
            key = f"ip:{get_ip()}"
            
        limit = int(current_app.config.get("USER_LIMIT_MAX", 120))
        window = int(current_app.config.get("USER_LIMIT_WINDOW_SECS", 60))
        
        if check_sliding_window_rate_limit(key, limit, window):
            return jsonify({
                "error": "Too many actions. Please try again later.",
                "retry_after": window
            }), 429
            
        return f(*args, **kwargs)
    return decorated
