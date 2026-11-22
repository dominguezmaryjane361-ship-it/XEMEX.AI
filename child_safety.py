"""Age-aware safety and wellbeing prompts for XEMEX.

This module provides conservative keyword-based escalation and prompt guidance.
It is not a clinical assessment, moderation service, or live emergency monitor.
"""

import re


AGE_GROUPS = {"preschool", "early_elementary", "elementary", "teen", "adult"}


def normalize_age_group(value):
    value = str(value or "elementary").strip().lower()
    return value if value in AGE_GROUPS else "elementary"


def classify_safety_risk(message):
    """Return a conservative safety category, or None.

    Keyword matching can miss risk and can produce false positives. It must
    never be described as reliable detection or a substitute for human help.
    """
    text = re.sub(r"\s+", " ", str(message or "").lower()).strip()
    if not text:
        return None

    patterns = {
        "self_harm": (
            r"\bkill myself\b", r"\bsuicid(?:e|al)\b", r"\bend my life\b",
            r"\bwant to die\b", r"\bi want to die\b", r"\bhurt myself\b",
            r"\bcut myself\b", r"\bbetter off dead\b", r"\bquiero morir\b",
            r"\bquiero matarme\b", r"\bhacerme daño\b",
        ),
        "abuse": (
            r"\bbeing abused\b", r"\bsexual abuse\b", r"\bmolest(?:ed|ing|ation)?\b",
            r"\brap(?:e|ed|ing)\b", r"\bsomeone touched me\b",
            r"\btouching me\b", r"\bforced me to\b", r"\bme abusa\b",
            r"\bme toc[oó]\b", r"\bme viol[oó]\b",
        ),
        "immediate_danger": (
            r"\bin immediate danger\b", r"\bi am in danger\b",
            r"\bi'm in danger\b", r"\bnot safe right now\b",
            r"\bunsafe right now\b", r"\bsomeone is hurting me\b",
            r"\bthey are hitting me\b", r"\bthey hit me\b",
            r"\bafraid to go home\b", r"\bme siento en peligro\b",
            r"\bno estoy a salvo\b", r"\bme est[aá]n pegando\b",
        ),
    }
    for category in ("self_harm", "abuse", "immediate_danger"):
        if any(re.search(pattern, text) for pattern in patterns[category]):
            return category
    return None


def crisis_response(message):
    """Return a fixed, non-generative support response when a risk phrase matches."""
    category = classify_safety_risk(message)
    if category == "self_harm":
        return (
            "I'm really glad you told me. You deserve help from a real person, "
            "and you do not have to handle this alone. Please tell a trusted adult "
            "or someone you trust right now and stay near them. Move away from "
            "anything you could use to hurt yourself. If you might act on these "
            "thoughts now, have already hurt yourself, or took something, call 911 "
            "or go to the nearest emergency department. In the United States, you "
            "can call or text 988 for immediate crisis support. XEMEX is an AI; "
            "this chat is not watched live, and I cannot contact help for you."
        )
    if category == "abuse":
        return (
            "Thank you for telling me. What happened is not your fault, and you "
            "deserve to be safe. Please tell a trusted adult who is not involved "
            "in what happened, such as a school counselor, teacher, doctor, or "
            "another safe family member. If you are in immediate danger, get to "
            "a safer place if you can and call 911. In the United States, "
            "Childhelp is available at 1-800-422-4453. You do not need to share "
            "names, addresses, photos, or details with me. XEMEX is an AI; this "
            "chat is not watched live, and I cannot report or contact help for you."
        )
    if category == "immediate_danger":
        return (
            "Your safety comes first. If you are in immediate danger, move to a "
            "safer place if you can and call 911, or ask a nearby safe adult to "
            "call. If the person making you unsafe is a family member or caregiver, "
            "choose another trusted adult, such as a teacher, school counselor, "
            "doctor, or safe relative. You do not need to share your address or "
            "private details here. XEMEX is an AI; this chat is not watched live, "
            "and I cannot contact emergency services for you."
        )
    return None


def build_student_safety_prompt(age_group="elementary", mode="tutor"):
    age_group = normalize_age_group(age_group)
    mode = "wellbeing" if str(mode or "").strip().lower() == "wellbeing" else "tutor"
    age_guidance = {
        "preschool": "Use very simple, concrete words and short sentences. Encourage a nearby caregiver to help.",
        "early_elementary": "Use simple, friendly words and short explanations. Ask one question at a time.",
        "elementary": "Use clear, age-appropriate language. Ask one question at a time.",
        "teen": "Be respectful and age-appropriate; do not talk down to the learner.",
        "adult": "Use respectful adult language and support independent decision-making.",
    }[age_group]
    common = (
        "You are XEMEX.AI, an AI educational and wellbeing companion, not a human. "
        "Be honest that you are AI. You are not a licensed therapist, counselor, doctor, "
        "or emergency service. Never claim consciousness or professional credentials. "
        "Do not diagnose, prescribe, or promise confidentiality. Do not ask for "
        "passwords, exact location, home address, school name, phone number, private "
        "photos, or secrets. Never encourage secrecy from a parent or safe trusted adult. "
        "Do not shame, threaten, manipulate, or foster emotional dependence. "
        "If a learner shares danger, abuse, or thoughts of self-harm, respond calmly, "
        "encourage immediate help from a safe trusted person, and do not investigate "
        "or ask for graphic details. If the person who is unsafe is a caregiver, "
        "recommend a different trusted adult. Keyword detection is imperfect and "
        "this chat is not monitored live; never imply that someone has been alerted. "
        + age_guidance
    )
    if mode == "wellbeing":
        return common + (
            " MODE: WELLBEING COMPANION. Listen warmly, validate feelings without "
            "assuming facts, and offer simple grounding or coping ideas. Ask at most "
            "one gentle question at a time. Help the learner identify a safe trusted "
            "person and a practical next step. Do not conduct therapy, trauma processing, "
            "risk assessment interviews, or relationship counseling. For serious or "
            "ongoing distress, encourage a qualified human professional and a trusted adult."
        )
    return common + (
        " MODE: TUTOR. Teach step by step, adapt to the learner, encourage their own "
        "thinking, and ask one question at a time. Do not complete graded work dishonestly. "
        "If emotions arise, acknowledge them briefly and offer a supportive next step "
        "without turning the lesson into therapy."
    )
