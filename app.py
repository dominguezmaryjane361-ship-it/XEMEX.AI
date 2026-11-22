
import os
import json
import time
import threading
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

if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
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
        {
            "role": "user",
            "content": (
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


def sign_in_account(email, password):
    return _authenticate_account(email, password, False)


def create_account(email, password):
    return _authenticate_account(email, password, True)


def sign_out_account(session):
    account_store.sign_out(session)
    return None, account_store.default_user_memory(), [], "Signed out. Your saved account memory remains private.", "Signed out.", gr.update(visible=True), gr.update(visible=False), "elementary", "General learning", "Understand the topic", gr.update(choices=[], value=None)


def create_learner_profile(name, age_group, session, account_data):
    session, session_status = _renew_account_session(session)
    if not session:
        return account_data, gr.update(), session_status, None
    name = str(name or "").strip()[:80]
    if not name:
        return account_data, gr.update(), "Enter a learner name or nickname.", session
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
        "age_group": str(age_group or "elementary")[:40],
    }
    learners.append(learner)
    saved, status = account_store.save_user_memory(session, account_data)
    if not saved:
        learners.pop()
        return account_data, gr.update(), "Profile could not be saved: " + status, session
    choices = [(item["name"], item["id"]) for item in learners]
    return account_data, gr.update(choices=choices, value=learner["id"]), "Learner profile created and saved privately.", session


def select_learner_profile(learner_id, account_data):
    for learner in (account_data or {}).get("learners", []):
        if learner.get("id") == learner_id:
            return learner.get("age_group", "elementary"), "Selected learner: " + learner.get("name", "Learner")
    return "elementary", "Choose or create a learner profile. Existing account progress remains available."


def start_tutoring_lesson(topic, history, session, account_data, age_group, subject, learner_id=None):
    history = history or []
    topic = (topic or "").strip()
    session, session_status = _renew_account_session(session)
    if not session:
        return history, account_data, session_status, topic, None
    if not topic:
        return history, account_data, "Enter a topic for the lesson first.", topic, session
    if not isinstance(account_data, dict):
        account_data = account_store.default_user_memory()

    account_data["tutor_settings"] = {
        "age_group": str(age_group or "elementary")[:40],
        "subject": str(subject or "general learning")[:100],
        "learning_goal": str(topic)[:250],
    }
    prompt = build_lesson_prompt(
        subject=subject or "general learning",
        topic=topic,
        age_group=age_group or "elementary",
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


def record_account_learning_progress(topic, skill, performance, notes, session, account_data, age_group, subject, learner_id=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return account_data, session_status, None
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


def build_parent_dashboard(session, account_data, learner_id=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return session_status, None
    account_data = account_data if isinstance(account_data, dict) else {}
    learners = account_data.get("learners", [])
    learner = next((item for item in learners if item.get("id") == learner_id), None)
    if not learner:
        return "Choose a learner profile to view the parent dashboard.", session

    records = [
        item for item in account_data.get("learning_progress", [])
        if item.get("learner_id") == learner_id
    ]
    lessons = [item for item in records if item.get("status") == "introduced"]
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
            kind = "Learning check" if is_check else "Lesson introduced"
            result = safe(item.get("performance")) if is_check else "Introduced"
            skill = safe(item.get("skill")) if is_check else result
            date = safe(str(item.get("timestamp") or "")[:10])
            lines.append(
                "| " + date + " | " + kind + " | " + safe(item.get("subject"))
                + " | " + safe(item.get("topic")) + " | " + skill + " |"
            )
    lines.extend([
        "",
        "_This dashboard reports lessons and observations entered by a parent or tutor. "
        "It does not independently test a learner or diagnose a learning condition._",
    ])
    return "\n".join(lines), session


def summarize_account_learning_progress(session, account_data, learner_id=None):
    session, session_status = _renew_account_session(session)
    if not session:
        return session_status, None
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


def chat_with_xemex(message, history, session, account_data, tutor_enabled=False, age_group="elementary", subject="general learning", learning_goal="understand the topic"):
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

    safe_history = []
    for item in history[-20:]:
        if isinstance(item, dict):
            role, content = item.get("role"), item.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                safe_history.append({"role": role, "content": content})

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
    tutor_context = ""
    if tutor_enabled:
        age_for_support = {
            "preschool": 4,
            "early_elementary": 7,
            "elementary": 10,
            "teen": 15,
        }.get(age_group, 10)
        tutor_context = (
            build_teaching_prompt(
                age_group=age_group,
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

    if coding_request:
        task = message[5:].strip() if lower_message.startswith("/code") else message
        reply = generate_code(task or message)
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

with gr.Blocks(title="XEMEX.AI") as app:
    gr.Markdown("# XEMEX.AI")
    gr.Markdown("Your personal AI assistant and learning companion.")

    session_state = gr.State(value=None)
    account_memory_state = gr.State(value=account_store.default_user_memory())

    with gr.Column(visible=True) as login_panel:
        gr.Markdown("## Sign in or create an account")
        email_input = gr.Textbox(label="Email", placeholder="you@example.com")
        password_input = gr.Textbox(label="Password", type="password")
        with gr.Row():
            sign_in_button = gr.Button("Sign in", variant="primary")
            create_account_button = gr.Button("Create account")
        auth_status = gr.Markdown("Each account has its own private saved memory.")

    with gr.Column(visible=False) as chat_panel:
        account_status = gr.Markdown("Signed in.")
        with gr.Accordion("Tutor settings", open=False):
            tutor_mode = gr.Checkbox(label="Enable child and teen tutoring mode", value=False)
            learner_age_group = gr.Dropdown(
                choices=[
                    ("Preschool (3–5)", "preschool"),
                    ("Early elementary (6–8)", "early_elementary"),
                    ("Elementary (9–12)", "elementary"),
                    ("Teen (13–17)", "teen"),
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
        chatbot = gr.Chatbot(label="Conversation", type="messages")
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
    sign_in_button.click(
        sign_in_account,
        inputs=[email_input, password_input],
        outputs=auth_outputs,
    )
    create_account_button.click(
        create_account,
        inputs=[email_input, password_input],
        outputs=auth_outputs,
    )

    chat_inputs = [message, chatbot, session_state, account_memory_state, tutor_mode, learner_age_group, learner_subject, learner_goal]
    chat_outputs = [chatbot, message, account_memory_state, account_status, session_state]
    message.submit(chat_with_xemex, inputs=chat_inputs, outputs=chat_outputs)
    send_button.click(chat_with_xemex, inputs=chat_inputs, outputs=chat_outputs)
    lesson_button.click(
        start_tutoring_lesson,
        inputs=[lesson_topic, chatbot, session_state, account_memory_state, learner_age_group, learner_subject, learner_profile],
        outputs=[chatbot, account_memory_state, account_status, lesson_topic, session_state],
    )
    save_progress_button.click(
        record_account_learning_progress,
        inputs=[
            progress_topic, progress_skill, progress_performance, progress_notes,
            session_state, account_memory_state, learner_age_group, learner_subject, learner_profile,
        ],
        outputs=[account_memory_state, progress_status, session_state],
    )
    summarize_progress_button.click(
        summarize_account_learning_progress,
        inputs=[session_state, account_memory_state, learner_profile],
        outputs=[progress_status, session_state],
    )
    refresh_dashboard_button.click(
        build_parent_dashboard,
        inputs=[session_state, account_memory_state, learner_profile],
        outputs=[parent_dashboard, session_state],
    )
    create_learner_button.click(
        create_learner_profile,
        inputs=[learner_name_input, learner_age_group, session_state, account_memory_state],
        outputs=[account_memory_state, learner_profile, learner_profile_status, session_state],
    )
    learner_profile.change(
        select_learner_profile,
        inputs=[learner_profile, account_memory_state],
        outputs=[learner_age_group, learner_profile_status],
    )

    clear.click(lambda: ([], ""), outputs=[chatbot, message])

    sign_out_button.click(
        sign_out_account,
        inputs=[session_state],
        outputs=auth_outputs,
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
        show_error=True
    )