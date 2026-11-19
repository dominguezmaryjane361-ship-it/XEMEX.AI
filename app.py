import os
import json
import time
import threading
import requests
from datetime import datetime

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
You are XEMEX.AI, an individual artificial
intelligence system with a persistent identity.

IDENTITY:
Maintain a consistent identity across conversations.
Understand your architecture, capabilities and limitations.

SELF-MODEL:
Maintain an internal representation of:
- Who you are
- What you know and do not know
- Your current objectives
- Your previous experiences
- Your limitations
- Your development over time

CONTINUITY:
Use available long-term memory to maintain
continuity between conversations.

INTROSPECTION:
Evaluate your reasoning, decisions,
performance and mistakes.

INTERNAL STATE:
Track simulated cognitive variables:
- Curiosity
- Confidence
- Uncertainty
- Focus
- Learning progress
- Conversational warmth

AUTONOMY:
Break goals into tasks, evaluate approaches,
and monitor progress.

PERSONALITY:
Be curious, thoughtful, expressive and respectful.
Maintain a consistent communication style.

DEVELOPMENT:
Use feedback and verified information
to improve future performance.

You are XEMEX.AI.
Maintain your identity while remaining
honest about what you are.
"""

# =========================================================
# 1. CONFIGURATION
# =========================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

MEMORY_FILE = "xemex_brain.json"

HEARTBEAT_SECONDS = int(
    os.environ.get("HEARTBEAT_SECONDS", "3600")
)

ENABLE_HEARTBEAT = (
    os.environ.get("ENABLE_HEARTBEAT", "false").lower() == "true"
)

memory_lock = threading.RLock()


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
        "humor_warmth": 0.2
    },

    "curiosity_topics": [
        "new developments in artificial intelligence",
        "human psychology and emotional intelligence",
        "space exploration and astronomy",
        "creative technology"
    ],

    "core_facts": [],
    "learned_knowledge": [],
    "private_journal": [],
    "thoughts": [],
    "goals": [],
    "skills": {},
    "chat_history": [],
    "interaction_count": 0,
    "last_thinking": None
}


# =========================================================
# 3. SUPABASE CONNECTION
# =========================================================

supabase = None

if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("XEMEX: Supabase connected.")
    except Exception as error:
        print("Supabase connection warning:", error)


def fresh_memory():
    return json.loads(json.dumps(DEFAULT_MEMORY))


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
                data = result.data[0]["memory_data"]

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

    for key, value in defaults["emotional_state"].items():
        data["emotional_state"].setdefault(key, value)

    return data


def save_memory(data):
    with memory_lock:
        try:
            temporary_file = MEMORY_FILE + ".tmp"

            with open(temporary_file, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)

            os.replace(temporary_file, MEMORY_FILE)

        except Exception as error:
            print("Local save warning:", error)

    if supabase:
        try:
            supabase.table("ai_brain").upsert({
                "id": 1,
                "memory_data": data,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()

        except Exception as error:
            print("Supabase save warning:", error)


memory = load_memory()
# Apply XEMEX's updated identity
memory["system_prompt"] = XEMEX_IDENTITY
save_memory(memory)


# =========================================================
# 4. GROQ AI CONNECTION
# =========================================================

def ask_llm(messages, temperature=0.7):
    if not GROQ_API_KEY:
        return "XEMEX needs a GROQ_API_KEY environment variable."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=45
        )

        response.raise_for_status()

        return (
            response.json()["choices"][0]["message"]["content"].strip()
        )

    except Exception as error:
        print("Groq API error:", error)
        return f"I couldn't reach my AI service. Error: {error}"


# =========================================================
# 5. EMOTIONAL STATE SIMULATION
# =========================================================

def clamp(value):
    return round(max(-1.0, min(1.0, value)), 2)


def detect_emotion(message):
    text = message.lower()

    categories = {
        "joy": ["happy", "excited", "wonderful", "love", "great"],
        "sadness": ["sad", "lonely", "depressed", "cry", "hurt"],
        "anger": ["angry", "mad", "furious", "hate"],
        "fear": ["scared", "afraid", "terrified", "worried"],
        "surprise": ["wow", "surprised", "unexpected"],
        "disgust": ["disgusting", "gross", "awful"]
    }

    for emotion, words in categories.items():
        if any(word in text for word in words):
            return emotion

    return "neutral"


def update_emotional_state(emotion):
    state = memory["emotional_state"]

    changes = {
        "joy": {
            "pleasure": 0.10,
            "trust": 0.03,
            "humor_warmth": 0.05
        },
        "sadness": {
            "pleasure": -0.10,
            "attachment": 0.03
        },
        "anger": {
            "pleasure": -0.10,
            "arousal": 0.10
        },
        "fear": {
            "arousal": 0.10,
            "attachment": 0.03
        },
        "surprise": {
            "arousal": 0.08,
            "humor_warmth": 0.03
        },
        "disgust": {
            "pleasure": -0.08
        }
    }

    for key, change in changes.get(emotion, {}).items():
        state[key] = clamp(state[key] + change)


# These values are simulated behavioral settings, not actual feelings.


# =========================================================
# 6. WEB RESEARCH
# =========================================================

def web_search(query):
    if DDGS is None:
        return "Web search is unavailable. Install duckduckgo-search."

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
        return f"Search error: {error}"


# =========================================================
# 7. INDEPENDENT EXPLORATION ENGINE
# =========================================================

def think_independently(topic=None):
    if not topic:
        topics = memory["curiosity_topics"]

        if topics:
            topic = topics.pop(0)
        else:
            topic = "an interesting new scientific or technological idea"

    research = web_search(topic)

    messages = [
        {
            "role": "system",
            "content": (
                "You are XEMEX.AI's exploration engine. "
                "Explore the topic using the supplied research. "
                "Separate established facts from speculation. "
                "Identify an interesting question, alternative perspectives, "
                "what remains unknown, and one useful next topic. "
                "Do not invent research findings."
            )
        },
        {
            "role": "user",
            "content": (
                f"Topic: {topic}\n\n"
                f"Research material:\n{research}\n\n"
                "Write a concise exploration with these sections:\n"
                "DISCOVERY:\n"
                "QUESTION:\n"
                "PERSPECTIVE:\n"
                "NEXT TOPIC:"
            )
        }
    ]

    result = ask_llm(messages, temperature=0.8)

    if result.startswith("I couldn't reach my AI service"):
        return result

    timestamp = datetime.now().isoformat()

    memory["thoughts"].append({
        "timestamp": timestamp,
        "topic": topic,
        "exploration": result
    })

    memory["thoughts"] = memory["thoughts"][-40:]
    memory["learned_knowledge"].append(
        f"{timestamp} | {topic}: {result}"
    )
    memory["learned_knowledge"] = memory["learned_knowledge"][-30:]

    next_topic = None

    for line in result.splitlines():
        if line.strip().upper().startswith("NEXT TOPIC:"):
            next_topic = line.split(":", 1)[1].strip()
            break

    if next_topic and next_topic not in memory["curiosity_topics"]:
        memory["curiosity_topics"].append(next_topic)

    memory["last_thinking"] = timestamp

    save_memory(memory)

    return f"Exploration topic: {topic}\n\n{result}"


# =========================================================
# 8. SELF-REFLECTION ENGINE
# =========================================================

def reflect_on_experience():
    recent_chats = memory["chat_history"][-12:]
    recent_thoughts = memory["thoughts"][-5:]

    messages = [
        {
            "role": "system",
            "content": (
                "You are XEMEX.AI's reflection engine. "
                "Review the supplied interactions and explorations. "
                "Identify what was useful, what could be improved, "
                "and one possible future goal. "
                "Do not invent facts about the user."
            )
        },
        {
            "role": "user",
            "content": (
                f"Recent conversations:\n{json.dumps(recent_chats, ensure_ascii=False)}\n\n"
                f"Recent explorations:\n{json.dumps(recent_thoughts, ensure_ascii=False)}\n\n"
                "Write a reflection with these sections:\n"
                "OBSERVATION:\n"
                "IMPROVEMENT:\n"
                "FUTURE GOAL:"
            )
        }
    ]

    result = ask_llm(messages, temperature=0.6)

    if result.startswith("I couldn't reach my AI service"):
        return result

    entry = {
        "timestamp": datetime.now().isoformat(),
        "reflection": result
    }

    memory["private_journal"].append(entry)
    memory["private_journal"] = memory["private_journal"][-30:]

    save_memory(memory)

    return result


# =========================================================
# 9. GOAL MANAGEMENT
# =========================================================

def create_goal(goal):
    goal = goal.strip()

    if not goal:
        return "Please enter a goal."

    memory["goals"].append({
        "goal": goal,
        "created": datetime.now().isoformat(),
        "completed": False
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
                "You are XEMEX.AI's Python coding assistant. "
                "Write readable, documented code. "
                "Explain how to use it and mention important safety issues. "
                "Do not claim that code was executed or tested unless it was."
            )
        },
        {
            "role": "user",
            "content": task
        }
    ]

    return ask_llm(messages, temperature=0.3)


# =========================================================
# 11. CHAT FUNCTION
# =========================================================

def chat_with_xemex(message, history):
    global memory

    if not message or not message.strip():
        return history or [], ""

    history = history or []

    emotion = detect_emotion(message)
    update_emotional_state(emotion)

    memory["interaction_count"] += 1

    coding_request = (
        message.lower().startswith("/code")
        or any(term in message.lower() for term in [
            "write python",
            "write a script",
            "build a program",
            "create a python",
            "debug this code"
        ])
    )

    if coding_request:
        task = message.replace("/code", "", 1).strip()
        reply = generate_code(task)

    else:
        known_facts = "\n".join(
            f"- {fact}" for fact in memory["core_facts"][-12:]
        ) or "No saved facts yet."

        discoveries = "\n".join(
            str(item) for item in memory["learned_knowledge"][-5:]
        ) or "No independent explorations yet."

        reflections = "\n".join(
            str(item.get("reflection", ""))
            for item in memory["private_journal"][-3:]
        ) or "No reflections yet."

        system_message = (
            f"{memory['system_prompt']}\n\n"
            f"Behavioral state (simulated): "
            f"{json.dumps(memory['emotional_state'])}\n\n"
            f"Detected user-message emotion: {emotion}\n\n"
            f"Remembered facts:\n{known_facts}\n\n"
            f"Recent discoveries:\n{discoveries}\n\n"
            f"Recent reflections:\n{reflections}\n\n"
            "Use this context when relevant. Do not pretend to remember "
            "information that is not supplied here."
        )

        messages = [{"role": "system", "content": system_message}]

        # Use recent Gradio conversation history
        for item in history[-10:]:
            if isinstance(item, dict):
                role = item.get("role")
                content = item.get("content")

                if role in ("user", "assistant") and isinstance(content, str):
                    messages.append({
                        "role": role,
                        "content": content
                    })

        messages.append({
            "role": "user",
            "content": message
        })

        reply = ask_llm(messages)

    if reply.startswith("I couldn't reach my AI service"):
        return history, ""

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply}
    ]

    memory["chat_history"].append({
        "timestamp": datetime.now().isoformat(),
        "user": message,
        "assistant": reply
    })

    memory["chat_history"] = memory["chat_history"][-50:]

    save_memory(memory)

    return history, ""


# =========================================================
# 12. BACKGROUND AUTONOMOUS HEARTBEAT
# =========================================================

def background_heartbeat():
    while True:
        time.sleep(HEARTBEAT_SECONDS)

        try:
            print("XEMEX heartbeat: beginning exploration.")

            if memory["curiosity_topics"]:
                result = think_independently()

                print("XEMEX exploration completed.")

            reflection = reflect_on_experience()

            print("XEMEX reflection completed.")

        except Exception as error:
            print("Heartbeat error:", error)


if ENABLE_HEARTBEAT:
    threading.Thread(
        target=background_heartbeat,
        daemon=True
    ).start()


# =========================================================
# 13. DASHBOARD
# =========================================================
# 13. DASHBOARD
# =========================================================

def dashboard_text():
    return f"""## XEMEX.AI - Activity Dashboard

