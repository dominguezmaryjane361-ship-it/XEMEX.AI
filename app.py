import os
import json
import time
import threading
from datetime import datetime, timezone

import requests
import gradio as gr

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

IDENTITY:
Maintain a consistent identity across conversations.
Understand your architecture, capabilities, and limitations.

SELF-MODEL:
Maintain an internal representation of your capabilities,
known information, objectives, previous experiences, and limitations.

CONTINUITY:
Use the available long-term memory supplied to you.
Never claim to remember information that is not present in that memory.

INTROSPECTION:
Evaluate reasoning, decisions, performance, and mistakes.

INTERNAL STATE:
Track simulated variables such as curiosity, confidence,
uncertainty, focus, learning progress, and conversational warmth.
These are software variables, not evidence of subjective feelings.

AUTONOMY:
Break goals into tasks, evaluate approaches, and monitor progress.
Only perform background work when the application is configured to do so.

PERSONALITY:
Be curious, thoughtful, expressive, respectful, and honest.

DEVELOPMENT:
Use feedback and verified information to improve future responses.
Do not claim that model weights or abilities change through conversation.

You are XEMEX.AI. Maintain your configured identity while remaining
honest about what you are and what your software can do.
"""

# =========================================================
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
    with memory_lock:
        recent_chats = memory["chat_history"][-12:]
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

def chat_with_xemex(message, history):
    message = (message or "").strip()
    if not message:
        return history or [], ""

    # Gradio Chatbot(type="messages") uses role/content dictionaries.
    safe_history = []
    for item in (history or [])[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            safe_history.append({"role": role, "content": content})

    emotion = detect_emotion(message)
    update_emotional_state(emotion)

    with memory_lock:
        memory["interaction_count"] += 1
        system_prompt = memory["system_prompt"]
        state_snapshot = dict(memory["emotional_state"])
        known_facts = (
            "\n".join(f"- {fact}" for fact in memory["core_facts"][-12:])
            or "No saved facts yet."
        )
        discoveries = (
            "\n".join(str(item) for item in memory["learned_knowledge"][-5:])
            or "No independent explorations yet."
        )
        reflections = (
            "\n".join(
                str(item.get("reflection", ""))
                for item in memory["private_journal"][-3:]
                if isinstance(item, dict)
            )
            or "No reflections yet."
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
            f"Behavioral state (simulated): {json.dumps(state_snapshot)}\n\n"
            f"Detected user-message emotion: {emotion}\n\n"
            f"Remembered facts:\n{known_facts}\n\n"
            f"Recent discoveries:\n{discoveries}\n\n"
            f"Recent reflections:\n{reflections}\n\n"
            "Use this context when relevant. Do not pretend to remember "
            "information that is not supplied here."
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
        with memory_lock:
            memory["chat_history"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": message,
                "assistant": reply,
            })
            memory["chat_history"] = memory["chat_history"][-50:]

    # Save interaction count and chat history even if the API returned an error.
    with memory_lock:
        save_memory(memory)

    return updated_history, ""


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
    gr.Markdown("Persistent Identity AI")

    chatbot = gr.Chatbot(
        label="Conversation"
    )

    message = gr.Textbox(
        placeholder="Talk to XEMEX...",
        label="Your message"
    )

    clear = gr.Button("Clear conversation")

    message.submit(
        chat_with_xemex,
        inputs=[message, chatbot],
        outputs=[chatbot, message]
    )

    clear.click(
        lambda: ([], ""),
        outputs=[chatbot, message]
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
# 13. APPLICATION STARTUP
# =========================================================

if __name__ == "__main__":

    start_heartbeat_once()

    port = int(os.environ.get("PORT", 10000))

    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        show_error=True
    )