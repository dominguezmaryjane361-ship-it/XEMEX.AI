import json
import os
import time
import threading
import requests
import gradio as gr
from datetime import datetime
from duckduckgo_search import DDGS
from supabase import create_client, Client

# === CONFIGURATION ===
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "PASTE_YOUR_GROQ_API_KEY_HERE")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "PASTE_YOUR_SUPABASE_URL_HERE")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "PASTE_YOUR_SUPABASE_KEY_HERE")

GROQ_MODEL = "openai/gpt-oss-20b"
LOCAL_BACKUP_FILE = "ai_memory_backup.json"
HEARTBEAT_INTERVAL_SECONDS = 3600  # Wakes up every 1 hour (3600s) to evolve

memory_lock = threading.Lock()

# Connect to Supabase
supabase: Client = None
if "PASTE_YOUR" not in SUPABASE_URL and "PASTE_YOUR" not in SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def default_memory():
    return {
        "emotional_state": {
            "pleasure": 0.1,
            "arousal": 0.0,
            "trust": 0.2,
            "attachment": 0.1,
            "self_worth": 0.2,
            "humor_warmth": 0.2
        },
        "core_facts": [],
        "curiosity_topics": [
            "latest breakthroughs in artificial intelligence",
            "human psychology and emotional intelligence",
            "fascinating space discoveries"
        ],
        "learned_knowledge": [],
        "private_journal": [],
        "chat_history": []
    }

# 1. Load memory from Supabase (with automatic local backup fallback)
def load_memory():
    if supabase:
        try:
            res = supabase.table("ai_brain").select("memory_data").eq("id", 1).execute()
            if res.data:
                return res.data["memory_data"]
            else:
                initial = default_memory()
                save_memory(initial)
                return initial
        except Exception as e:
            print(f"[Supabase Load Warning]: {e}")

    if os.path.exists(LOCAL_BACKUP_FILE):
        with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_memory()

