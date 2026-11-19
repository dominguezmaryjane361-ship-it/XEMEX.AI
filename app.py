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

GROQ_MODEL = "llama-3.3-70b-versatile"
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
    
    url= "https:\\groq.com"
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
        return res.json()["choices"]["message"]["content"].strip()
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







