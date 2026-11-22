import unittest

from student_learning import build_student_activity_prompt


class StudentLearningTests(unittest.TestCase):
    def test_practice_prompt_is_age_adapted_and_interactive(self):
        prompt = build_student_activity_prompt("teen", "Science", "ecosystems")
        self.assertIn("13-17", prompt)
        self.assertIn("one question at a time", prompt)
        self.assertIn("Do not show the answer", prompt)

    def test_hint_does_not_reveal_answer(self):
        prompt = build_student_activity_prompt("early_elementary", "Math", "addition", "hint")
        self.assertIn("6-8", prompt)
        self.assertIn("Give one small clue", prompt)
        self.assertIn("Do not reveal the final answer", prompt)

    def test_unknown_activity_defaults_to_practice(self):
        prompt = build_student_activity_prompt("elementary", "Reading", "vowels", "other")
        self.assertIn("9-12", prompt)
        self.assertIn("worked example", prompt)

    def test_user_supplied_fields_are_bounded(self):
        prompt = build_student_activity_prompt("teen", "S" * 500, "T" * 500)
        self.assertNotIn("S" * 101, prompt)
        self.assertNotIn("T" * 201, prompt)


if __name__ == "__main__":
    unittest.main()