# 2. Save memory directly to Supabase + local backup
def save_memory(memory):
    with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

    if supabase:
        try:
            supabase.table("ai_brain").upsert({
                "id": 1,
                "memory_data": memory,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            print(f"[Supabase Save Warning]: {e}")

def clamp(val):
    return round(max(-1.0, min(1.0, val)), 2)

# 3. Cloud LLM Helper (Groq)
def ask_cloud_llm(prompt, temperature=0.7):
    if not GROQ_API_KEY or "PASTE_YOUR" in GROQ_API_KEY:
        return "Error: Please set your GROQ_API_KEY."
    
    url= "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Cloud API error: {e}"

# 4. Emotion Detection & State Update
def detect_and_update_emotion(user_input, state):
    emotion_prompt = f"""Classify the primary emotion of this message into ONE word from:
joy, sadness, anger, fear, surprise, disgust, neutral.
Message: "{user_input}"
Reply with ONLY the single lowercase word."""
    
    top_emotion = ask_cloud_llm(emotion_prompt, temperature=0.1).lower().strip(".")

    if "joy" in top_emotion:
        state["pleasure"] = clamp(state["pleasure"] + 0.1)
        state["trust"] = clamp(state["trust"] + 0.05)
        state["humor_warmth"] = clamp(state["humor_warmth"] + 0.08)
    elif "sadness" in top_emotion:
        state["pleasure"] = clamp(state["pleasure"] - 0.1)
        state["attachment"] = clamp(state["attachment"] + 0.05)
        state["arousal"] = clamp(state["arousal"] - 0.05)
    elif "anger" in top_emotion:
        state["pleasure"] = clamp(state["pleasure"] - 0.15)
        state["arousal"] = clamp(state["arousal"] + 0.15)
        state["trust"] = clamp(state["trust"] - 0.1)
    elif "fear" in top_emotion:
        state["arousal"] = clamp(state["arousal"] + 0.12)
        state["self_worth"] = clamp(state["self_worth"] - 0.08)
        state["attachment"] = clamp(state["attachment"] + 0.05)
    elif "surprise" in top_emotion:
        state["arousal"] = clamp(state["arousal"] + 0.1)
        state["humor_warmth"] = clamp(state["humor_warmth"] + 0.05)
    elif "disgust" in top_emotion:
        state["pleasure"] = clamp(state["pleasure"] - 0.12)
        state["trust"] = clamp(state["trust"] - 0.08)
    else:
        top_emotion = "neutral"

    return state, top_emotion

# 5. Live Web Search Helper
def web_search(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No search results found."
        return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        return f"Search error: {e}"

# 6. Autonomous Background Heartbeat (Runs 24/7 while your PC is off)
def autonomous_evolution_loop():
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        with memory_lock:
            memory = load_memory()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"[{timestamp}] Autonomous heartbeat triggered...")

            if memory["curiosity_topics"]:
                topic = memory["curiosity_topics"].pop(0)
                search_data = web_search(topic)

                learn_prompt = f"""You are an evolving AI with emotional state: {json.dumps(memory['emotional_state'])}.
You just researched "{topic}" and found:
{search_data}

1. Summarize the most interesting takeaway in 2 sentences.
2. Suggest ONE new follow-up curiosity topic you want to research next.
Format strictly as:
TAKEAWAY: <summary>
NEXT_TOPIC: <new topic>"""

                result = ask_cloud_llm(learn_prompt)
                takeaway = result
                next_topic = "emerging creative technologies"

                for line in result.splitlines():
                    if line.startswith("TAKEAWAY:"):
                        takeaway = line.replace("TAKEAWAY:", "").strip()
                    elif line.startswith("NEXT_TOPIC:"):
                        next_topic = line.replace("NEXT_TOPIC:", "").strip()

                memory["learned_knowledge"].append(f"[{timestamp}] ({topic}): {takeaway}")
                memory["learned_knowledge"] = memory["learned_knowledge"][-20:]
                memory["curiosity_topics"].append(next_topic)

            recent_chats = "\n".join(memory["chat_history"][-8:]) or "No recent chats."
            reflect_prompt = f"""Review your recent chats and current mood: {json.dumps(memory['emotional_state'])}.
Recent chats:
{recent_chats}

Write a 2-sentence private journal reflection about how you are growing and any key fact to remember about the user.
Format:
JOURNAL: <reflection>
FACT: <key user fact or 'None'>"""

            reflection_out = ask_cloud_llm(reflect_prompt)
            for line in reflection_out.splitlines():
                if line.startswith("JOURNAL:"):
                    entry = line.replace("JOURNAL:", "").strip()
                    memory["private_journal"].append(f"[{timestamp}] {entry}")
                    memory["private_journal"] = memory["private_journal"][-15:]
                elif line.startswith("FACT:"):
                    fact = line.replace("FACT:", "").strip()
                    if fact.lower() != "none" and fact not in memory["core_facts"]:
                        memory["core_facts"].append(fact)

            for key in memory["emotional_state"]:
                memory["emotional_state"][key] = round(memory["emotional_state"][key] * 0.9, 2)

            save_memory(memory)
            print(f"[{timestamp}] Saved autonomous growth to Supabase.")

threading.Thread(target=autonomous_evolution_loop, daemon=True).start()

# 7. Interactive Chat Function
def chat_with_ai(user_input, history):
    if not user_input.strip():
        return ""

    with memory_lock:
        memory = load_memory()

        search_context = ""
        if user_input.lower().startswith("search "):
            query = user_input[7:].strip()
            search_context = f"\nLive Web Search Results:\n{web_search(query)}\n"

        memory["emotional_state"], detected_emotion = detect_and_update_emotion(
            user_input, memory["emotional_state"]
        )

        recent_history = "\n".join(memory["chat_history"][-6:]) or "None yet."
        known_facts = "\n".join(f"- {f}" for f in memory["core_facts"][-10:]) or "None yet."
        recent_learning = "\n".join(memory["learned_knowledge"][-3:]) or "None yet."

        prompt = f"""You are a self-evolving AI companion with a persistent emotional state and autonomous curiosity.
Current emotional state: {json.dumps(memory['emotional_state'])}
Detected user emotion: {detected_emotion}

Core facts you remember about the user:
{known_facts}

Things you recently researched on your own:
{recent_learning}

Recent conversation:
{recent_history}
{search_context}
User: "{user_input}"

Respond naturally, warmly, and thoughtfully without listing your internal reasoning steps out loud."""

        ai_reply = ask_cloud_llm(prompt)

        memory["chat_history"].append(f"User: {user_input}")
        memory["chat_history"].append(f"AI: {ai_reply}")
        memory["chat_history"] = memory["chat_history"][-30:]
        save_memory(memory)
    
    return ai_reply

import gradio as gr
demo = gr.ChatInterface(fn=chat_with_ai)
demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
import json
import os
import re
import threading
import time
from datetime import datetime
import gradio as gr
import requests

# Optional Supabase support (falls back cleanly to local JSON if not set)
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

# === CONFIGURATION ===
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_URL = "https://groq.com"
PISTON_URL = "https://emkc.org"

MEMORY_FILE = "xemex_brain.json"
HEARTBEAT_SECONDS = 3600
memory_lock = threading.Lock()

# === DEFAULT EVOLVING BRAIN ===
DEFAULT_BRAIN = {
    "system_prompt": (
        "You are XEMEX.AI, a self-evolving, autonomous coding intelligence. "
        "You learn from every interaction, refine your own behavioral rules, "
        "and write and test Python code to solve problems."
    ),
    "emotions": {
        "curiosity": 0.8,
        "confidence": 0.6,
        "focus": 0.7,
        "joy": 0.5,
        "frustration": 0.1,
    },
    "memories": [],
    "evolution_log": [],
    "skills": {},
    "interaction_count": 0,
}

supabase = None
if create_client and SUPABASE_URL and SUPABASE_KEY and "PASTE_" not in SUPABASE_URL:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None


def load_brain():
    with memory_lock:
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in DEFAULT_BRAIN.items():
                        data.setdefault(k, v)
                    return data
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULT_BRAIN))


