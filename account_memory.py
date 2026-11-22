"""Per-account authentication and memory storage for XEMEX.AI.

Supabase Auth issues the user JWT. Every database request uses that user's
JWT, so the user_memories table's auth.uid() RLS policies remain in force.
A UUID-named local JSON copy provides the second storage layer.
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
USER_DATA_DIR = Path(os.environ.get("XEMEX_USER_DATA_DIR", "user_data"))
REQUEST_TIMEOUT = 20
_uuid_pattern = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_file_lock = threading.RLock()


def _headers(access_token=None, prefer=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.")
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = "Bearer " + access_token
    else:
        headers["Authorization"] = "Bearer " + SUPABASE_KEY
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _response_json(response):
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok:
        # Do not log or return request headers, passwords, or bearer tokens.
        message = data.get("msg") or data.get("message") or data.get("error_description")
        if not message:
            message = "Supabase request failed (HTTP {}).".format(response.status_code)
        raise RuntimeError(str(message)[:300])
    return data


def sign_up(email, password):
    email = (email or "").strip().lower()
    password = password or ""
    if not email or "@" not in email:
        return None, "Enter a valid email address."
    if len(password) < 8:
        return None, "Use a password with at least 8 characters."
    try:
        response = requests.post(
            SUPABASE_URL + "/auth/v1/signup",
            headers=_headers(),
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        data = _response_json(response)
        session = data.get("session")
        if not session or not session.get("access_token"):
            return None, "Account created. Check your email to confirm it, then sign in."
        user = data.get("user") or {}
        return {
            "access_token": session["access_token"],
            "refresh_token": session.get("refresh_token", ""),
            "user_id": user.get("id"),
            "email": user.get("email", email),
            "expires_at": time.time() + max(0, int(session.get("expires_in", 3600)) - 60),
        }, "Account created. You are signed in."
    except (requests.RequestException, RuntimeError) as error:
        return None, "Sign-up failed: {}".format(error)


def sign_in(email, password):
    email = (email or "").strip().lower()
    password = password or ""
    if not email or not password:
        return None, "Enter your email and password."
    try:
        response = requests.post(
            SUPABASE_URL + "/auth/v1/token?grant_type=password",
            headers=_headers(),
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        data = _response_json(response)
        user = data.get("user") or {}
        user_id = user.get("id")
        token = data.get("access_token")
        if not user_id or not token:
            return None, "Supabase did not return a valid sign-in session."
        return {
            "access_token": token,
            "refresh_token": data.get("refresh_token", ""),
            "user_id": user_id,
            "email": user.get("email", email),
            "expires_at": time.time() + max(0, int(data.get("expires_in", 3600)) - 60),
        }, "Signed in successfully."
    except (requests.RequestException, RuntimeError) as error:
        return None, "Sign-in failed: {}".format(error)


def refresh_session(session):
    if not isinstance(session, dict) or not session.get("refresh_token"):
        return None
    try:
        response = requests.post(
            SUPABASE_URL + "/auth/v1/token?grant_type=refresh_token",
            headers=_headers(),
            json={"refresh_token": session["refresh_token"]},
            timeout=REQUEST_TIMEOUT,
        )
        data = _response_json(response)
        user = data.get("user") or {}
        if not data.get("access_token"):
            return None
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", session["refresh_token"]),
            "user_id": user.get("id") or session.get("user_id"),
            "email": user.get("email") or session.get("email", ""),
            "expires_at": time.time() + max(0, int(data.get("expires_in", 3600)) - 60),
        }
    except (requests.RequestException, RuntimeError):
        return None


def ensure_valid_session(session):
    """Refresh a Supabase session shortly before expiry.

    Returns (session, status). A failed refresh never silently reuses an
    expired access token; the caller must ask the user to sign in again.
    """
    if not isinstance(session, dict) or not session.get("access_token"):
        return None, "Please sign in again."
    expires_at = session.get("expires_at")
    if isinstance(expires_at, (int, float)) and expires_at > time.time():
        return session, "Session active."
    refreshed = refresh_session(session)
    if not refreshed or refreshed.get("user_id") != session.get("user_id"):
        return None, "Your session expired. Please sign in again."
    return refreshed, "Your session was securely renewed."


def sign_out(session):
    if not isinstance(session, dict) or not session.get("access_token"):
        return
    try:
        requests.post(
            SUPABASE_URL + "/auth/v1/logout",
            headers=_headers(session["access_token"]),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        pass


def _user_file(user_id):
    user_id = str(user_id or "")
    if not _uuid_pattern.fullmatch(user_id):
        raise ValueError("Invalid account identifier.")
    return USER_DATA_DIR / (user_id.lower() + ".json")


def default_user_memory():
    return {
        "profile": {"name": ""},
        "facts": [],
        "chat_history": [],
        "emotional_state": {
            "pleasure": 0.1,
            "arousal": 0.0,
            "trust": 0.2,
            "attachment": 0.1,
            "self_worth": 0.2,
            "humor_warmth": 0.2,
        },
        "interaction_count": 0,
        "tutor_settings": {"age_group": "elementary", "subject": "general learning", "learning_goal": "understand the topic"},
        "learning_progress": [],
        "learners": [],
        "updated_at": None,
    }


def _normalize_memory(data):
    defaults = default_user_memory()
    if not isinstance(data, dict):
        data = {}
    result = defaults
    profile = data.get("profile")
    if isinstance(profile, dict) and isinstance(profile.get("name"), str):
        result["profile"]["name"] = profile["name"][:100]
    for key in ("facts", "chat_history"):
        value = data.get(key)
        if isinstance(value, list):
            result[key] = value[-100:]
    state = data.get("emotional_state")
    if isinstance(state, dict):
        for key in result["emotional_state"]:
            value = state.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result["emotional_state"][key] = max(-1.0, min(1.0, float(value)))
    count = data.get("interaction_count")
    if isinstance(count, int) and count >= 0:
        result["interaction_count"] = count
    tutor_settings = data.get("tutor_settings")
    if isinstance(tutor_settings, dict):
        for key, limit in (("age_group", 40), ("subject", 100), ("learning_goal", 250)):
            value = tutor_settings.get(key)
            if isinstance(value, str):
                result["tutor_settings"][key] = value.strip()[:limit]
    progress = data.get("learning_progress")
    if isinstance(progress, list):
        result["learning_progress"] = [
            item for item in progress[-100:]
            if isinstance(item, dict)
        ]
    learners = data.get("learners")
    if isinstance(learners, list):
        cleaned_learners = []
        seen_ids = set()
        for learner in learners[-20:]:
            if not isinstance(learner, dict):
                continue
            learner_id = str(learner.get("id") or "")[:64]
            learner_name = str(learner.get("name") or "").strip()[:80]
            age_group = str(learner.get("age_group") or "elementary")[:40]
            if not learner_id or not learner_name or learner_id in seen_ids:
                continue
            seen_ids.add(learner_id)
            controls = learner.get("parent_controls")
            if not isinstance(controls, dict):
                controls = {}
            allow_practice = controls.get("allow_practice", True)
            allow_hints = controls.get("allow_hints", True)
            daily_limit = controls.get("daily_activity_limit", 20)
            if not isinstance(allow_practice, bool):
                allow_practice = True
            if not isinstance(allow_hints, bool):
                allow_hints = True
            if daily_limit not in (0, 5, 10, 15, 20, 30):
                daily_limit = 20
            pin_record = learner.get("student_pin")
            if not isinstance(pin_record, dict):
                pin_record = None
            else:
                salt = pin_record.get("salt")
                digest = pin_record.get("hash")
                iterations = pin_record.get("iterations", 240000)
                if (not isinstance(salt, str) or len(salt) != 32
                        or not isinstance(digest, str) or len(digest) != 64
                        or not isinstance(iterations, int) or iterations < 100000 or iterations > 500000):
                    pin_record = None
                else:
                    pin_record = {"salt": salt, "hash": digest, "iterations": iterations}
            attempts = learner.get("pin_failed_attempts", 0)
            if not isinstance(attempts, int) or attempts < 0:
                attempts = 0
            locked_until = learner.get("pin_locked_until", 0)
            if not isinstance(locked_until, (int, float)):
                locked_until = 0
            cleaned_learners.append({
                "id": learner_id,
                "name": learner_name,
                "age_group": age_group,
                "age": (learner.get("age") if isinstance(learner.get("age"), int) and not isinstance(learner.get("age"), bool) and 0 <= learner.get("age") <= 120 else None),
                "is_self": learner.get("is_self") is True,
                "student_pin": pin_record,
                "pin_failed_attempts": min(attempts, 5),
                "pin_locked_until": max(0, float(locked_until)),
                "parent_controls": {
                    "allow_practice": allow_practice,
                    "allow_hints": allow_hints,
                    "daily_activity_limit": daily_limit,
                },
            })
        result["learners"] = cleaned_learners
    registration_setup = data.get("registration_setup")
    if isinstance(registration_setup, dict):
        setup_for = registration_setup.get("setup_for")
        age = registration_setup.get("learner_age")
        age_group = registration_setup.get("age_group")
        if setup_for in ("self", "child") and isinstance(age, int) and not isinstance(age, bool) and 3 <= age <= 120:
            result["registration_setup"] = {
                "setup_for": setup_for,
                "learner_age": age,
                "age_group": str(age_group or "elementary")[:40],
                "adult_learner_consent": registration_setup.get("adult_learner_consent") is True,
                "created_at": str(registration_setup.get("created_at") or "")[:40],
                "self_learner_id": str(registration_setup.get("self_learner_id") or "")[:64],
            }
    result["updated_at"] = data.get("updated_at")
    return result


def load_user_memory(session):
    if not isinstance(session, dict):
        return default_user_memory(), "No signed-in account."
    user_id = session.get("user_id")
    token = session.get("access_token")
    if not _uuid_pattern.fullmatch(str(user_id or "")) or not token:
        return default_user_memory(), "Your sign-in session is invalid. Please sign in again."

    # Supabase is the primary shared durable store; local JSON is the second copy.
    try:
        response = requests.get(
            SUPABASE_URL + "/rest/v1/user_memories",
            headers=_headers(token),
            params={"select": "memory_data", "user_id": "eq." + str(user_id), "limit": "1"},
            timeout=REQUEST_TIMEOUT,
        )
        rows = _response_json(response)
        if rows:
            data = _normalize_memory(rows[0].get("memory_data"))
            _write_local(user_id, data)
            return data, "Memory loaded from your account."
    except (requests.RequestException, RuntimeError, ValueError) as error:
        remote_error = str(error)
    else:
        remote_error = "No cloud memory found yet."

    try:
        local = _read_local(user_id)
        if local is not None:
            return _normalize_memory(local), "Loaded your local saved memory. Cloud sync needs attention."
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return default_user_memory(), "Starting a new private memory. " + remote_error


def _read_local(user_id):
    path = _user_file(user_id)
    with _file_lock:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def _write_local(user_id, data):
    path = _user_file(user_id)
    with _file_lock:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(str(temporary), str(path))


def save_user_memory(session, memory_data):
    if not isinstance(session, dict):
        return False, "Sign in before saving memory."
    user_id = session.get("user_id")
    token = session.get("access_token")
    if not _uuid_pattern.fullmatch(str(user_id or "")) or not token:
        return False, "Your sign-in session is invalid. Please sign in again."

    data = _normalize_memory(memory_data)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    local_error = None
    cloud_error = None
    try:
        _write_local(user_id, data)
    except (OSError, ValueError) as error:
        local_error = str(error)

    try:
        response = requests.post(
            SUPABASE_URL + "/rest/v1/user_memories?on_conflict=user_id",
            headers=_headers(token, "resolution=merge-duplicates,return=minimal"),
            json={"user_id": user_id, "memory_data": data, "updated_at": data["updated_at"]},
            timeout=REQUEST_TIMEOUT,
        )
        _response_json(response)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        cloud_error = str(error)

    if not local_error and not cloud_error:
        return True, "Your private memory was saved locally and to your account."
    if not local_error:
        return True, "Saved locally. Cloud sync needs attention: " + str(cloud_error)
    if not cloud_error:
        return True, "Saved to your account. Local backup failed: " + str(local_error)
    return False, "Memory could not be saved. Local: {}; Cloud: {}".format(local_error, cloud_error)
