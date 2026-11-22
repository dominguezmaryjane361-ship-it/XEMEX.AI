"""Independent student credentials and private learning memory.

All student-account table access is server-side and requires the Supabase
service-role key. Never expose that key to a browser or Gradio component.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone

import requests

import account_memory as parent_store

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SESSION_SECRET = os.environ.get("XEMEX_STUDENT_SESSION_SECRET", "").encode("utf-8")
TIMEOUT = 20
ITERATIONS = 310_000
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,23}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _headers():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Student accounts need SUPABASE_SERVICE_ROLE_KEY configured on the server.")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": "Bearer " + SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }


def _request(method, path, *, params=None, payload=None, prefer=None):
    headers = _headers()
    if prefer:
        headers["Prefer"] = prefer
    response = requests.request(
        method, SUPABASE_URL + "/rest/v1/" + path,
        headers=headers, params=params, json=payload, timeout=TIMEOUT,
    )
    try:
        body = response.json() if response.content else []
    except ValueError:
        body = []
    if not response.ok:
        message = body.get("message") if isinstance(body, dict) else None
        raise RuntimeError((message or "Student account storage failed (HTTP {}).".format(response.status_code))[:250])
    return body


def _password_record(password):
    password = str(password or "")
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Use a student password with 10 to 128 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex(), digest.hex(), ITERATIONS


def _verify_password(password, record):
    try:
        salt = bytes.fromhex(record["password_salt"])
        expected = record["password_hash"]
        rounds = int(record["password_iterations"])
        if len(salt) != 16 or not re.fullmatch(r"[0-9a-f]{64}", expected):
            return False
        if rounds < 100_000 or rounds > 500_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", str(password or "").encode(), salt, rounds).hex()
        return hmac.compare_digest(actual, expected)
    except (KeyError, TypeError, ValueError):
        return False


def _student_defaults(username, email=None, learner_name="", age_group="elementary"):
    return {
        "profile": {"username": username, "email": email or "", "learner_name": learner_name, "age_group": age_group},
        "facts": [],
        "chat_history": [],
        "learning_progress": [],
        "interaction_count": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _session_signing_secret():
    if len(SESSION_SECRET) < 32:
        raise RuntimeError("Set XEMEX_STUDENT_SESSION_SECRET to a separate random secret of at least 32 characters.")
    return SESSION_SECRET


def _issue_session(record):
    secret = _session_signing_secret()
    payload = {
        "sid": record["id"],
        "pid": record["parent_user_id"],
        "lid": record["learner_id"],
        "exp": int(time.time()) + 8 * 60 * 60,
        "nonce": secrets.token_hex(12),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()
    return {"token": raw + "." + signature, "student_id": record["id"],
            "parent_user_id": record["parent_user_id"], "learner_id": record["learner_id"],
            "expires_at": payload["exp"]}


def validate_student_session(session):
    if not isinstance(session, dict) or not isinstance(session.get("token"), str):
        return None
    try:
        raw, supplied = session["token"].rsplit(".", 1)
        secret = _session_signing_secret()
        expected = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            return None
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        if payload.get("sid") != session.get("student_id"):
            return None
        if payload.get("pid") != session.get("parent_user_id"):
            return None
        if payload.get("lid") != session.get("learner_id"):
            return None
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def create_student_account(parent_session, learner_id, username, password, email=None):
    parent_session, session_status = parent_store.ensure_valid_session(parent_session)
    if not parent_session:
        return None, "Parent session expired. Sign in again."
    username = str(username or "").strip().lower()
    email = str(email or "").strip().lower()
    if not USERNAME_RE.fullmatch(username):
        return None, "Username must be 3–24 characters: letters, numbers, dots, dashes, or underscores."
    if email and not EMAIL_RE.fullmatch(email):
        return None, "Enter a valid email address or leave it blank."
    try:
        salt, digest, rounds = _password_record(password)
        parent_memory, _ = parent_store.load_user_memory(parent_session)
        learner = next((x for x in parent_memory.get("learners", []) if x.get("id") == learner_id), None)
        if not learner:
            return None, "That learner profile does not belong to this parent account."
        existing = _request("GET", "student_accounts", params={
            "parent_user_id": "eq." + parent_session["user_id"],
            "learner_id": "eq." + str(learner_id),
            "select": "id",
            "limit": "1",
        })
        payload = {
            "parent_user_id": parent_session["user_id"],
            "learner_id": str(learner_id),
            "username": username,
            "email": email or None,
            "password_salt": salt,
            "password_hash": digest,
            "password_iterations": rounds,
            "memory_data": _student_defaults(username, email, learner.get("name", ""), learner.get("age_group", "elementary")),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            # Updating a login must never erase the learner's saved work.
            payload.pop("memory_data", None)
            rows = _request("PATCH", "student_accounts", params={"id": "eq." + existing[0]["id"]},
                            payload=payload, prefer="return=representation")
        else:
            rows = _request("POST", "student_accounts", payload=payload, prefer="return=representation")
        if not rows:
            return None, "Student account was not saved."
        return {"username": username, "email": email, "learner_id": str(learner_id)}, "Student sign-in created."
    except (ValueError, RuntimeError, requests.RequestException) as error:
        return None, "Could not create student sign-in: " + str(error)[:220]


def sign_in_student(identifier, password):
    identifier = str(identifier or "").strip().lower()
    if not identifier or not password:
        return None, "Enter your student username or email and password."
    try:
        field = "email" if "@" in identifier else "username"
        rows = _request("GET", "student_accounts", params={
            field: "eq." + identifier,
            "select": "id,parent_user_id,learner_id,username,email,password_salt,password_hash,password_iterations,failed_attempts,locked_until",
            "limit": "1",
        })
        if not rows:
            return None, "Student sign-in was not recognized. Check the username/email and password."
        record = rows[0]
        if int(record.get("locked_until") or 0) > int(time.time()):
            return None, "This student sign-in is temporarily locked. Try again later or ask a parent for help."
        if not _verify_password(password, record):
            attempts = int(record.get("failed_attempts") or 0) + 1
            patch = {"failed_attempts": 0 if attempts >= 5 else attempts}
            if attempts >= 5:
                patch["locked_until"] = int(time.time()) + 900
            _request("PATCH", "student_accounts", params={"id": "eq." + record["id"]}, payload=patch)
            return None, "Student sign-in was not recognized. Check the username/email and password."
        _request("PATCH", "student_accounts", params={"id": "eq." + record["id"]},
                 payload={"failed_attempts": 0, "locked_until": 0})
        return _issue_session(record), "Student signed in."
    except (RuntimeError, requests.RequestException) as error:
        return None, "Student sign-in unavailable: " + str(error)[:220]


def reset_student_password(parent_session, learner_id, new_password):
    parent_session, _ = parent_store.ensure_valid_session(parent_session)
    if not parent_session:
        return False, "Parent session expired. Sign in again."
    try:
        salt, digest, rounds = _password_record(new_password)
        rows = _request("GET", "student_accounts", params={
            "parent_user_id": "eq." + parent_session["user_id"],
            "learner_id": "eq." + str(learner_id),
            "select": "id",
            "limit": "1",
        })
        if not rows:
            return False, "No student sign-in exists for that learner yet."
        _request("PATCH", "student_accounts", params={"id": "eq." + rows[0]["id"]},
                 payload={"password_salt": salt, "password_hash": digest,
                          "password_iterations": rounds,
                          "failed_attempts": 0, "locked_until": 0,
                          "updated_at": datetime.now(timezone.utc).isoformat()})
        return True, "Student password reset."
    except (ValueError, RuntimeError, requests.RequestException) as error:
        return False, "Could not reset student password: " + str(error)[:220]


def get_student_parent_controls(student_session):
    payload = validate_student_session(student_session)
    if not payload:
        return None, "Student session expired. Sign in again."
    try:
        rows = _request("GET", "user_memories", params={
            "user_id": "eq." + payload["pid"],
            "select": "memory_data",
            "limit": "1",
        })
        if not rows:
            return None, "Parent settings could not be loaded."
        data = rows[0].get("memory_data") or {}
        learner = next((item for item in data.get("learners", [])
                        if item.get("id") == payload["lid"]), None)
        if not learner:
            return None, "This student profile is no longer linked to the parent account."
        controls = learner.get("parent_controls") or {}
        return {
            "allow_chat": controls.get("allow_chat", True) is True,
            "allow_practice": controls.get("allow_practice", True) is True,
            "allow_hints": controls.get("allow_hints", True) is True,
            "daily_activity_limit": controls.get("daily_activity_limit", 20),
            "learner_name": learner.get("name", "Student"),
            "age_group": learner.get("age_group", "elementary"),
        }, "Parent settings loaded."
    except (RuntimeError, requests.RequestException) as error:
        return None, "Could not load parent settings: " + str(error)[:200]


def get_parent_student_progress(parent_session, learner_id):
    parent_session, _ = parent_store.ensure_valid_session(parent_session)
    if not parent_session:
        return [], "Parent session expired. Sign in again."
    try:
        rows = _request("GET", "student_accounts", params={
            "parent_user_id": "eq." + parent_session["user_id"],
            "learner_id": "eq." + str(learner_id),
            "select": "memory_data",
            "limit": "1",
        })
        if not rows:
            return [], "No independent student login is linked to this learner."
        memory = rows[0].get("memory_data") or {}
        records = memory.get("learning_progress", [])
        return ([item for item in records if isinstance(item, dict)], "Student progress loaded.")
    except (RuntimeError, requests.RequestException) as error:
        return [], "Could not load student progress: " + str(error)[:180]


def load_student_memory(student_session):
    payload = validate_student_session(student_session)
    if not payload:
        return None, "Student session expired. Sign in again."
    try:
        rows = _request("GET", "student_accounts", params={
            "id": "eq." + payload["sid"],
            "parent_user_id": "eq." + payload["pid"],
            "learner_id": "eq." + payload["lid"],
            "select": "memory_data,username,email",
            "limit": "1",
        })
        if not rows:
            return None, "Student account could not be found."
        memory = rows[0].get("memory_data")
        if not isinstance(memory, dict):
            memory = _student_defaults(rows[0]["username"], rows[0].get("email"))
        memory["profile"] = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
        memory["profile"]["username"] = rows[0]["username"]
        memory["profile"]["email"] = rows[0].get("email") or ""
        return memory, "Student memory loaded privately."
    except (RuntimeError, requests.RequestException) as error:
        return None, "Could not load student memory: " + str(error)[:220]


def save_student_memory(student_session, memory):
    payload = validate_student_session(student_session)
    if not payload:
        return False, "Student session expired. Sign in again."
    if not isinstance(memory, dict):
        return False, "Student memory must be a data object."
    safe = _student_defaults("", "")
    for key in ("facts", "chat_history", "learning_progress"):
        value = memory.get(key)
        if isinstance(value, list):
            safe[key] = [item for item in value[-100:] if isinstance(item, (dict, str))]
    profile = memory.get("profile")
    if isinstance(profile, dict):
        safe["profile"].update({
            k: str(profile.get(k) or "")[:100]
            for k in ("username", "email", "learner_name", "age_group")
        })
    count = memory.get("interaction_count", 0)
    safe["interaction_count"] = max(0, count) if isinstance(count, int) else 0
    safe["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        _request("PATCH", "student_accounts", params={
            "id": "eq." + payload["sid"],
            "parent_user_id": "eq." + payload["pid"],
            "learner_id": "eq." + payload["lid"],
        }, payload={"memory_data": safe, "updated_at": safe["updated_at"]})
        return True, "Student memory saved."
    except (RuntimeError, requests.RequestException) as error:
        return False, "Could not save student memory: " + str(error)[:220]