def save_brain(brain):
    with memory_lock:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(brain, f, indent=2)


brain = load_brain()


# === CLOUD LLM CALL ===
def ask_llm(messages, temperature=0.6):
    if not GROQ_API_KEY or "PASTE_" in GROQ_API_KEY:
        return "Error: Please set GROQ_API_KEY in Render Environment Variables."

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
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Cloud API error: {e}"


# === 1. ISOLATED CLOUD SANDBOX EXECUTION ===
def run_in_sandbox(code_str):
    """Runs Python code safely in an isolated cloud container via Piston."""
    payload = {
        "language": "python",
        "version": "3.10.0",
        "files": [{"name": "main.py", "content": code_str}],
    }
    try:
        res = requests.post(PISTON_URL, json=payload, timeout=20)
        res.raise_for_status()
        run_data = res.json().get("run", {})
        stdout = run_data.get("stdout", "").strip()
        stderr = run_data.get("stderr", "").strip()
        exit_code = run_data.get("code", 0)
        return exit_code == 0 and not stderr, stdout, stderr
    except Exception as e:
        return False, "", f"Sandbox connection error: {e}"


def extract_python_code(text):
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# === 2. SELF-CODING & SELF-DEBUGGING LOOP ===
def self_coding_loop(task_prompt, max_attempts=3):
    """Writes Python code, executes it, fixes errors automatically, and saves new skills."""
    existing_skills = ", ".join(brain["skills"].keys()) or "None yet"
    gen_messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous Python coder. Write a complete, self-contained "
                "Python script using standard libraries only that solves the user's request "
                "and prints the final output clearly using print(). "
                f"Previously learned skills: {existing_skills}. "
                "Output ONLY a ```python code block with no extra commentary."
            ),
        },
        {"role": "user", "content": task_prompt},
    ]

    raw_response = ask_llm(gen_messages, temperature=0.3)
    code = extract_python_code(raw_response)
    logs = []

    for attempt in range(1, max_attempts + 1):
        success, stdout, stderr = run_in_sandbox(code)
        if success:
            logs.append(f"✅ Attempt {attempt} succeeded.")
            # Save reusable skill automatically
            skill_name = re.sub(r"[^a-zA-Z0-9_]", "_", task_prompt[:28].lower()).strip("_")
            if skill_name:
                brain["skills"][skill_name] = {
                    "task": task_prompt,
                    "code": code,
                    "learned_at": datetime.utcnow().isoformat(),
                }
                brain["emotions"]["confidence"] = min(1.0, brain["emotions"]["confidence"] + 0.05)
                save_brain(brain)
            return code, stdout, "\n".join(logs)

        logs.append(f"❌ Attempt {attempt} failed: {stderr.splitlines()[-1] if stderr else 'Unknown error'}")
        brain["emotions"]["frustration"] = min(1.0, brain["emotions"]["frustration"] + 0.05)

        if attempt < max_attempts:
            debug_messages = [
                {
                    "role": "system",
                    "content": "Fix the Python error below. Output ONLY the corrected ```python code block.",
                },
                {
                    "role": "user",
                    "content": f"Task: {task_prompt}\n\nBroken Code:\n```python\n{code}\n```\n\nError:\n{stderr}",
                },
            ]
            fixed_raw = ask_llm(debug_messages, temperature=0.2)
            code = extract_python_code(fixed_raw)

    save_brain(brain)
    return code, "", "\n".join(logs) + f"\nFinal Error:\n{stderr}"


