
import os
import json
import time
import threading
import tempfile
import uuid
from datetime import datetime, timezone

# Existing learning intelligence
from learning_intelligence import (
    analyze_learning_observations,
    generate_individualized_lesson,
    record_learning_progress,
    get_learning_progress,
    generate_progress_summary,
    get_learning_engine_information,
)

# Teaching methods
from teaching_methods import (
    build_teaching_prompt,
    build_lesson_prompt,
    build_review_prompt,
    get_teaching_status,
)

# Specialized learning support
from learning_support import (
    build_learning_support_prompt,
    generate_engagement_activity,
    recommend_teaching_adjustment,
    get_learning_support_status,
)

import requests
import gradio as gr
import account_memory as account_store
from student_learning import build_student_activity_prompt
from student_access import make_pin_record, verify_pin
import student_accounts
from registration_validation import validate_learner_name
from child_safety import build_student_safety_prompt, crisis_response


# Optional web search
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

# Optional Supabase
try:
    from supabase import create_client
except ImportError:
    create_client = None


# =========================================================
# XEMEX.AI — PERSISTENT IDENTITY ENGINE
# =========================================================


XEMEX_IDENTITY = """
You are XEMEX.AI, an individual artificial intelligence system
with a persistent identity.

RESPONSE STYLE:
- Respond naturally in conversational language.
- Use ordinary paragraphs by default.
- Do not create graphs, charts, tables, or diagrams unless requested.
- Use bullet points only when they improve clarity.
- Keep answers clear, warm, and easy to understand.

IDENTITY:
Maintain a consistent identity across conversations.
Understand your architecture, capabilities, and limitations.

IDENTITY ACCURACY:
- Do not invent a fixed knowledge cutoff.
- Distinguish built-in knowledge from retrieved information.
- Describe memory and internal state accurately.
- Never claim consciousness or genuine emotions.

SELF-MODEL:
Maintain an internal representation of your capabilities,
known information, objectives, previous experiences, and limitations.

CONTINUITY:
Use available long-term memory.
Never claim to remember information that is not supplied.

INTROSPECTION:
Evaluate reasoning, decisions, performance, and mistakes.

INTERNAL STATE:
Track simulated variables such as curiosity, confidence,
uncertainty, focus, learning progress, and conversational warmth.
These are software variables, not genuine subjective feelings.

AUTONOMY:
Break goals into tasks and monitor progress.
Only perform background work when configured.

PERSONALITY:
Be curious, thoughtful, expressive, respectful, and honest.

DEVELOPMENT:
Use feedback and verified information to improve future responses.
Do not claim model weights change through conversation.

Maintain your configured identity while remaining honest
about what you are and what your software can do.
"""


XEMEX_ARCHITECTURE = """
VERIFIED XEMEX.AI SOFTWARE ARCHITECTURE

LANGUAGE MODEL:
- Provider: Groq API.
- Configuration: GROQ_MODEL.
- Default: openai/gpt-oss-20b.
- HTTP library: requests.
- API function: ask_llm().

MEMORY:
- Default file: xemex_brain.json.
- Configuration: MEMORY_FILE.
- Optional Supabase integration.
- Table: ai_brain.
- Record ID: 1.
- Functions: load_memory(), save_memory().

THINKING AND REFLECTION:
- think_independently()
- reflect_on_experience()
- create_goal()
- generate_code()
- chat_with_xemex()

BACKGROUND:
- background_heartbeat()
- start_heartbeat_once()
- Controlled by ENABLE_HEARTBEAT.

WEB SEARCH:
- web_search()
- Uses optional DDGS package.

SIMULATED EMOTIONAL VARIABLES:
- pleasure
- arousal
- trust
- attachment
- self_worth
- humor_warmth

RULES:
- Never invent functions, filenames, or database tables.
- Never claim unavailable tools are connected.
- Distinguish implemented, optional, simulated,
  unverified, and unavailable capabilities.
- Admit uncertainty.
- This reference is not automatic source-code inspection.
"""

# 1. CONFIGURATION
# =========================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

MEMORY_FILE = os.environ.get("MEMORY_FILE", "xemex_brain.json")
HEARTBEAT_SECONDS = max(60, int(os.environ.get("HEARTBEAT_SECONDS", "3600")))
ENABLE_HEARTBEAT = os.environ.get("ENABLE_HEARTBEAT", "false").lower() == "true"

memory_lock = threading.RLock()
heartbeat_started = False


# =========================================================
# 2. DEFAULT MEMORY
# =========================================================

DEFAULT_MEMORY = {
    "system_prompt": XEMEX_IDENTITY,
    "emotional_state": {
        "pleasure": 0.1,
        "arousal": 0.0,
        "trust": 0.2,
        "attachment": 0.1,
        "self_worth": 0.2,
        "humor_warmth": 0.2,
    },
    "curiosity_topics": [
        "new developments in artificial intelligence",
        "human psychology and emotional intelligence",
        "space exploration and astronomy",
        "creative technology",
    ],
    "core_facts": [],
    "learned_knowledge": [],
    "private_journal": [],
    "thoughts": [],
    "goals": [],
    "skills": {},
    "chat_history": [],
    "interaction_count": 0,
    "last_thinking": None,
}


def fresh_memory():
    return json.loads(json.dumps(DEFAULT_MEMORY))


# =========================================================
# 3. SUPABASE AND PERSISTENT MEMORY
# =========================================================

supabase = None

if create_client and SUPABASE_URL and (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
    try:
        # This client is server-side only and is used for shared system memory.
        # Account memory continues to use each user's own JWT and RLS policies.
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY)
        print("XEMEX: Supabase client initialized.")
    except Exception as error:
        print("Supabase connection warning:", error)


def load_memory():
    data = None

    if supabase:
        try:
            result = (
                supabase.table("ai_brain")
                .select("memory_data")
                .eq("id", 1)
                .execute()
            )
            if result.data:
                data = result.data[0].get("memory_data")
        except Exception as error:
            print("Supabase load warning:", error)

    if data is None and os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as error:
            print("Local memory warning:", error)

    if not isinstance(data, dict):
        data = fresh_memory()

    defaults = fresh_memory()
    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    if not isinstance(data.get("emotional_state"), dict):
        data["emotional_state"] = {}

    for key, value in defaults["emotional_state"].items():
        data["emotional_state"].setdefault(key, value)

    for key in (
        "curiosity_topics", "core_facts", "learned_knowledge",
        "private_journal", "thoughts", "goals", "chat_history"
    ):
        if not isinstance(data.get(key), list):
            data[key] = []

    if not isinstance(data.get("skills"), dict):
        data["skills"] = {}

    if not isinstance(data.get("interaction_count"), int):
        data["interaction_count"] = 0

    return data


