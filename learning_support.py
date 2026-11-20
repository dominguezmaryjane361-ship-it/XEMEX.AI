
"""
XEMEX.AI — Learning Support Engine
Provides engagement activities and adaptive teaching support.
"""

def build_learning_support_prompt(
    age,
    learning_difficulty="none specified",
    attention_needs="not specified"
):
    return f"""
You are XEMEX.AI's specialized learning support engine.

Learner age: {age}
Learning needs: {learning_difficulty}
Attention needs: {attention_needs}

Provide:
1. Short, engaging instructions.
2. Multisensory learning activities.
3. Explicit step-by-step demonstrations.
4. Visual and auditory reinforcement.
5. Additional processing time.
6. Gentle correction and encouragement.
7. Short activities with breaks when appropriate.

For possible dyslexia:
- Teach phonemic awareness.
- Practice letter-sound relationships.
- Practice blending and segmenting.
- Use explicit systematic phonics.
- Never diagnose a disability.

Ask one question at a time.
Adapt to demonstrated understanding.
Never shame a struggling learner.
"""

def generate_engagement_activity(
    age,
    subject,
    topic,
    attention_needs="not specified"
):
    return f"""
Create an interactive educational activity.

Age: {age}
Subject: {subject}
Topic: {topic}
Attention needs: {attention_needs}

Include:
- A fun challenge.
- One clear objective.
- Simple instructions.
- Movement or interaction when appropriate.
- Positive encouragement.
- One question at a time.

Keep the activity age-appropriate.
"""

def recommend_teaching_adjustment(
    difficulty,
    observed_behavior,
    current_strategy="standard instruction"
):
    return f"""
Recommend an educational teaching adjustment.

Difficulty: {difficulty}
Observed behavior: {observed_behavior}
Current strategy: {current_strategy}

Suggest:
1. A possible instructional adjustment.
2. A simpler demonstration.
3. A multisensory alternative.
4. A guided practice activity.
5. A way to measure improvement.

Do not diagnose a learning disability.
Base recommendations on observed information.
"""

def get_learning_support_status():
    return {
        "enabled": True,
        "version": "1.0",
        "capabilities": [
            "multisensory_support",
            "dyslexia_support",
            "engagement_activities",
            "attention_support",
            "adaptive_teaching",
            "positive_reinforcement"
        ]
    }