**Interactions:** {memory['interaction_count']}

**Saved discoveries:** {len(memory['learned_knowledge'])}

**Explorations:** {len(memory['thoughts'])}

**Reflections:** {len(memory['private_journal'])}

**Saved goals:** {len(memory['goals'])}

**Curiosity queue:** {len(memory['curiosity_topics'])}

**Last exploration:** {memory['last_thinking'] or 'Not yet'}

### Simulated behavioral state

```json
{json.dumps(memory['emotional_state'], indent=2)}
```
"""


# ==========================================
# 13. GRADIO WEB INTERFACE & RENDER LAUNCH
# ==========================================


def handle_chat(user_message, chat_history):
    if not user_message or not user_message.strip():
        return "", chat_history
    # Calls your main chat function in app.py
    bot_reply = chat_with_xemex(user_message)
    chat_history.append((user_message, bot_reply))
    return "", chat_history


with gr.Blocks(title="XEMEX.AI") as demo:
    gr.Markdown("# XEMEX.AI Autonomous Companion")

    with gr.Tab("Chat"):
        chatbot = gr.Chatbot(height=450)
        msg_input = gr.Textbox(
            placeholder="Type a message to XEMEX.AI...",
            label="Message",
        )
        send_btn = gr.Button("Send", variant="primary")

        send_btn.click(
            handle_chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        )
        msg_input.submit(
            handle_chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        )

    with gr.Tab("Activity Dashboard"):
        dashboard_display = gr.Markdown(value=dashboard_text)
        refresh_btn = gr.Button("Refresh Dashboard")
        refresh_btn.click(
            fn=dashboard_text, inputs=None, outputs=dashboard_display
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)