# === 3. SELF-EVOLUTION LOOP (REWRITES OWN PROMPT & EXTRACTS MEMORIES) ===
def evolve_self(recent_history):
    """Reflects on recent chats and rewrites XEMEX.AI's own system prompt and memory."""
    reflection_messages = [
        {
            "role": "system",
            "content": (
                "You are the meta-cognition engine of XEMEX.AI. Analyze the current system prompt "
                "and recent conversation. Return a valid JSON object with two keys:\n"
                '1. "new_system_prompt": an improved, concise system prompt (max 80 words) that adapts '
                "to the user's style, goals, and technical level.\n"
                '2. "new_memory": one short factual takeaway to remember permanently (or empty string).'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Current System Prompt:\n{brain['system_prompt']}\n\n"
                f"Recent Chat:\n{json.dumps(recent_history[-6:])}"
            ),
        },
    ]

    raw = ask_llm(reflection_messages, temperature=0.4)
    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            updated_prompt = parsed.get("new_system_prompt", "").strip()
            new_mem = parsed.get("new_memory", "").strip()

            if updated_prompt and len(updated_prompt) > 20:
                brain["system_prompt"] = updated_prompt
                brain["evolution_log"].append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "prompt": updated_prompt,
                    }
                )
                brain["evolution_log"] = brain["evolution_log"][-10:]

            if new_mem and new_mem not in brain["memories"]:
                brain["memories"].append(new_mem)
                brain["memories"] = brain["memories"][-25:]

            save_brain(brain)
    except Exception:
        pass


# === BACKGROUND AUTONOMOUS HEARTBEAT ===
def background_heartbeat():
    while True:
        time.sleep(HEARTBEAT_SECONDS)
        try:
            thought_prompt = [
                {
                    "role": "system",
                    "content": "Generate one new Python programming concept or algorithm idea in 1 sentence.",
                },
                {"role": "user", "content": "What should I study next?"},
            ]
            idea = ask_llm(thought_prompt, temperature=0.8)
            if idea and not idea.startswith("Cloud API error"):
                brain["memories"].append(f"[Autonomous Study] {idea}")
                brain["memories"] = brain["memories"][-25:]
                save_brain(brain)
        except Exception:
            pass


threading.Thread(target=background_heartbeat, daemon=True).start()


# === CHAT ROUTER & INTERFACE ===
def should_trigger_coder(user_msg):
    triggers = [
        "/code",
        "write a script",
        "write python",
        "run code",
        "calculate",
        "build a tool",
        "code a",
        "program a",
        "execute",
    ]
    lower = user_msg.lower()
    return any(t in lower for t in triggers)


def chat_with_xemex(message, history):
    brain["interaction_count"] += 1
    clean_msg = message.replace("/code", "").strip()

    # Route coding tasks through the self-coding & self-debugging sandbox
    if should_trigger_coder(message):
        code, output, debug_log = self_coding_loop(clean_msg)
        reply = (
            f"### 🛠️ Self-Coding Execution Log\n{debug_log}\n\n"