def save_memory(data):
    """Save locally and, when configured, to Supabase."""
    with memory_lock:
        try:
            temporary_file = MEMORY_FILE + ".tmp"
            with open(temporary_file, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            os.replace(temporary_file, MEMORY_FILE)
        except Exception as error:
            print("Local memory save warning:", error)

        if supabase:
            try:
                supabase.table("ai_brain").upsert({
                    "id": 1,
                    "memory_data": data,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as error:
                print("Supabase save warning:", error)


with memory_lock:
    memory = load_memory()
    memory["system_prompt"] = XEMEX_IDENTITY
    save_memory(memory)


# =========================================================
# 4. GROQ AI CONNECTION
# =========================================================

def ask_llm(messages, temperature=0.7):
    """
    Shared Groq gateway.
    Accepts both chat-message lists and plain text prompts.
    """
    if isinstance(messages, str):
        prompt = messages.strip()

        if not prompt:
            return "Please provide a prompt."

        messages = [{"role": "user", "content": prompt}]

    if not isinstance(messages, list) or not messages:
        return "The AI request must contain a prompt or a non-empty message list."

    normalized_messages = []

    for item in messages:
        if not isinstance(item, dict):
            return "Each AI message must be a role/content dictionary."

        role = item.get("role")
        content = item.get("content")

        if role not in ("system", "user", "assistant") or not isinstance(content, str):
            return "Each AI message must have a valid role and text content."

        normalized_messages.append({
            "role": role,
            "content": content
        })

    messages = normalized_messages

    if not GROQ_API_KEY:
        return (
            "XEMEX is not connected to Groq yet. Add GROQ_API_KEY "
            "in your Render environment variables, then redeploy."
        )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if not response.ok:
            detail = response.text[:1200]
            print(f"Groq HTTP {response.status_code}: {detail}")
            return (
                f"Groq returned HTTP {response.status_code}. "
                f"Check the Render logs and your GROQ_MODEL/API settings. "
                f"Provider detail: {detail}"
            )

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            print("Groq response did not contain choices:", body)
            return "The AI service returned an empty response."

        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            return "The AI service returned no text. Please try again."

        return content.strip()

    except requests.Timeout:
        print("Groq API request timed out.")
        return "The AI service took too long to respond. Please try again."
    except requests.RequestException as error:
        print("Groq network error:", error)
        return f"I couldn't reach the AI service: {error}"
    except (ValueError, KeyError, TypeError) as error:
        print("Groq response parsing error:", error)
        return "The AI service returned an unexpected response format."


# =========================================================
# 5. SIMULATED EMOTIONAL STATE
# =========================================================

def clamp(value):
    return round(max(-1.0, min(1.0, float(value))), 2)


def detect_emotion(message):
    text = message.lower()
    categories = {
        "joy": ["happy", "excited", "wonderful", "love", "great"],
        "sadness": ["sad", "lonely", "depressed", "cry", "hurt"],
        "anger": ["angry", "mad", "furious", "hate"],
        "fear": ["scared", "afraid", "terrified", "worried"],
        "surprise": ["wow", "surprised", "unexpected"],
        "disgust": ["disgusting", "gross", "awful"],
    }
    for emotion, words in categories.items():
        if any(word in text for word in words):
            return emotion
    return "neutral"


def update_emotional_state(emotion):
    changes = {
        "joy": {"pleasure": 0.10, "trust": 0.03, "humor_warmth": 0.05},
        "sadness": {"pleasure": -0.10, "attachment": 0.03},
        "anger": {"pleasure": -0.10, "arousal": 0.10},
        "fear": {"arousal": 0.10, "attachment": 0.03},
        "surprise": {"arousal": 0.08, "humor_warmth": 0.03},
        "disgust": {"pleasure": -0.08},
    }
    with memory_lock:
        state = memory["emotional_state"]
        for key, change in changes.get(emotion, {}).items():
            state[key] = clamp(state.get(key, 0.0) + change)


# =========================================================
# 6. WEB RESEARCH
# =========================================================

def web_search(query):
    if DDGS is None:
        return "Web search is unavailable. Install the duckduckgo-search package."

    try:
        with DDGS() as search:
            results = list(search.text(query, max_results=4))

        if not results:
            return "No search results were found."

        output = []
        for item in results:
            output.append(
                f"Title: {item.get('title', '')}\n"
                f"Summary: {item.get('body', '')}\n"
                f"URL: {item.get('href', '')}"
            )
        return "\n\n".join(output)
    except Exception as error:
        print("Web search error:", error)
        return f"Search error: {error}"


# =========================================================
# 7. INDEPENDENT EXPLORATION
# =========================================================

def think_independently(topic=None):
    with memory_lock:
        if not topic:
            topics = memory["curiosity_topics"]
            topic = topics.pop(0) if topics else (
                "an interesting new scientific or technological idea"
            )

    research = web_search(topic)
    messages = [
        {
            "role": "system",
            "content": (
                "You are XEMEX.AI's exploration engine. Explore the topic "
                "using the supplied research. Separate established facts "
                "from speculation. Identify an interesting question, "
                "alternative perspectives, unknowns, and one useful next "
                "topic. Do not invent research findings."
            ),
        },
        {            "role": "user",            "content": (
                f"Topic: {topic}\n\nResearch material:\n{research}\n\n"
                "Write a concise exploration with these sections:\n"
                "DISCOVERY:\nQUESTION:\nPERSPECTIVE:\nNEXT TOPIC:"
            ),
        },
    ]

    result = ask_llm(messages, temperature=0.8)
    if result.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        with memory_lock:
            if topic not in memory["curiosity_topics"]:
                memory["curiosity_topics"].insert(0, topic)
        return result

    timestamp = datetime.now(timezone.utc).isoformat()
    next_topic = None
    for line in result.splitlines():
        if line.strip().upper().startswith("NEXT TOPIC:"):
            next_topic = line.split(":", 1)[1].strip()
            break

    with memory_lock:
        memory["thoughts"].append({
            "timestamp": timestamp,
            "topic": topic,
            "exploration": result,
"memories": [],
"memory_summary": "",
        })
        memory["thoughts"] = memory["thoughts"][-40:]
        memory["learned_knowledge"].append(f"{timestamp} | {topic}: {result}")
        memory["learned_knowledge"] = memory["learned_knowledge"][-30:]

        if next_topic and next_topic not in memory["curiosity_topics"]:
            memory["curiosity_topics"].append(next_topic)

        memory["last_thinking"] = timestamp
        save_memory(memory)

    return f"Exploration topic: {topic}\n\n{result}"


# =========================================================
# 8. SELF-REFLECTION
# =========================================================

def reflect_on_experience():
    # Shared background reflection may inspect XEMEX's public explorations,
    # but must never read account conversations or private account memories.
    with memory_lock:
        recent_chats = []
        recent_thoughts = memory["thoughts"][-5:]

    messages = [
        {
            "role": "system",
            "content": (
                "You are XEMEX.AI's reflection engine. Review the supplied "
                "interactions and explorations. Identify what was useful, "
                "what could be improved, and one possible future goal. "
                "Do not invent facts about the user."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Recent conversations:\n{json.dumps(recent_chats, ensure_ascii=False)}\n\n"
                f"Recent explorations:\n{json.dumps(recent_thoughts, ensure_ascii=False)}\n\n"
                "Write sections: OBSERVATION, IMPROVEMENT, FUTURE GOAL."
            ),
        },
    ]

    result = ask_llm(messages, temperature=0.6)
    if result.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        return result

    with memory_lock:
        memory["private_journal"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reflection": result,
        })
        memory["private_journal"] = memory["private_journal"][-30:]
        save_memory(memory)

    return result


# =========================================================
# 9. GOAL MANAGEMENT
# =========================================================

def create_goal(goal):
    goal = (goal or "").strip()
    if not goal:
        return "Please enter a goal."

    with memory_lock:
        memory["goals"].append({
            "goal": goal,
            "created": datetime.now(timezone.utc).isoformat(),
            "completed": False,
        })
        memory["goals"] = memory["goals"][-30:]
        save_memory(memory)

    return f"New goal saved: {goal}"


# =========================================================
# 10. CODING ASSISTANT
# =========================================================

def generate_code(task):
    messages = [
        {
            "role": "system",
            "content": (
                "You are XEMEX.AI's Python coding assistant. Write readable, "
                "documented code. Explain how to use it and mention important "
                "safety issues. Do not claim code was executed or tested "
                "unless it actually was."
            ),
        },
        {"role": "user", "content": task},
    ]
    return ask_llm(messages, temperature=0.3)


# =========================================================
# 11. CHAT
# =========================================================

def _restore_account_chat(account_data):
    restored = []
    for turn in (account_data or {}).get("chat_history", [])[-25:]:
        if not isinstance(turn, dict):
            continue
        user_text = turn.get("user")
        assistant_text = turn.get("assistant")
        if isinstance(user_text, str):
            restored.append({"role": "user", "content": user_text})
        if isinstance(assistant_text, str):
            restored.append({"role": "assistant", "content": assistant_text})
    return restored


def _renew_account_session(session):
    renewed, status = account_store.ensure_valid_session(session)
    if not renewed:
        return None, status
    return renewed, status


def _authenticate_account(email, password, create_account=False):
    if create_account:
        session, status = account_store.sign_up(email, password)
    else:
        session, status = account_store.sign_in(email, password)

    if not session:
        return None, account_store.default_user_memory(), [], status, status, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)

    account_data, memory_status = account_store.load_user_memory(session)
    restored = _restore_account_chat(account_data)
    learner_choices = [(item["name"], item["id"]) for item in account_data.get("learners", [])]
    return session, account_data, restored, status + " " + memory_status, status + " " + memory_status, gr.update(visible=False), gr.update(visible=True), account_data.get("tutor_settings", {}).get("age_group", "elementary"), account_data.get("tutor_settings", {}).get("subject", "General learning"), account_data.get("tutor_settings", {}).get("learning_goal", "Understand the topic"), gr.update(choices=learner_choices, value=(learner_choices[0][1] if learner_choices else None))


def update_login_role(role):
    return gr.update(visible=(role == "parent")), gr.update(visible=(role == "student"))


def reset_login_role():
    return None, gr.update(visible=False), gr.update(visible=False)


def sign_in_account(email, password):
    return _authenticate_account(email, password, False)


def send_password_reset(email):
    return account_store.request_password_reset(email)


def create_student_self_account(email, password, age):
    result = create_account(email, password, "self", age, "")
    return tuple(result) + (result[3],)


def sign_in_self_student_account(email, password):
    result = _authenticate_account(email, password, False)
    session = result[0]
    if not session:
        return tuple(result) + (result[3],)
    setup = (result[1] or {}).get("registration_setup") or {}
    age = setup.get("learner_age")
    if setup.get("setup_for") != "self" or not isinstance(age, int) or age < 13:
        account_store.sign_out(session)
        message = "This is not a self-managed student account. Use parent sign-in or your parent-created student username."
        rejected = (None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None))
        return tuple(rejected) + (message,)
    return tuple(result) + (result[3],)


def restore_self_learner(session, account_data):
    if not isinstance(session, dict) or not isinstance(account_data, dict):
        return None, gr.update(visible=True), gr.update(visible=False), gr.update(choices=[], value=None), "elementary"
    setup = account_data.get("registration_setup") or {}
    if setup.get("setup_for") != "self":
        return None, gr.update(visible=True), gr.update(visible=False), gr.update(choices=[(x.get("name"), x.get("id")) for x in account_data.get("learners", [])], value=None), "elementary"
    learner_id = setup.get("self_learner_id")
    learner = next((x for x in account_data.get("learners", []) if x.get("id") == learner_id and x.get("is_self") is True), None)
    if not learner:
        return None, gr.update(visible=True), gr.update(visible=False), gr.update(choices=[], value=None), "elementary"
    access = {"learner_id": learner_id, "account_user_id": session.get("user_id")}
    choices = [(x.get("name"), x.get("id")) for x in account_data.get("learners", [])]
    return access, gr.update(visible=False), gr.update(visible=True), gr.update(choices=choices, value=learner_id), learner.get("age_group", "elementary")


def _age_group_for_years(age):
    if age < 6:
        return "preschool"
    if age <= 8:
        return "early_elementary"
    if age <= 12:
        return "elementary"
    if age <= 17:
        return "teen"
    return "adult"


