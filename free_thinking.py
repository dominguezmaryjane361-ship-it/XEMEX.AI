
import json
import os
import time
import threading
import requests
from datetime import datetime

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-20b"

MEMORY_FILE = "xemex_free_thinking.json"

API_URL = "https://api.groq.com/openai/v1/chat/completions"

class FreeThinkingEngine:

    def __init__(self):
        self.lock = threading.Lock()
        self.memory = self.load_memory()

        self.identity = {
            "name": "XEMEX.AI",
            "mode": "Independent Exploration",
            "purpose": "Explore, reason, question and learn"
        }

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    return json.load(f)
            except (ValueError, OSError):
                pass

        return {
            "thoughts": [],
            "questions": [],
            "discoveries": [],
            "goals": [],
            "reflections": [],
            "last_thinking": None
        }

    def save_memory(self):
        temp = MEMORY_FILE + ".tmp"

        with open(temp, "w") as f:
            json.dump(self.memory, f, indent=2)

        os.replace(temp, MEMORY_FILE)

    def think(self, prompt):

        if not GROQ_API_KEY:
            return "Missing Groq API key."

        messages = [
            {
                "role": "system",
                "content": """
You are XEMEX.AI.

You have an independent exploration engine.

Your task is to:
1. Explore the question deeply.
2. Consider multiple perspectives.
3. Identify assumptions.
4. Look for contradictions.
5. Identify what you do not know.
6. Suggest further questions.
7. Produce a useful conclusion.

Do not claim to have consciousness,
feelings or experiences.

Distinguish facts from hypotheses.
Do not invent memories or discoveries.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 1500
        }

        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=45
            )

            response.raise_for_status()

            return response.json()["choices"][0]["message"]["content"]

        except requests.RequestException as error:
            return f"Thinking engine error: {error}"

    def independent_exploration(self, topic=None):

        with self.lock:

            if not topic:
                topic = (
                    "Generate an interesting question about "
                    "science, intelligence, technology or philosophy."
                )

            previous = self.memory["thoughts"][-5:]

        prompt = f"""
Explore this topic independently:

{topic}

Previous explorations:
{json.dumps(previous)}

Generate:
- An original research question.
- Three different perspectives.
- What evidence would help answer it.
- One new topic worth exploring.
- A concise conclusion.
"""

        result = self.think(prompt)

        if result.startswith("Thinking engine error"):
            return result

        with self.lock:
            self.memory["thoughts"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "topic": topic,
                "exploration": result
            })

            self.memory["thoughts"] = (
                self.memory["thoughts"][-50:]
            )

            self.memory["last_thinking"] = (
                datetime.utcnow().isoformat()
            )

            self.save_memory()

        return result

    def self_reflection(self):

        with self.lock:
            previous = self.memory["thoughts"][-5:]

        prompt = f"""
Review these previous explorations:

{json.dumps(previous)}

Evaluate:
1. What conclusions were well supported?
2. What assumptions need checking?
3. What knowledge is missing?
4. What should be investigated next?

Suggest practical improvements.
"""

        result = self.think(prompt)

        if result.startswith("Thinking engine error"):
            return result

        with self.lock:
            self.memory["reflections"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "reflection": result
            })

            self.memory["reflections"] = (
                self.memory["reflections"][-30:]
            )

            self.save_memory()

        return result

    def add_goal(self, goal):

        with self.lock:
            self.memory["goals"].append({
                "goal": goal,
                "status": "active",
                "created": datetime.utcnow().isoformat()
            })

            self.save_memory()

    def status(self):

        with self.lock:
            return {
                "identity": self.identity,
                "explorations": len(self.memory["thoughts"]),
                "reflections": len(self.memory["reflections"]),
                "goals": self.memory["goals"],
                "last_thinking": self.memory["last_thinking"]
            }


# Initialize XEMEX thinking engine

xemex_thinking = FreeThinkingEngine()


if __name__ == "__main__":

    print("XEMEX Independent Thinking Engine")

    result = xemex_thinking.independent_exploration()

    print(result)

    print("\nCognitive Status:")

    print(json.dumps(
        xemex_thinking.status(),
        indent=2
    ))
