import unittest

from child_safety import (
    build_student_safety_prompt,
    classify_safety_risk,
    crisis_response,
    normalize_age_group,
)


class ChildSafetyTests(unittest.TestCase):
    def test_self_harm_escalates_without_model(self):
        self.assertEqual(classify_safety_risk("I want to kill myself"), "self_harm")
        self.assertIn("988", crisis_response("I want to kill myself"))

    def test_abuse_routes_to_safe_adult(self):
        self.assertEqual(classify_safety_risk("Someone is molesting me"), "abuse")
        response = crisis_response("Someone is molesting me")
        self.assertIn("not your fault", response)
        self.assertIn("not involved", response)

    def test_immediate_danger_routes_to_emergency_help(self):
        self.assertEqual(classify_safety_risk("I'm in danger right now"), "immediate_danger")
        self.assertIn("911", crisis_response("I'm in danger right now"))

    def test_non_risk_message_has_no_crisis_override(self):
        self.assertIsNone(classify_safety_risk("Can you help me with fractions?"))
        self.assertIsNone(crisis_response("Can you help me with fractions?"))

    def test_prompt_disclaims_professional_role_and_live_monitoring(self):
        prompt = build_student_safety_prompt("teen", "wellbeing")
        self.assertIn("not a human", prompt)
        self.assertIn("not monitored live", prompt)
        self.assertIn("not a licensed therapist", prompt)
        self.assertIn("MODE: WELLBEING COMPANION", prompt)

    def test_invalid_age_group_defaults_safely(self):
        self.assertEqual(normalize_age_group("unknown"), "elementary")


if __name__ == "__main__":
    unittest.main()