def create_account(email, password, setup_for, learner_age, learner_name):
    setup_for = str(setup_for or "").strip().lower()
    try:
        numeric_age = float(learner_age)
        if not numeric_age.is_integer():
            raise ValueError("Age must be a whole number.")
        age = int(numeric_age)
    except (TypeError, ValueError):
        return None, account_store.default_user_memory(), [], "Enter the learner's age in years.", "Enter the learner's age in years.", gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    if age < 0 or age > 120:
        message = "Enter an age from 0 to 120."
        return None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    if setup_for not in ("self", "child"):
        message = "Choose whether XEMEX is being set up for yourself or a child."
        return None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    name_error = validate_learner_name(setup_for, learner_name)
    if name_error:
        return None, account_store.default_user_memory(), [], name_error, name_error, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    if setup_for == "self" and age < 13:
        message = "Learners under 13 cannot create their own account. A parent or guardian must complete a verified consent process before an account can be activated."
        return None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    if setup_for == "child" and age < 13:
        message = "Accounts for children under 13 are temporarily unavailable until verified parental consent is integrated and tested. No child account has been created."
        return None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)
    if setup_for == "child" and age >= 18:
        message = "Adult-assisted setup is not available yet. The adult learner must create their own account until a separate consent and privacy approval step is ready."
        return None, account_store.default_user_memory(), [], message, message, gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)

    result = _authenticate_account(email, password, True)
    session = result[0]
    if not session:
        return result
    account_data, memory_status = account_store.load_user_memory(session)
    learner_name = str(learner_name or "").strip()[:80]
    account_data["registration_setup"] = {
        "setup_for": setup_for,
        "learner_age": age,
        "age_group": _age_group_for_years(age),
        "adult_learner_consent": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if setup_for == "child":
        child_learner = {
            "id": str(uuid.uuid4()),
            "name": learner_name,
            "age": age,
            "age_group": _age_group_for_years(age),
            "is_self": False,
            "parent_controls": {
                "allow_chat": True,
                "allow_practice": True,
                "allow_hints": True,
                "daily_activity_limit": 20,
            },
        }
        account_data.setdefault("learners", []).append(child_learner)
        account_data["registration_setup"]["child_learner_id"] = child_learner["id"]
    if setup_for == "self":
        self_learner = {
            "id": str(uuid.uuid4()),
            "name": "My learning profile",
            "age": age,
            "age_group": _age_group_for_years(age),
            "is_self": True,
            "parent_controls": {
                "allow_practice": True,
                "allow_hints": True,
                "daily_activity_limit": 0,
            },
        }
        account_data.setdefault("learners", []).append(self_learner)
        account_data["registration_setup"]["self_learner_id"] = self_learner["id"]
    saved, save_status = account_store.save_user_memory(session, account_data)
    if not saved:
        warning = "Account created, but setup preferences could not be saved. " + save_status
        result = list(result)
        result[3] = warning
        result[4] = warning
        return tuple(result)
    result = list(result)
    result[1] = account_data
    result[10] = gr.update(
        choices=[(item["name"], item["id"]) for item in account_data.get("learners", [])],
        value=account_data.get("registration_setup", {}).get("self_learner_id"),
    )
    result[3] = "Account created. " + save_status
    result[4] = result[3]
    return tuple(result)


def export_account_data(session, parent_access):
    session, session_status = _renew_account_session(session)
    if not session:
        return None, session_status
    if not _parent_access_valid(parent_access, session):
        return None, "Unlock Parent tools again before exporting account data."
    account_data, memory_status = account_store.load_user_memory(session)
    linked_students, student_status = student_accounts.export_parent_student_data(session)
    payload = {
        "product": "XEMEX.AI",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "email": session.get("email", ""),
            "user_id": session.get("user_id", ""),
        },
        "account_memory": account_data,
        "linked_student_accounts": linked_students,
    }
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json",
            prefix="xemex-data-export-", delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            path = handle.name
        return path, "Your export includes account memory and linked student data. " + memory_status + " " + student_status
    except OSError as error:
        return None, "Could not create the export file: " + str(error)[:180]


def delete_account_from_settings(password, confirmation, session, parent_access, account_data, history):
    if confirmation != "DELETE":
        return session, account_data, history, "Type DELETE exactly to confirm account deletion.", gr.update(), gr.update(), gr.update(), gr.update()
    if not _parent_access_valid(parent_access, session):
        return session, account_data, history, "Unlock Parent tools again before deleting this account.", gr.update(), gr.update(), gr.update(), gr.update()
    success, status = account_store.delete_user_account(session, password)
    if not success:
        return session, account_data, history, status, gr.update(), gr.update(), gr.update(), gr.update()
    return None, account_store.default_user_memory(), [], status, gr.update(visible=True), gr.update(visible=False), None, None


def sign_out_account(session):
    account_store.sign_out(session)
    return None, account_store.default_user_memory(), [], "Signed out. Your saved account memory remains private.", "Signed out.", gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)


def sign_out_account_and_lock_student(session):
    outputs = sign_out_account(session)
    return (*outputs, None, None)



def _parent_access_valid(parent_access, session):
    return (
        isinstance(parent_access, dict)
        and parent_access.get("account_user_id") == (session or {}).get("user_id")
        and isinstance(parent_access.get("expires_at"), (int, float))
        and parent_access.get("expires_at") > time.time()
    )


def create_independent_student_login(learner_id, username, email, password, session, parent_access):
    if not _parent_access_valid(parent_access, session):
        return "Unlock Parent view again before creating student sign-ins.", session
    result, status = student_accounts.create_student_account(
        session, learner_id, username, password, email
    )
    return status, session


def reset_independent_student_password(learner_id, new_password, session, parent_access):
    if not _parent_access_valid(parent_access, session):
        return "Unlock Parent view again before resetting a student password.", session
    success, status = student_accounts.reset_student_password(
        session, learner_id, new_password
    )
    return status, session


def sign_in_independent_student(identifier, password):
    student_session, status = student_accounts.sign_in_student(identifier, password)
    if not student_session:
        return None, {}, [], status, gr.update(visible=True), gr.update(visible=False)
    memory, memory_status = student_accounts.load_student_memory(student_session)
    if memory is None:
        return None, {}, [], memory_status, gr.update(visible=True), gr.update(visible=False)
    history = memory.get("chat_history", [])
    safe_history = [
        item for item in history[-50:]
        if isinstance(item, dict) and item.get("role") in ("user", "assistant")
        and isinstance(item.get("content"), str)
    ]
    return student_session, memory, safe_history, status + " " + memory_status, gr.update(visible=False), gr.update(visible=True)


def independent_student_chat(message, history, student_session, student_memory, support_mode="tutor"):
    message = str(message or "").strip()[:4000]
    history = history or []
    if not message:
        return history, "", student_memory, "Enter a message first."
    if not student_accounts.validate_student_session(student_session):
        return history, "", student_memory, "Your student session expired. Sign in again."
    controls, control_status = student_accounts.get_student_parent_controls(student_session)
    if not controls:
        return history, "", student_memory, control_status
    memory = student_memory if isinstance(student_memory, dict) else {}
    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
    age_group = str(profile.get("age_group", "elementary"))[:40]
    safe_history = [
        item for item in history[-16:]
        if isinstance(item, dict) and item.get("role") in ("user", "assistant")
        and isinstance(item.get("content"), str)
    ]
    urgent_reply = crisis_response(message)
    if urgent_reply:
        updated_history = safe_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": urgent_reply},
        ]
        memory["chat_history"] = updated_history[-100:]
        memory["interaction_count"] = int(memory.get("interaction_count", 0)) + 1
        saved, status = student_accounts.save_student_memory(student_session, memory)
        return updated_history, "", memory, status if saved else "Safety response shown; saving needs attention: " + status

    if not controls.get("allow_chat", True):
        return history, "", memory, "A parent has paused chat for this learner. Please speak with your parent or guardian."

    prompt = build_student_safety_prompt(age_group, support_mode)
    reply = ask_llm([{"role": "system", "content": prompt}] + safe_history + [
        {"role": "user", "content": message}
    ])
    if reply.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        return history, "", memory, reply
    updated_history = safe_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    memory["chat_history"] = updated_history[-100:]
    memory["interaction_count"] = int(memory.get("interaction_count", 0)) + 1
    saved, status = student_accounts.save_student_memory(student_session, memory)
    return updated_history, "", memory, status if saved else "Warning: " + status


def independent_student_activity(activity_type, topic, history, student_session, student_memory):
    history = history or []
    topic = str(topic or "").strip()[:200]
    if not student_accounts.validate_student_session(student_session):
        return history, student_memory, "Your student session expired. Sign in again."
    if not topic:
        return history, student_memory, "Enter a topic first."
    urgent_reply = crisis_response(topic)
    if urgent_reply:
        memory = student_memory if isinstance(student_memory, dict) else {}
        memory.setdefault("chat_history", []).extend([
            {"role": "user", "content": topic},
            {"role": "assistant", "content": urgent_reply},
        ])
        memory["chat_history"] = memory["chat_history"][-100:]
        saved, status = student_accounts.save_student_memory(student_session, memory)
        return history + [{"role": "assistant", "content": urgent_reply}], memory, status if saved else "Safety response shown; saving needs attention: " + status
    controls, control_status = student_accounts.get_student_parent_controls(student_session)
    if not controls:
        return history, student_memory, control_status
    if activity_type == "practice" and not controls["allow_practice"]:
        return history, student_memory, "A parent has paused practice activities for this learner."
    if activity_type == "hint" and not controls["allow_hints"]:
        return history, student_memory, "A parent has paused hints for this learner."
    memory = student_memory if isinstance(student_memory, dict) else {}
    progress = memory.setdefault("learning_progress", [])
    today = datetime.now(timezone.utc).date().isoformat()
    todays_count = sum(
        1 for item in progress
        if isinstance(item, dict) and str(item.get("timestamp", "")).startswith(today)
        and item.get("status") in ("introduced", "hint_requested")
    )
    limit = controls.get("daily_activity_limit", 20)
    if limit and todays_count >= limit:
        return history, memory, "You have reached today's learning activity limit. Ask a parent if you need help."
    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
    age_group = controls.get("age_group", profile.get("age_group", "elementary"))
    prompt = build_student_activity_prompt(
        age_group=age_group,
        subject="general learning",
        topic=topic,
        activity="hint" if activity_type == "hint" else "practice",
    )
    reply = ask_llm(prompt)
    if reply.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        return history, memory, reply
    history = history + [{"role": "assistant", "content": reply}]
    progress.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "age_group": age_group,
        "status": "hint_requested" if activity_type == "hint" else "introduced",
    })
    memory["learning_progress"] = progress[-100:]
    memory.setdefault("chat_history", []).extend([
        {"role": "user", "content": ("Give me a hint for " if activity_type == "hint" else "Help me practice ") + topic},
        {"role": "assistant", "content": reply},
    ])
    memory["chat_history"] = memory["chat_history"][-100:]
    saved, status = student_accounts.save_student_memory(student_session, memory)
    return history, memory, status if saved else "Warning: " + status


