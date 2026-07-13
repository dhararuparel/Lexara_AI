import re
from functools import wraps
from flask import request, jsonify

# Predefined format regexes
EMAIL_REGEX = r"^[\w\.\-\+]+@[\w\.\-]+\.[a-zA-Z]{2,}$"
HEX_COLOR_REGEX = r"^#[0-9a-fA-F]{6}$"
ALPHANUM_REGEX = r"^[a-zA-Z0-9_\-]+$"
NAME_REGEX = r"^[a-zA-Z\s\-\.\'\’]+$"
URL_REGEX = r"^https?://[^\s/$.?#].[^\s]*$"
DIGITS_REGEX = r"^[0-9]+$"

def validate_data(data, schema):
    """
    Validates a data dictionary against a strict schema mapping.
    Returns (True, None) if valid, or (False, error_message) if invalid.
    """
    if not isinstance(data, dict):
        return False, "Request payload must be a JSON object"
        
    for field, rules in schema.items():
        is_optional = rules.get("optional", False)
        
        # Check presence
        if field not in data:
            if is_optional:
                continue
            return False, f"Missing required field: '{field}'"
            
        val = data[field]
        
        # Check nullability
        if val is None:
            if is_optional:
                continue
            return False, f"Field '{field}' cannot be null"
            
        # Check type
        expected_type = rules.get("type")
        if expected_type:
            # Special check for numbers (e.g. accepting int when type is float)
            if expected_type == float and isinstance(val, int):
                val = float(val)
            elif not isinstance(val, expected_type):
                return False, f"Field '{field}' must be of type {expected_type.__name__}"
                
        # String constraints
        if isinstance(val, str):
            min_len = rules.get("min_len")
            max_len = rules.get("max_len")
            if min_len is not None and len(val) < min_len:
                return False, f"Field '{field}' must be at least {min_len} characters long"
            if max_len is not None and len(val) > max_len:
                return False, f"Field '{field}' cannot exceed {max_len} characters"
                
            # Regex format check
            pattern = rules.get("regex")
            if pattern:
                if not re.match(pattern, val):
                    return False, f"Field '{field}' has an invalid format"
                    
        # Number constraints
        elif isinstance(val, (int, float)):
            min_val = rules.get("min_val")
            max_val = rules.get("max_val")
            if min_val is not None and val < min_val:
                return False, f"Field '{field}' must be greater than or equal to {min_val}"
            if max_val is not None and val > max_val:
                return False, f"Field '{field}' must be less than or equal to {max_val}"
                
        # Choices constraint
        choices = rules.get("choices")
        if choices is not None and val not in choices:
            return False, f"Field '{field}' must be one of: {list(choices)}"
            
    return True, None

def validate_json(schema):
    """Decorator to strictly validate Flask JSON request payload against a schema."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Request content type must be application/json"}), 400
                
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"error": "Invalid or missing JSON payload"}), 400
                
            is_valid, error_msg = validate_data(data, schema)
            if not is_valid:
                return jsonify({"error": error_msg}), 400
                
            return f(*args, **kwargs)
        return decorated
    return decorator

def validate_args(schema):
    """Decorator to strictly validate query parameters (GET arguments) against a schema."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            data = {}
            for field, rules in schema.items():
                expected_type = rules.get("type", str)
                val = request.args.get(field)
                if val is not None:
                    try:
                        # Safely cast string query params to expected types
                        if expected_type == int:
                            data[field] = int(val)
                        elif expected_type == float:
                            data[field] = float(val)
                        elif expected_type == bool:
                            data[field] = val.lower() in ("true", "1", "yes")
                        else:
                            data[field] = val
                    except ValueError:
                        return jsonify({"error": f"Query parameter '{field}' must be of type {expected_type.__name__}"}), 400
                else:
                    # Let validation rules verify if the parameter is required
                    pass
                    
            is_valid, error_msg = validate_data(data, schema)
            if not is_valid:
                return jsonify({"error": error_msg}), 400
                
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Schemas for Application Endpoints ───────────────────────────────

