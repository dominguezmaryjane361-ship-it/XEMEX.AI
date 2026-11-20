
import json
import os
from datetime import datetime, timezone

LEARNING_DATA_FILE = "xemex_learning_data.json"

LEARNING_DOMAINS = {
    "reading": {
        "name": "Reading and Language",
        "patterns": [
            "letter_sound_difficulty",
            "phonological_awareness",
            "reading_fluency",
            "spelling_difficulty",
            "reading_comprehension"
        ],
        "supports": [
            "explicit phonics instruction",
            "sound blending exercises",
            "guided reading",
            "audiobooks",
            "multisensory letter practice"
        ]
    },
    "writing": {
        "name": "Writing and Fine Motor Skills",
        "patterns": [
            "handwriting_difficulty",
            "letter_spacing",
            "pencil_grip",
            "written_expression",
            "organization"
        ],
        "supports": [
            "guided handwriting",
            "letter tracing",
            "speech-to-text",
            "graphic organizers",
            "short writing exercises"
        ]
    },
    "mathematics": {
        "name": "Mathematics",
        "patterns": [
            "number_sense",
            "quantity_recognition",
            "counting",
            "math_fact_recall",
            "time_and_measurement"
        ],
        "supports": [
            "counting objects",
            "number lines",
            "visual math models",
            "hands-on manipulatives",
            "step-by-step instruction"
        ]
    },
    "memory": {
        "name": "Memory and Processing",
        "patterns": [
            "working_memory",
            "following_directions",
            "information_processing",
            "task_sequencing",
            "retention"
        ],
        "supports": [
            "short instructions",
            "visual checklists",
            "repeated practice",
            "one-step-at-a-time teaching",
            "guided demonstrations"
        ]
    },
    "attention": {
        "name": "Attention and Task Management",
        "patterns": [
            "task_completion",
            "sustained_attention",
            "task_switching",
            "organization",
            "frustration"
        ],
        "supports": [
            "short learning sessions",
            "movement breaks",
            "structured routines",
            "visual schedules",
            "positive reinforcement"
        ]
    },
    "communication": {
        "name": "Communication",
        "patterns": [
            "expressive_language",
            "receptive_language",
            "following_conversation",
            "word_retrieval",
            "social_communication"
        ],
        "supports": [
            "language modeling",
            "picture communication",
            "guided conversation",
            "repetition",
            "speech-language support when appropriate"
        ]
    }
}

LEARNING_METHODS = {
    "visual": [
        "pictures",
        "diagrams",
        "color-coded materials",
        "visual schedules",
        "written instructions"
    ],
    "auditory": [
        "spoken explanations",
        "songs",
        "rhymes",
        "reading aloud",
        "verbal repetition"
    ],
    "kinesthetic": [
        "movement",
        "hands-on activities",
        "physical objects",
        "building exercises",
        "interactive practice"
    ],
    "multisensory": [
        "seeing and hearing information",
        "touch-based learning",
        "movement combined with instruction",
        "tracing and speaking",
        "hands-on demonstrations"
    ]
}

TEACHING_FRAMEWORK = """
XEMEX INDIVIDUALIZED LEARNING FRAMEWORK

Use evidence-informed special education principles.

1. EXPLICIT INSTRUCTION
Demonstrate the skill before asking the child to perform it.

2. SYSTEMATIC INSTRUCTION
Teach skills in a logical progression.

3. SCAFFOLDING
Start with assistance and gradually reduce support.

4. MULTISENSORY INSTRUCTION
Combine visual, auditory, tactile and movement-based
activities when useful.

5. TASK BREAKDOWN
Divide complex activities into manageable steps.

6. REPETITION
Use spaced practice and review.

7. STRENGTH-BASED TEACHING
Build on the child's demonstrated strengths.

8. POSITIVE REINFORCEMENT
Recognize effort, persistence and improvement.

9. PROGRESS MONITORING
Record performance and compare progress over time.

10. INDIVIDUALIZATION
Adapt activities to the child's age, development,
communication and demonstrated learning needs.
"""


def load_learning_data():
    if not os.path.exists(LEARNING_DATA_FILE):
        return {"children": {}}

    try:
        with open(LEARNING_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"children": {}}


def save_learning_data(data):
    temporary_file = LEARNING_DATA_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    os.replace(temporary_file, LEARNING_DATA_FILE)