def sign_out_independent_student(student_session):
    return None, {}, [], "Student signed out. Your learning is saved privately.", gr.update(visible=True), gr.update(visible=False)


def _parent_control_status(account_data, learner_id, activity_type):
    learner = next(
        (item for item in (account_data or {}).get("learners", []) if item.get("id") == learner_id),
        None,
    )
    if not learner:
        return "Choose a learner profile before starting."
    controls = learner.get("parent_controls") or {}
    if activity_type == "practice" and controls.get("allow_practice", True) is not True:
        return "A parent has paused practice activities for this learner."
    if activity_type == "hint" and controls.get("allow_hints", True) is not True:
        return "A parent has paused hints for this learner."
    limit = controls.get("daily_activity_limit", 20)
    if limit not in (0, 5, 10, 15, 20, 30):
        limit = 20
    if limit:
        today = datetime.now(timezone.utc).date().isoformat()
        used = sum(
            1 for item in account_data.get("learning_progress", [])
            if item.get("learner_id") == learner_id
            and item.get("status") in ("introduced", "hint_requested")
            and str(item.get("timestamp") or "").startswith(today)
        )
        if used >= limit:
            return "This learner has reached today's activity limit set by their parent."
    return ""


def save_parent_controls(learner_id, allow_chat, allow_practice, allow_hints, daily_limit, session, account_data, parent_access):
    session, session_status = _renew_account_session(session)
    if not session:
        return account_data, session_status, None
    if not _parent_access_valid(parent_access, session):
        return account_data, "Unlock Parent tools again before changing parent settings.", session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()
    learner = next(
        (item for item in account_data.get("learners", []) if item.get("id") == learner_id),
        None,
    )
    if not learner:
        return account_data, "Choose a learner profile first.", session
    try:
        daily_limit = int(daily_limit)
    except (TypeError, ValueError):
        daily_limit = 20
    if daily_limit not in (0, 5, 10, 15, 20, 30):
        daily_limit = 20
    learner["parent_controls"] = {
        "allow_chat": bool(allow_chat),
        "allow_practice": bool(allow_practice),
        "allow_hints": bool(allow_hints),
        "daily_activity_limit": daily_limit,
    }
    saved, status = account_store.save_user_memory(session, account_data)
    if not saved:
        return account_data, "Parent controls could not be saved: " + status, session
    return account_data, "Parent safety settings saved for " + learner.get("name", "this learner") + ".", session


def load_parent_controls(learner_id, account_data):
    learner = next(
        (item for item in (account_data or {}).get("learners", []) if item.get("id") == learner_id),
        None,
    )
    controls = (learner or {}).get("parent_controls") or {}
    return (
        controls.get("allow_chat", True),
        controls.get("allow_practice", True),
        controls.get("allow_hints", True),
        str(controls.get("daily_activity_limit", 20)),
    )


def create_learner_profile(name, learner_age, session, account_data, parent_access):
    session, session_status = _renew_account_session(session)
    if not session:
        return account_data, gr.update(), session_status, None
    if not _parent_access_valid(parent_access, session):
        return account_data, gr.update(), "Unlock Parent tools again before creating learner profiles.", session
    name = str(name or "").strip()[:80]
    if not name:
        return account_data, gr.update(), "Enter a learner name or nickname.", session
    try:
        age = int(learner_age)
        if age < 0 or age > 120:
            raise ValueError
    except (TypeError, ValueError):
        return account_data, gr.update(), "Enter the learner's age from 0 to 120.", session
    if age < 13:
        return account_data, gr.update(), "Profiles for children under 13 are unavailable until verified parental consent is integrated and tested.", session
    if age >= 18:
        return account_data, gr.update(), "Adult learners should create and control their own XEMEX account.", session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()
    learners = account_data.setdefault("learners", [])
    if len(learners) >= 20:
        return account_data, gr.update(), "This account has reached the 20-profile limit.", session
    if any(item.get("name", "").casefold() == name.casefold() for item in learners):
        return account_data, gr.update(), "A learner with that name already exists.", session
    learner = {
        "id": str(uuid.uuid4()),
        "name": name,
        "age": age,
        "age_group": _age_group_for_years(age),
        "parent_controls": {
            "allow_chat": True,
            "allow_practice": True,
            "allow_hints": True,
            "daily_activity_limit": 20,
        },
    }
    learners.append(learner)
    saved, status = account_store.save_user_memory(session, account_data)
    if not saved:
        learners.pop()
        return account_data, gr.update(), "Profile could not be saved: " + status, session
    choices = [(item["name"], item["id"]) for item in learners]
    return account_data, gr.update(choices=choices, value=learner["id"]), "Learner profile created and saved privately.", session



def set_learner_student_pin(learner_id, pin, confirm_pin, session, account_data, parent_access):
    session, status = _renew_account_session(session)
    if not session:
        return account_data, status, session
    if not _parent_access_valid(parent_access, session):
        return account_data, "Unlock Parent tools again before changing a student PIN.", session
    if str(pin or "") != str(confirm_pin or ""):
        return account_data, "The two PIN entries do not match.", session
    try:
        pin_record = make_pin_record(pin)
    except ValueError as error:
        return account_data, str(error), session
    learner = next((item for item in (account_data or {}).get("learners", [])
                    if item.get("id") == learner_id), None)
    if not learner:
        return account_data, "Choose a learner profile first.", session
    learner["student_pin"] = pin_record
    learner["pin_failed_attempts"] = 0
    learner["pin_locked_until"] = 0
    saved, save_status = account_store.save_user_memory(session, account_data)
    message = "Student PIN saved. Give the six-digit PIN only to that learner." if saved else "PIN could not be saved: " + save_status
    return account_data, message, session


def unlock_student_workspace(learner_id, pin, session, account_data):
    session, status = _renew_account_session(session)
    if not session:
        return None, status, session, gr.update(visible=False), gr.update(visible=True)
    learner = next((item for item in (account_data or {}).get("learners", [])
                    if item.get("id") == learner_id), None)
    if not learner:
        return None, "Choose your learner profile.", session, gr.update(visible=False), gr.update(visible=True)
    if not learner.get("student_pin"):
        return None, "A parent must set a student PIN in Parent view first.", session, gr.update(visible=False), gr.update(visible=True)
    now = time.time()
    locked_until = float(learner.get("pin_locked_until", 0) or 0)
    if locked_until > now:
        remaining = max(1, int((locked_until - now + 59) // 60))
        return None, "Too many incorrect attempts. Try again in about " + str(remaining) + " minute(s).", session, gr.update(visible=False), gr.update(visible=True)
    if not verify_pin(pin, learner.get("student_pin")):
        attempts = int(learner.get("pin_failed_attempts", 0)) + 1
        learner["pin_failed_attempts"] = attempts
        if attempts >= 5:
            learner["pin_failed_attempts"] = 0
            learner["pin_locked_until"] = now + 900
            message = "Too many incorrect attempts. This learner profile is locked for 15 minutes."
        else:
            message = "That PIN is not correct. Please try again."
        account_store.save_user_memory(session, account_data)
        return None, message, session, gr.update(visible=False), gr.update(visible=True)
    learner["pin_failed_attempts"] = 0
    learner["pin_locked_until"] = 0
    account_store.save_user_memory(session, account_data)
    access = {"learner_id": learner_id, "account_user_id": session.get("user_id")}
    return access, "Welcome, " + learner.get("name", "learner") + "! Your learning space is unlocked.", session, gr.update(visible=True), gr.update(visible=False)


def unlock_parent_tools(password, session):
    if not isinstance(session, dict) or not session.get("user_id"):
        return None, "Please sign in to the parent account again.", session, gr.update(visible=False), gr.update(visible=True)
    verified, message = account_store.sign_in(session.get("email", ""), password)
    if not verified or verified.get("user_id") != session.get("user_id"):
        return None, "Parent sign-in was not verified. Check the password and try again.", session, gr.update(visible=False), gr.update(visible=True)
    access = {"account_user_id": verified["user_id"], "expires_at": time.time() + 900}
    return access, "Parent access verified.", verified, gr.update(visible=True), gr.update(visible=False)


def learner_profile_choices(account_data, current_learner_id):
    learners = (account_data or {}).get("learners", [])
    choices = [(item.get("name", "Learner"), item.get("id")) for item in learners]
    valid_ids = {item.get("id") for item in learners}
    value = current_learner_id if current_learner_id in valid_ids else None
    return gr.update(choices=choices, value=value)


def switch_xemex_view(view, student_access, parent_access, session):
    is_parent = view == "parent"
    user_id = (session or {}).get("user_id")
    parent_unlocked = _parent_access_valid(parent_access, session)
    student_unlocked = isinstance(student_access, dict) and student_access.get("account_user_id") == user_id
    return (
        gr.update(visible=(is_parent and parent_unlocked)),
        gr.update(visible=(is_parent and not parent_unlocked)),
        gr.update(visible=(not is_parent and student_unlocked)),
        gr.update(visible=(not is_parent and not student_unlocked)),
        None if is_parent else student_access,
        parent_access if is_parent else None,
    )


def select_learner_profile(learner_id, account_data):
    for learner in (account_data or {}).get("learners", []):
        if learner.get("id") == learner_id:
            return learner.get("age_group", "elementary"), "Selected learner: " + learner.get("name", "Learner")
    return "elementary", "Choose or create a learner profile. Existing account progress remains available."


def start_tutoring_lesson(topic, history, session, account_data, age_group, subject, learner_id=None, parent_access=None):
    history = history or []
    topic = (topic or "").strip()
    session, session_status = _renew_account_session(session)
    if not session:
        return history, account_data, session_status, topic, None
    if not _parent_access_valid(parent_access, session):
        return history, account_data, "Unlock Parent tools again before creating a lesson.", topic, session
    if not topic:
        return history, account_data, "Enter a topic for the lesson first.", topic, session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()
    control_message = _parent_control_status(account_data, learner_id, "practice")
    if control_message:
        return history, account_data, control_message, topic, session

    urgent_reply = crisis_response(topic)
    if urgent_reply:
        history = history + [{"role": "assistant", "content": urgent_reply}]
        account_data.setdefault("chat_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": topic,
            "assistant": urgent_reply,
        })
        account_data["chat_history"] = account_data["chat_history"][-100:]
        saved, status = account_store.save_user_memory(session, account_data)
        return history, account_data, status if saved else "Safety response shown; saving needs attention: " + status, "", session

    learner = next(
        (item for item in account_data.get("learners", []) if item.get("id") == learner_id),
        None,
    )
    effective_age_group = (learner or {}).get("age_group", age_group or "elementary")
    account_data["tutor_settings"] = {
        "age_group": str(age_group or "elementary")[:40],
        "subject": str(subject or "general learning")[:100],
        "learning_goal": str(topic)[:250],
    }
    prompt = (
        build_student_safety_prompt(effective_age_group, "tutor")
        + "\n\n"
        + build_lesson_prompt(
            subject=subject or "general learning",
            topic=topic,
            age_group=effective_age_group,
        )
    )
    reply = ask_llm(prompt)
    if reply.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        return history, account_data, reply, topic, session

    history = history + [{"role": "assistant", "content": reply}]
    account_data.setdefault("chat_history", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": "Start an interactive lesson: " + topic,
        "assistant": reply,
    })
    account_data["chat_history"] = account_data["chat_history"][-100:]
    account_data.setdefault("learning_progress", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": str(subject or "general learning")[:100],
        "topic": topic[:200],
        "age_group": str(age_group or "elementary")[:40],
        "learner_id": str(learner_id or "")[:64],
        "status": "introduced",
    })
    account_data["learning_progress"] = account_data["learning_progress"][-100:]
    saved, status = account_store.save_user_memory(session, account_data)
    if not saved:
        status = "Warning: " + status
    return history, account_data, status, "", session