SIGNUP_SCHEMA = {
    "name": {"type": str, "min_len": 1, "max_len": 100, "regex": NAME_REGEX},
    "email": {"type": str, "min_len": 3, "max_len": 255, "regex": EMAIL_REGEX},
    "password": {"type": str, "min_len": 6, "max_len": 128}
}

LOGIN_SCHEMA = {
    "email": {"type": str, "min_len": 3, "max_len": 255, "regex": EMAIL_REGEX},
    "password": {"type": str, "min_len": 6, "max_len": 128},
    "totp_code": {"type": str, "optional": True, "min_len": 6, "max_len": 6, "regex": DIGITS_REGEX}
}

FORGOT_PASSWORD_SCHEMA = {
    "email": {"type": str, "min_len": 3, "max_len": 255, "regex": EMAIL_REGEX}
}

RESET_PASSWORD_SCHEMA = {
    "token": {"type": str, "min_len": 32, "max_len": 128, "regex": ALPHANUM_REGEX},
    "password": {"type": str, "min_len": 6, "max_len": 128}
}

RESET_PAGE_SCHEMA = {
    "token": {"type": str, "min_len": 32, "max_len": 128, "regex": ALPHANUM_REGEX}
}

TOTP_CODE_SCHEMA = {
    "code": {"type": str, "min_len": 6, "max_len": 6, "regex": DIGITS_REGEX}
}

UPDATE_PROFILE_SCHEMA = {
    "name": {"type": str, "min_len": 1, "max_len": 100, "regex": NAME_REGEX},
    "old_password": {"type": str, "optional": True, "min_len": 0, "max_len": 128},
    "new_password": {"type": str, "optional": True, "min_len": 6, "max_len": 128}
}

ASK_SCHEMA = {
    "question": {"type": str, "min_len": 1, "max_len": 2000},
    "mention_doc": {"type": str, "optional": True, "min_len": 0, "max_len": 255}
}

FOLDER_SCHEMA = {
    "name": {"type": str, "min_len": 1, "max_len": 100},
    "color": {"type": str, "optional": True, "min_len": 7, "max_len": 7, "regex": HEX_COLOR_REGEX}
}

COMPARE_SCHEMA = {
    "doc_a": {"type": str, "min_len": 1, "max_len": 255},
    "doc_b": {"type": str, "min_len": 1, "max_len": 255},
    "topic": {"type": str, "optional": True, "min_len": 1, "max_len": 255}
}

SEARCH_SCHEMA = {
    "q": {"type": str, "min_len": 1, "max_len": 255}
}

PROMPT_SCHEMA = {
    "title": {"type": str, "min_len": 1, "max_len": 100},
    "prompt": {"type": str, "min_len": 1, "max_len": 5000}
}

WORKSPACE_POST_SCHEMA = {
    "name": {"type": str, "min_len": 1, "max_len": 100},
    "description": {"type": str, "optional": True, "min_len": 0, "max_len": 1000}
}

WORKSPACE_PATCH_SCHEMA = {
    "name": {"type": str, "min_len": 1, "max_len": 100},
    "description": {"type": str, "optional": True, "min_len": 0, "max_len": 1000}
}

WORKSPACE_MEMBER_SCHEMA = {
    "email": {"type": str, "min_len": 3, "max_len": 255, "regex": EMAIL_REGEX},
    "role": {"type": str, "choices": {"admin", "editor", "viewer"}}
}

WORKSPACE_MEMBER_ROLE_SCHEMA = {
    "role": {"type": str, "choices": {"admin", "editor", "viewer"}}
}

INGEST_URL_SCHEMA = {
    "url": {"type": str, "min_len": 4, "max_len": 2048, "regex": URL_REGEX}
}

FEEDBACK_SCHEMA = {
    "rating": {"type": int, "choices": {1, -1}}
}

PIN_MSG_SCHEMA = {
    "chat_id": {"type": int, "min_val": 1}
}