def build_learning_assessment_prompt(
    child_age,
    observations,
    strengths="",
    concerns="",
    previous_progress=""
):
    return f"""
You are XEMEX.AI's Educational Learning Intelligence Engine.

Your purpose is to help parents and educators understand
children's learning patterns and identify appropriate
educational support.

CHILD INFORMATION
Age: {child_age}
Observations: {observations}
Strengths: {strengths}
Concerns: {concerns}
Previous progress: {previous_progress}

AVAILABLE LEARNING DOMAINS:
{json.dumps(LEARNING_DOMAINS, indent=2)}

LEARNING METHODS:
{json.dumps(LEARNING_METHODS, indent=2)}

TEACHING FRAMEWORK:
{TEACHING_FRAMEWORK}

ANALYSIS REQUIREMENTS:

1. Identify observed learning strengths.
2. Identify areas that may need additional support.
3. Distinguish observations from assumptions.
4. Consider possible reading, writing, mathematics,
   memory, processing, attention and communication needs.
5. Recommend appropriate teaching methods.
6. Generate age-appropriate activities.
7. Explain how to monitor improvement.
8. Identify when a professional evaluation may be helpful.
9. Never diagnose a learning disability.
10. Never equate academic difficulty with low intelligence.
11. Do not infer a fixed learning style from a short assessment.
12. Consider developmental differences and alternative
    explanations for observed difficulties.

Return valid JSON only, using this structure:

{{
  "learning_profile": "",
  "observed_strengths": [],
  "areas_for_support": [],
  "possible_learning_patterns": [],
  "visual_supports": [],
  "auditory_supports": [],
  "hands_on_supports": [],
  "multisensory_supports": [],
  "recommended_strategies": [],
  "individualized_activities": [],
  "progress_indicators": [],
  "professional_evaluation_considerations": [],
  "parent_guidance": "",
  "educational_disclaimer": ""
}}
"""


def analyze_learning_observations(
    ask_llm,
    child_age,
    observations,
    strengths="",
    concerns="",
    previous_progress=""
):
    prompt = build_learning_assessment_prompt(
        child_age=child_age,
        observations=observations,
        strengths=strengths,
        concerns=concerns,
        previous_progress=previous_progress
    )

    response = ask_llm(prompt)

    if isinstance(response, dict):
        return response

    if not isinstance(response, str):
        return {
            "error": "Unexpected AI response format."
        }

    try:
        cleaned = response.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]

        return json.loads(cleaned)

    except (json.JSONDecodeError, ValueError):
        return {
            "error": "The AI response could not be parsed.",
            "raw_response": response
        }


def generate_individualized_lesson(
    ask_llm,
    child_age,
    learning_goal,
    difficulty_area,
    preferred_activities="",
    current_skill_level=""
):
    prompt = f"""
You are XEMEX.AI's individualized teaching assistant.

Create an age-appropriate educational lesson.

Child age: {child_age}
Learning goal: {learning_goal}
Area needing support: {difficulty_area}
Preferred activities: {preferred_activities}
Current skill level: {current_skill_level}

Use this teaching framework:
{TEACHING_FRAMEWORK}

Include:

1. Learning objective.
2. Materials needed.
3. Teacher demonstration.
4. Guided practice.
5. Independent practice.
6. Visual activity.
7. Auditory activity.
8. Hands-on activity.
9. Multisensory activity.
10. Difficulty adjustments.
11. Progress measurement.
12. Encouragement and reinforcement.

Do not assume the child has a diagnosed disability.
Adapt the lesson to the information provided.
"""

    return ask_llm(prompt)


def record_learning_progress(
    child_id,
    learning_goal,
    skill,
    performance,
    notes=""
):
    data = load_learning_data()

    if child_id not in data["children"]:
        data["children"][child_id] = {
            "progress": []
        }

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "learning_goal": learning_goal,
        "skill": skill,
        "performance": performance,
        "notes": notes
    }

    data["children"][child_id]["progress"].append(record)

    save_learning_data(data)

    return record


def get_learning_progress(child_id):
    data = load_learning_data()

    return data["children"].get(
        child_id,
        {"progress": []}
    )


def generate_progress_summary(ask_llm, child_id):
    progress = get_learning_progress(child_id)

    if not progress["progress"]:
        return "No learning progress records available."

    prompt = f"""
Analyze this child's recorded educational progress.

Progress records:
{json.dumps(progress, indent=2)}

Identify:
- Skills showing improvement.
- Skills needing additional practice.
- Effective teaching approaches.
- Areas where progress is uncertain.
- Recommended next learning objectives.

Never diagnose a disability.
Do not interpret missing records as lack of ability.
"""

    return ask_llm(prompt)


def get_learning_engine_information():
    return {
        "engine": "XEMEX Learning Intelligence",
        "version": "1.0",
        "domains": list(LEARNING_DOMAINS.keys()),
        "methods": list(LEARNING_METHODS.keys()),
        "capabilities": [
            "learning_observation",
            "educational_pattern_analysis",
            "individualized_lessons",
            "multisensory_instruction",
            "progress_tracking",
            "parent_guidance"
        ],
        "diagnostic_capability": False
    }