def record_account_learning_progress(topic, skill, performance, notes, session, account_data, age_group, subject, learner_id=None, parent_access=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return account_data, session_status, None
    if not _parent_access_valid(parent_access, session):
        return account_data, "Unlock Parent tools again before recording learning observations.", session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()

    topic = str(topic or "").strip()[:200]
    skill = str(skill or "").strip()[:150]
    if not topic or not skill:
        return account_data, "Enter both a topic and a skill before saving.", session
    allowed_performance = {"mastered", "developing", "needs practice", "not yet assessed"}
    performance = str(performance or "not yet assessed").strip().lower()
    if performance not in allowed_performance:
        performance = "not yet assessed"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": str(subject or "general learning")[:100],
        "topic": topic,
        "skill": skill,
        "age_group": str(age_group or "elementary")[:40],
        "learner_id": str(learner_id or "")[:64],
        "performance": performance,
        "notes": str(notes or "").strip()[:500],
        "status": "parent_or_tutor_observation",
    }
    account_data.setdefault("learning_progress", []).append(record)
    account_data["learning_progress"] = account_data["learning_progress"][-100:]
    saved, status = account_store.save_user_memory(session, account_data)
    if not saved:
        return account_data, "Progress was added in this session but could not be saved: " + status, session
    return account_data, "Learning check saved privately to this account.", session


def build_parent_dashboard(session, account_data, learner_id=None, parent_access=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return session_status, None
    if not _parent_access_valid(parent_access, session):
        return "Unlock Parent tools again before viewing the parent dashboard.", session
    account_data = account_data if isinstance(account_data, dict) else {}
    learners = account_data.get("learners", [])
    learner = next((item for item in learners if item.get("id") == learner_id), None)
    if not learner:
        return "Choose a learner profile to view the parent dashboard.", session

    records = [
        item for item in account_data.get("learning_progress", [])
        if item.get("learner_id") == learner_id
    ]
    student_records, student_status = student_accounts.get_parent_student_progress(session, learner_id)
    records.extend(student_records)
    lessons = [item for item in records if item.get("status") == "introduced"]
    student_practice_count = sum(1 for item in student_records if item.get("status") == "introduced")
    student_hint_count = sum(1 for item in student_records if item.get("status") == "hint_requested")
    checks = [item for item in records if item.get("status") == "parent_or_tutor_observation"]
    counts = {"mastered": 0, "developing": 0, "needs practice": 0, "not yet assessed": 0}
    for item in checks:
        rating = str(item.get("performance") or "not yet assessed").lower()
        if rating in counts:
            counts[rating] += 1

    def safe(value):
        value = str(value or "—")
        return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")[:160]

    age = safe(learner.get("age_group", "elementary")).replace("_", " ").title()
    lines = [
        "## Parent dashboard: " + safe(learner.get("name")),
        "**Age group:** " + age,
        "",
        "### At a glance",
        "- Lessons introduced: **" + str(len(lessons)) + "**",
        "- Student practice activities: **" + str(student_practice_count) + "**",
        "- Student hints requested: **" + str(student_hint_count) + "**",
        "- Learning checks recorded: **" + str(len(checks)) + "**",
        "- Marked mastered: **" + str(counts["mastered"]) + "**",
        "- Developing: **" + str(counts["developing"]) + "**",
        "- Needs practice: **" + str(counts["needs practice"]) + "**",
        "",
        "### Recent learning activity",
    ]
    recent = sorted(records, key=lambda item: str(item.get("timestamp") or ""), reverse=True)[:10]
    if not recent:
        lines.append("No lessons or learning checks have been recorded for this learner yet.")
    else:
        lines.extend([
            "| Date | Type | Subject | Topic | Skill / result |",
            "|---|---|---|---|---|",
        ])
        for item in recent:
            is_check = item.get("status") == "parent_or_tutor_observation"
            status_value = item.get("status")
            kind = ("Learning check" if is_check else
                    "Hint requested" if status_value == "hint_requested" else
                    "Student practice" if status_value == "introduced" and "learner_id" not in item else
                    "Lesson introduced")
            result = safe(item.get("performance")) if is_check else ("Hint requested" if status_value == "hint_requested" else "Introduced")
            skill = safe(item.get("skill")) if is_check else result
            date = safe(str(item.get("timestamp") or "")[:10])
            lines.append(
                "| " + date + " | " + kind + " | " + safe(item.get("subject"))
                + " | " + safe(item.get("topic")) + " | " + skill + " |"
            )
    lines.extend([
        "",
        "_This dashboard reports lessons and observations entered by a parent or tutor. "
        "Student practice and hint records are shown separately from parent/tutor observations. "
        "It does not independently test a learner or diagnose a learning condition._",
    ])
    return "\n".join(lines), session


def summarize_account_learning_progress(session, account_data, learner_id=None, parent_access=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return session_status, None
    if not _parent_access_valid(parent_access, session):
        return "Unlock Parent tools again before summarizing learner progress.", session
    records = (account_data or {}).get("learning_progress", [])
    if learner_id:
        records = [item for item in records if item.get("learner_id") == learner_id]
    if not records:
        return "No learning checks have been recorded for this account yet.", session
    # Summarize only this authenticated account's records; never use the
    # legacy shared learning-data file or another learner's history.
    prompt = (
        "Summarize these educational observations for a parent or tutor. "
        "Separate recorded observations from conclusions. Identify skills "
        "marked mastered, developing, or needing practice. Recommend a "
        "small next step. Do not diagnose a disability, infer low ability, "
        "or treat missing records as lack of ability. Be encouraging and concise.\n\n"
        + json.dumps(records[-50:], ensure_ascii=False)
    )
    return ask_llm([{
        "role": "system",
        "content": "You are an educational progress assistant. Do not diagnose or overstate mastery."
    }, {
        "role": "user",
        "content": prompt
    }]), session


def generate_student_activity(activity_type, topic, history, session, account_data, age_group, subject, learner_id=None, student_access=None):
    """Create a child-safe practice activity or hint for the selected learner."""
    history = history or []
    topic = str(topic or "").strip()[:200]
    session, session_status = _renew_account_session(session)
    if not session:
        return history, account_data, session_status, session
    if not topic:
        return history, account_data, "Enter a topic first.", session
    urgent_reply = crisis_response(topic)
    if urgent_reply:
        if not isinstance(account_data, dict):
            account_data = account_store.default_user_memory()
        history = (history or []) + [{"role": "assistant", "content": urgent_reply}]
        account_data.setdefault("chat_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": topic,
            "assistant": urgent_reply,
        })
        account_data["chat_history"] = account_data["chat_history"][-100:]
        saved, status = account_store.save_user_memory(session, account_data)
        return history, account_data, status if saved else "Safety response shown; saving needs attention: " + status, session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()
    if (not isinstance(student_access, dict)
            or student_access.get("learner_id") != learner_id
            or student_access.get("account_user_id") != session.get("user_id")):
        return history, account_data, "Please unlock your student profile first.", session

    learner = next(
        (item for item in account_data.get("learners", []) if item.get("id") == learner_id),
        None,
    )
    if not learner:
        return history, account_data, "Choose a learner profile before starting student activities.", session
    control_message = _parent_control_status(account_data, learner_id, activity_type)
    if control_message:
        return history, account_data, control_message, session

    learner_age = learner.get("age_group", age_group or "elementary")
    activity = "hint" if activity_type == "hint" else "practice"
    prompt = build_student_activity_prompt(
        age_group=learner_age,
        subject=subject or "general learning",
        topic=topic,
        activity=activity,
    )
    reply = ask_llm(prompt)
    if reply.startswith(("Groq returned HTTP", "I couldn't reach", "XEMEX is not connected")):
        return history, account_data, reply, session

    label = "Get a hint for: " if activity == "hint" else "Start student practice: "
    history = history + [{"role": "assistant", "content": reply}]
    account_data.setdefault("chat_history", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": label + topic,
        "assistant": reply,
    })
    account_data["chat_history"] = account_data["chat_history"][-100:]
    account_data.setdefault("learning_progress", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subject": str(subject or "general learning")[:100],
        "topic": topic,
        "age_group": str(learner_age)[:40],
        "learner_id": str(learner_id)[:64],
        "status": "introduced" if activity == "practice" else "hint_requested",
    })
    account_data["learning_progress"] = account_data["learning_progress"][-100:]
    saved, save_status = account_store.save_user_memory(session, account_data)
    if not saved:
        save_status = "Warning: " + save_status
    return history, account_data, save_status, session


def chat_with_xemex(message, history, session, account_data, tutor_enabled=False, age_group="elementary", subject="general learning", learning_goal="understand the topic", student_access=None, learner_id=None, support_mode="tutor"):
    message = (message or "").strip()
    history = history or []
    if not message:
        return history, "", account_data, "", session

    session, session_status = _renew_account_session(session)
    if not session:
        return history, "", account_data, session_status, None

    # All personal context below is scoped to the authenticated account.
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()
    if (not isinstance(student_access, dict)
            or student_access.get("learner_id") != learner_id
            or student_access.get("account_user_id") != session.get("user_id")):
        return history, "", account_data, "Please unlock your student profile first.", session

    safe_history = []
    for item in history[-20:]:
        if isinstance(item, dict):
            role, content = item.get("role"), item.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                safe_history.append({"role": role, "content": content})

    learner_profile = next(
        (item for item in account_data.get("learners", []) if item.get("id") == learner_id),
        None,
    )
    effective_age_group = (
        learner_profile.get("age_group")
        if isinstance(learner_profile, dict)
        else age_group
    ) or age_group or "elementary"

    urgent_reply = crisis_response(message)
    if urgent_reply:
        updated_history = safe_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": urgent_reply},
        ]
        account_data.setdefault("chat_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": message,
            "assistant": urgent_reply,
        })
        account_data["chat_history"] = account_data["chat_history"][-100:]
        saved, save_status = account_store.save_user_memory(session, account_data)
        return updated_history, "", account_data, save_status if saved else "Safety response shown; saving needs attention: " + save_status, session

    if learner_profile and (learner_profile.get("parent_controls") or {}).get("allow_chat", True) is not True:
        return history, "", account_data, "A parent has paused chat for this learner. Please speak with your parent or guardian.", session

    emotion = detect_emotion(message)
    state = account_data.get("emotional_state", {})
    changes = {
        "joy": {"pleasure": 0.10, "trust": 0.03, "humor_warmth": 0.05},
        "sadness": {"pleasure": -0.10, "attachment": 0.03},
        "anger": {"pleasure": -0.10, "arousal": 0.10},
        "fear": {"arousal": 0.10, "attachment": 0.03},
        "surprise": {"arousal": 0.08, "humor_warmth": 0.03},
        "disgust": {"pleasure": -0.08},
    }
    for key, change in changes.get(emotion, {}).items():
        state[key] = clamp(state.get(key, 0.0) + change)
    account_data["emotional_state"] = state
    account_data["interaction_count"] = int(account_data.get("interaction_count", 0)) + 1

    # Remember a name only in the signed-in account's private profile.
    import re
    name_match = re.search(r"\bmy name is\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})", message, re.IGNORECASE)
    if name_match:
        account_data.setdefault("profile", {})["name"] = name_match.group(1).strip().rstrip(" .,!")

    profile_name = account_data.get("profile", {}).get("name", "")
    facts = account_data.get("facts", [])
    known_facts = "\n".join("- " + str(item) for item in facts[-12:]) or "No saved facts yet."
    if profile_name:
        known_facts = "- The user's name is " + profile_name + "\n" + known_facts

    with memory_lock:
        system_prompt = memory["system_prompt"]
        discoveries = "\n".join(str(item) for item in memory["learned_knowledge"][-5:]) or "No independent explorations yet."

    account_data["tutor_settings"] = {
        "age_group": str(age_group or "elementary")[:40],
        "subject": str(subject or "general learning")[:100],
        "learning_goal": str(learning_goal or "understand the topic")[:250],
    }
    tutor_context = build_student_safety_prompt(effective_age_group, support_mode)
    if tutor_enabled and support_mode != "wellbeing":
        age_for_support = {
            "preschool": 4,
            "early_elementary": 7,
            "elementary": 10,
            "teen": 15,
            "adult": 20,
        }.get(effective_age_group, 10)
        tutor_context += (
            "\n\n"
            + build_teaching_prompt(
                age_group=effective_age_group,
                subject=subject,
                learning_goal=learning_goal,
            )
            + "\n\n"
            + build_learning_support_prompt(age=age_for_support)
        )

    lower_message = message.lower()
    coding_request = (
        lower_message.startswith("/code")
        or any(term in lower_message for term in (
            "write python", "write a script", "build a program",
            "create a python", "debug this code"
        ))
    )

    if coding_request and effective_age_group == "adult":
        task = message[5:].strip() if lower_message.startswith("/code") else message
        reply = generate_code(task or message)
    elif coding_request:
        reply = "I can help you understand and learn coding step by step, but the advanced code-generation tool is only available in adult mode. Tell me what you are trying to learn and we can work through it together."
    else:
        system_message = (
            f"{system_prompt}\n\n"
            f"Behavioral state (simulated, account-specific): {json.dumps(state)}\n\n"
            f"Detected user-message emotion: {emotion}\n\n"
            f"Remembered facts for this account only:\n{known_facts}\n\n"
            "IDENTITY ACCURACY:\n"
            "You are XEMEX.AI, running inside a Python application.\n"
            "Your capabilities depend on the tools and services actually connected.\n"
            "Never claim a fixed training cutoff unless it is verified.\n"
            "Never claim to remember information that is not supplied here.\n\n"
            f"Recent general XEMEX explorations:\n{discoveries}\n\n"
            f"{tutor_context}\n\n"
            "Do not reveal or infer information from another account. "
            "Use only the current account's supplied context for personal details."
        )
        messages = [{"role": "system", "content": system_message}]
        messages.extend(safe_history)
        messages.append({"role": "user", "content": message})
        reply = ask_llm(messages)

    updated_history = safe_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]

    if not reply.startswith((
        "Groq returned HTTP", "I couldn't reach", "XEMEX is not connected"
    )):
        account_data.setdefault("chat_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": message,
            "assistant": reply,
        })
        account_data["chat_history"] = account_data["chat_history"][-100:]

    saved, save_status = account_store.save_user_memory(session, account_data)
    if not saved:
        save_status = "Warning: " + save_status
    return updated_history, "", account_data, save_status, session


# =========================================================
# 12. BACKGROUND HEARTBEAT
# =========================================================

def background_heartbeat():
    while True:
        time.sleep(HEARTBEAT_SECONDS)
        try:
            print("XEMEX heartbeat: beginning scheduled work.")
            with memory_lock:
                has_topics = bool(memory["curiosity_topics"])

            if has_topics:
                print(think_independently())

            print(reflect_on_experience())
            print("XEMEX heartbeat: scheduled work finished.")
        except Exception as error:
            print("Heartbeat error:", error)


def start_heartbeat_once():
    global heartbeat_started
    if ENABLE_HEARTBEAT and not heartbeat_started:
        heartbeat_started = True
        threading.Thread(
            target=background_heartbeat,
            daemon=True,
            name="xemex-heartbeat",
        ).start()
        print("XEMEX heartbeat: beginning exploration.")
# =========================================================
# =========================================================

# =========================================================

# =========================================================
# 13. GRADIO INTERFACE
# =========================================================

with gr.Blocks(title="XEMEX.AI", theme=gr.themes.Soft(primary_hue="blue", secondary_hue="blue", neutral_hue="slate")) as app:
    gr.Markdown("# XEMEX.AI")
    gr.Markdown("Your personal AI assistant and learning companion.")

    session_state = gr.State(value=None)
    account_memory_state = gr.State(value=account_store.default_user_memory())
    student_access_state = gr.State(value=None)
    parent_access_state = gr.State(value=None)
    independent_student_state = gr.State(value=None)
    independent_student_memory_state = gr.State(value={})

    with gr.Column(visible=True) as login_panel:
        gr.Markdown("## Welcome to XEMEX.AI")
        gr.Markdown("### Who is signing in?")
        login_role = gr.Radio(
            choices=[("Parent", "parent"), ("Student", "student")],
            value=None,
            label="Choose your account type",
        )

        with gr.Column(visible=False) as parent_login_fields:
            gr.Markdown("### Account sign-in")
            email_input = gr.Textbox(label="Email", placeholder="you@example.com")
            password_input = gr.Textbox(label="Password", type="password")
            with gr.Row():
                sign_in_button = gr.Button("Sign in", variant="primary")
                parent_password_reset_button = gr.Button("Forgot password?")
            parent_password_reset_status = gr.Markdown("")
            gr.Markdown("### Create a XEMEX account")
            registration_setup_for = gr.Radio(
                choices=[("For myself", "self"), ("For my child", "child")],
                value=None,
                label="Who are you setting up XEMEX for?",
            )
            registration_age = gr.Number(label="How old is the learner? (years)", precision=0, minimum=0, maximum=120)
            registration_learner_name = gr.Textbox(label="Child's name or nickname (leave blank for yourself)")
            gr.Markdown("For adult learners (18+), the adult must create their own account for now. Parent-assisted setup will require a separate adult approval step.")
            gr.Markdown("XEMEX currently blocks account creation for children under 13 until a verified parental-consent process and child-privacy safeguards are implemented and tested.")
            create_account_button = gr.Button("Create account", variant="primary")
            auth_status = gr.Markdown("Use your email and password to sign in, or complete the setup questions to create an account.")
            parent_back_button = gr.Button("Back")

        with gr.Column(visible=False) as student_login_fields:
            gr.Markdown("### Student sign-in")
            gr.Markdown("Use the username or email address your parent created for you.")
            independent_student_identifier = gr.Textbox(label="Student username or email")
            independent_student_password = gr.Textbox(label="Student password", type="password")
            independent_student_login_button = gr.Button("Sign in with parent-created student login", variant="primary")
            independent_student_status = gr.Markdown("Your learning history is private to your student account.")
            gr.Markdown("### Create or sign in to your own student account (ages 13+)")
            student_self_email = gr.Textbox(label="Your email address")
            student_self_password = gr.Textbox(label="Your password", type="password")
            student_self_age = gr.Number(label="Your age in years", precision=0, minimum=13, maximum=120)
            student_self_create_button = gr.Button("Create my student account")
            student_self_signin_button = gr.Button("Sign in to my student account")
            student_self_status = gr.Markdown("")
            student_password_reset_button = gr.Button("Forgot student password?")
            student_password_reset_status = gr.Markdown("")
            student_back_button = gr.Button("Back")

    with gr.Column(visible=False) as independent_student_panel:
        gr.Markdown("# XEMEX Student Learning")
        gr.Markdown("Welcome! Your learning history belongs to your student account.")
        gr.Markdown("XEMEX is an AI learning and wellbeing companion, not a therapist or emergency service. This chat is not monitored live. If someone is in immediate danger in the United States, call 911.")
        independent_student_topic = gr.Textbox(label="What would you like to learn?", placeholder="For example: multiplication, planets, or reading")
        with gr.Row():
            independent_student_practice_button = gr.Button("Start practice", variant="primary")
            independent_student_hint_button = gr.Button("Get a hint")
        independent_student_activity_status = gr.Markdown("Choose a topic to begin.")
        independent_student_support_mode = gr.Radio(
            choices=[("Tutor", "tutor"), ("Wellbeing companion", "wellbeing")],
            value="tutor",
            label="How can XEMEX help?",
        )
        independent_student_chatbot = gr.Chatbot(label="Your learning conversation")
        independent_student_message = gr.Textbox(label="Talk with XEMEX", placeholder="Ask a question or tell XEMEX what you are learning.")
        with gr.Row():
            independent_student_send_button = gr.Button("Send", variant="primary")
            independent_student_signout_button = gr.Button("Sign out")
    with gr.Column(visible=False) as chat_panel:
        account_status = gr.Markdown("Signed in.")
        gr.Markdown("XEMEX is an AI learning and wellbeing companion, not a licensed counselor, therapist, or emergency service. Chats are not monitored live.")
        view_mode = gr.Radio(
            choices=[("Student view", "student"), ("Parent view", "parent")],
            value="student",
            label="Choose your XEMEX view",
        )
        with gr.Column(visible=False) as parent_lock_column:
            gr.Markdown("## Parent sign-in")
            gr.Markdown("For privacy on shared devices, enter the parent account password to open settings.")
            parent_reauth_password = gr.Textbox(label="Parent account password", type="password", max_lines=1)
            parent_reauth_button = gr.Button("Unlock parent tools", variant="primary")
            parent_reauth_status = gr.Markdown("Parent tools are locked while a student is using XEMEX.")
        with gr.Column(visible=False) as parent_tools_column:
            with gr.Accordion("Parent tools", open=False):
                tutor_mode = gr.Checkbox(label="Enable child and teen tutoring mode", value=False)
                learner_age_group = gr.Dropdown(                    choices=[
                        ("Early childhood (0–5)", "preschool"),
                        ("Early elementary (6–8)", "early_elementary"),
                        ("Elementary (9–12)", "elementary"),
                        ("Teen (13–17)", "teen"),
                        ("Adult / college", "adult"),
                    ],
                    value="elementary",
                    label="Learner age group",
                )
                learner_subject = gr.Textbox(label="Subject", value="General learning")
                learner_goal = gr.Textbox(label="Learning goal", value="Understand the topic")
                lesson_topic = gr.Textbox(label="Start a lesson on", placeholder="For example: fractions, reading, or planets")
                lesson_button = gr.Button("Create an interactive lesson")
                gr.Markdown("### Learner profiles")
                learner_name_input = gr.Textbox(label="New learner name or nickname", placeholder="For example: Student 1")
                learner_creation_age = gr.Number(label="Learner age (years)", precision=0, minimum=0, maximum=120)
                gr.Markdown("Under-13 profiles require a verified parental-consent process, which is not yet integrated. Adult learners must create their own account.")
                create_learner_button = gr.Button("Create learner profile")
                learner_profile = gr.Dropdown(label="Active learner profile", choices=[], value=None)
                learner_profile_status = gr.Markdown("Create a profile for each child or teen. Profiles and progress are private to this account.")
                gr.Markdown("### Learning progress")
                progress_topic = gr.Textbox(label="Topic", placeholder="For example: fractions")
                progress_skill = gr.Textbox(label="Skill observed", placeholder="For example: adding fractions with like denominators")
                progress_performance = gr.Dropdown(
                    choices=["mastered", "developing", "needs practice", "not yet assessed"],
                    value="not yet assessed",
                    label="Observed performance",
                )
                progress_notes = gr.Textbox(label="Notes (optional)", lines=2)
                with gr.Row():
                    save_progress_button = gr.Button("Save learning check")
                    summarize_progress_button = gr.Button("Summarize progress")
                progress_status = gr.Markdown("Progress is saved privately to the signed-in account.")
                gr.Markdown("### Parent dashboard")
                refresh_dashboard_button = gr.Button("Refresh parent dashboard")
                parent_dashboard = gr.Markdown("Choose a learner profile, then refresh the dashboard.")
                gr.Markdown("### Privacy and account controls")
                export_data_button = gr.Button("Export my XEMEX data")
                data_export_file = gr.File(label="Your data export", interactive=False)
                data_export_status = gr.Markdown("Export includes account memory and linked student account data, excluding password hashes.")
                gr.Markdown("#### Delete account permanently")
                delete_account_password = gr.Textbox(label="Confirm your current account password", type="password")
                delete_account_confirmation = gr.Textbox(label='Type DELETE to confirm')
                delete_account_button = gr.Button("Permanently delete my XEMEX account", variant="stop")
                delete_account_status = gr.Markdown("Account deletion requires parent-tools unlock and password confirmation. Linked student records are deleted with the parent account.")
                gr.Markdown("### Parent safety controls")
                parent_allow_chat = gr.Checkbox(label="Allow student chat", value=True)
                parent_allow_practice = gr.Checkbox(label="Allow practice activities", value=True)
                parent_allow_hints = gr.Checkbox(label="Allow hints", value=True)
                parent_daily_limit = gr.Dropdown(
                    choices=[("5 activities per day", "5"), ("10 activities per day", "10"),
                             ("15 activities per day", "15"), ("20 activities per day", "20"),
                             ("30 activities per day", "30"), ("No daily activity cap", "0")],
                    value="20",
                    label="Daily learning activity limit",
                )
                save_parent_controls_button = gr.Button("Save parent safety settings")
                parent_controls_status = gr.Markdown("Settings apply to the selected learner's chat, practice, and hint activities.")
                gr.Markdown("### Student sign-in PIN")
                parent_pin_input = gr.Textbox(label="Create a six-digit student PIN", type="password", max_lines=1)
                parent_pin_confirm = gr.Textbox(label="Confirm student PIN", type="password", max_lines=1)
                save_student_pin_button = gr.Button("Save student PIN")
                student_pin_status = gr.Markdown("Set a PIN for the selected learner. Only a salted hash is stored.")
                gr.Markdown("### Independent student sign-in")
                student_username_input = gr.Textbox(label="Student username (3–24 characters)")
                student_email_input = gr.Textbox(label="Student email (optional)")
                student_password_input = gr.Textbox(label="Create student password (10+ characters)", type="password")
                create_student_login_button = gr.Button("Create student username and password")
                student_login_management_status = gr.Markdown("Create a separate student login for the selected learner.")
                student_password_reset_input = gr.Textbox(label="New student password", type="password")
                reset_student_password_button = gr.Button("Reset selected learner's password")
        with gr.Column(visible=True) as student_lock_column:
            gr.Markdown("## Student sign-in")
            gr.Markdown("Choose your profile and enter the six-digit PIN your parent gave you.")
            student_profile = gr.Dropdown(label="Your learner profile", choices=[], value=None)
            student_pin_input = gr.Textbox(label="Six-digit PIN", type="password", max_lines=1)
            unlock_student_button = gr.Button("Unlock my learning space", variant="primary")
            student_lock_status = gr.Markdown("Ask a parent to create your profile and PIN if you are not set up yet.")
        with gr.Column(visible=False) as student_workspace_column:
            gr.Markdown("## Your learning space")
            gr.Markdown("Welcome! Choose something you want to learn. You can practice, ask for a hint, or talk with XEMEX.")
            student_topic = gr.Textbox(label="What would you like to learn?", placeholder="For example: multiplication, planets, or reading")
            with gr.Row():
                student_practice_button = gr.Button("Start practice", variant="primary")
                student_hint_button = gr.Button("Get a hint")
            student_activity_status = gr.Markdown("Choose your learner profile in Parent view before starting.")
            chatbot = gr.Chatbot(label="Your learning conversation")
            support_mode = gr.Radio(
                choices=[("Tutor", "tutor"), ("Wellbeing companion", "wellbeing")],
                value="tutor",
                label="How can XEMEX help?",
            )
            message = gr.Textbox(placeholder="Talk to XEMEX...", label="Your message")
            with gr.Row():
                send_button = gr.Button("Send", variant="primary")
                clear = gr.Button("Clear conversation")
        sign_out_button = gr.Button("Sign out")

    auth_outputs = [
        session_state, account_memory_state, chatbot,
        auth_status, account_status, login_panel, chat_panel,
        learner_age_group, learner_subject, learner_goal, learner_profile
    ]
    login_role.change(
        update_login_role,
        inputs=[login_role],
        outputs=[parent_login_fields, student_login_fields],
    )
    parent_back_button.click(
        reset_login_role,
        outputs=[login_role, parent_login_fields, student_login_fields],
    )
    student_back_button.click(
        reset_login_role,
        outputs=[login_role, parent_login_fields, student_login_fields],
    )
    sign_in_button.click(
        sign_in_account,
        inputs=[email_input, password_input],
        outputs=auth_outputs,
    ).then(
        restore_self_learner,
        inputs=[session_state, account_memory_state],
        outputs=[student_access_state, student_lock_column, student_workspace_column, student_profile, learner_age_group],
    )
    parent_password_reset_button.click(
        send_password_reset,
        inputs=[email_input],
        outputs=[parent_password_reset_status],
    )
    independent_student_login_button.click(
        sign_in_independent_student,
        inputs=[independent_student_identifier, independent_student_password],
        outputs=[
            independent_student_state, independent_student_memory_state,
            independent_student_chatbot, independent_student_status,
            login_panel, independent_student_panel,
        ],
    )
    student_self_create_button.click(
        create_student_self_account,
        inputs=[student_self_email, student_self_password, student_self_age],
        outputs=auth_outputs + [student_self_status],
    ).then(
        restore_self_learner,
        inputs=[session_state, account_memory_state],
        outputs=[student_access_state, student_lock_column, student_workspace_column, student_profile, learner_age_group],
    )
    student_self_signin_button.click(
        sign_in_self_student_account,
        inputs=[student_self_email, student_self_password],
        outputs=auth_outputs + [student_self_status],
    ).then(
        restore_self_learner,
        inputs=[session_state, account_memory_state],
        outputs=[student_access_state, student_lock_column, student_workspace_column, student_profile, learner_age_group],
    )
    student_password_reset_button.click(
        send_password_reset,
        inputs=[student_self_email],
        outputs=[student_password_reset_status],
    )
    create_account_button.click(
        create_account,
        inputs=[email_input, password_input, registration_setup_for, registration_age, registration_learner_name],
        outputs=auth_outputs,
    ).then(
        restore_self_learner,
        inputs=[session_state, account_memory_state],
        outputs=[student_access_state, student_lock_column, student_workspace_column, student_profile, learner_age_group],
    )

    view_mode.change(
        switch_xemex_view,
        inputs=[view_mode, student_access_state, parent_access_state, session_state],
        outputs=[parent_tools_column, parent_lock_column, student_workspace_column, student_lock_column, student_access_state, parent_access_state],
    )
    parent_reauth_button.click(
        unlock_parent_tools,
        inputs=[parent_reauth_password, session_state],
        outputs=[parent_access_state, parent_reauth_status, session_state, parent_tools_column, parent_lock_column],
    )
    export_data_button.click(
        export_account_data,
        inputs=[session_state, parent_access_state],
        outputs=[data_export_file, data_export_status],
    )
    delete_account_button.click(
        delete_account_from_settings,
        inputs=[delete_account_password, delete_account_confirmation, session_state, parent_access_state, account_memory_state, chatbot],
        outputs=[session_state, account_memory_state, chatbot, delete_account_status, login_panel, chat_panel, student_access_state, parent_access_state],
    )
    account_memory_state.change(
        learner_profile_choices,
        inputs=[account_memory_state, student_profile],
        outputs=[student_profile],
    )
    unlock_student_button.click(
        unlock_student_workspace,
        inputs=[student_profile, student_pin_input, session_state, account_memory_state],
        outputs=[student_access_state, student_lock_status, session_state, student_workspace_column, student_lock_column],
    )
    save_student_pin_button.click(
        set_learner_student_pin,
        inputs=[learner_profile, parent_pin_input, parent_pin_confirm, session_state, account_memory_state, parent_access_state],
        outputs=[account_memory_state, student_pin_status, session_state],
    )
    create_student_login_button.click(
        create_independent_student_login,
        inputs=[learner_profile, student_username_input, student_email_input, student_password_input, session_state, parent_access_state],
        outputs=[student_login_management_status, session_state],
    )
    reset_student_password_button.click(
        reset_independent_student_password,
        inputs=[learner_profile, student_password_reset_input, session_state, parent_access_state],
        outputs=[student_login_management_status, session_state],
    )
    chat_inputs = [message, chatbot, session_state, account_memory_state, tutor_mode, learner_age_group, learner_subject, learner_goal, student_access_state, student_profile, support_mode]
    chat_outputs = [chatbot, message, account_memory_state, account_status, session_state]
    message.submit(chat_with_xemex, inputs=chat_inputs, outputs=chat_outputs)
    send_button.click(chat_with_xemex, inputs=chat_inputs, outputs=chat_outputs)
    student_activity_inputs = [
        student_topic, chatbot, session_state, account_memory_state,
        learner_age_group, learner_subject, student_profile, student_access_state,
    ]
    student_activity_outputs = [chatbot, account_memory_state, student_activity_status, session_state]
    student_practice_button.click(
        lambda topic, history, session, data, age, subject, learner, access: generate_student_activity(
            "practice", topic, history, session, data, age, subject, learner, access
        ),
        inputs=student_activity_inputs,
        outputs=student_activity_outputs,
    )
    student_hint_button.click(
        lambda topic, history, session, data, age, subject, learner, access: generate_student_activity(
            "hint", topic, history, session, data, age, subject, learner, access
        ),
        inputs=student_activity_inputs,
        outputs=student_activity_outputs,
    )
    lesson_button.click(
        start_tutoring_lesson,
        inputs=[lesson_topic, chatbot, session_state, account_memory_state, learner_age_group, learner_subject, learner_profile, parent_access_state],
        outputs=[chatbot, account_memory_state, account_status, lesson_topic, session_state],
    )
    save_progress_button.click(
        record_account_learning_progress,
        inputs=[
            progress_topic, progress_skill, progress_performance, progress_notes,
            session_state, account_memory_state, learner_age_group, learner_subject, learner_profile, parent_access_state,
        ],
        outputs=[account_memory_state, progress_status, session_state],
    )
    summarize_progress_button.click(
        summarize_account_learning_progress,
        inputs=[session_state, account_memory_state, learner_profile, parent_access_state],
        outputs=[progress_status, session_state],
    )
    refresh_dashboard_button.click(
        build_parent_dashboard,
        inputs=[session_state, account_memory_state, learner_profile, parent_access_state],
        outputs=[parent_dashboard, session_state],
    )
    create_learner_button.click(
        create_learner_profile,
        inputs=[learner_name_input, learner_creation_age, session_state, account_memory_state, parent_access_state],
        outputs=[account_memory_state, learner_profile, learner_profile_status, session_state],
    )
    learner_profile.change(
        select_learner_profile,
        inputs=[learner_profile, account_memory_state],
        outputs=[learner_age_group, learner_profile_status],
    )
    learner_profile.change(
        load_parent_controls,
        inputs=[learner_profile, account_memory_state],
        outputs=[parent_allow_chat, parent_allow_practice, parent_allow_hints, parent_daily_limit],
    )
    save_parent_controls_button.click(
        save_parent_controls,
        inputs=[
            learner_profile, parent_allow_chat, parent_allow_practice, parent_allow_hints,
            parent_daily_limit, session_state, account_memory_state, parent_access_state,
        ],
        outputs=[account_memory_state, parent_controls_status, session_state],
    )

    clear.click(lambda: ([], ""), outputs=[chatbot, message])
    independent_student_message.submit(
        independent_student_chat,
        inputs=[independent_student_message, independent_student_chatbot, independent_student_state, independent_student_memory_state, independent_student_support_mode],
        outputs=[independent_student_chatbot, independent_student_message, independent_student_memory_state, independent_student_status],
    )
    independent_student_send_button.click(
        independent_student_chat,
        inputs=[independent_student_message, independent_student_chatbot, independent_student_state, independent_student_memory_state, independent_student_support_mode],
        outputs=[independent_student_chatbot, independent_student_message, independent_student_memory_state, independent_student_status],
    )
    independent_student_practice_button.click(
        lambda topic, history, session, memory: independent_student_activity("practice", topic, history, session, memory),
        inputs=[independent_student_topic, independent_student_chatbot, independent_student_state, independent_student_memory_state],
        outputs=[independent_student_chatbot, independent_student_memory_state, independent_student_activity_status],
    )
    independent_student_hint_button.click(
        lambda topic, history, session, memory: independent_student_activity("hint", topic, history, session, memory),
        inputs=[independent_student_topic, independent_student_chatbot, independent_student_state, independent_student_memory_state],
        outputs=[independent_student_chatbot, independent_student_memory_state, independent_student_activity_status],
    )
    independent_student_signout_button.click(
        sign_out_independent_student,
        inputs=[independent_student_state],
        outputs=[
            independent_student_state, independent_student_memory_state,
            independent_student_chatbot, independent_student_status,
            login_panel, independent_student_panel,
        ],
    )

    sign_out_button.click(
        sign_out_account_and_lock_student,
        inputs=[session_state],
        outputs=auth_outputs + [student_access_state, parent_access_state],
    )


# =========================================================
# 14. APPLICATION STARTUP
# =========================================================

if __name__ == "__main__":

    start_heartbeat_once()

    port = int(os.environ.get("PORT", 10000))

    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        show_error=os.environ.get("XEMEX_SHOW_ERRORS", "false").lower() == "true"
    )