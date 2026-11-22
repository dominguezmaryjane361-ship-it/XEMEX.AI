import unittest

from registration_validation import validate_learner_name


class RegistrationValidationTests(unittest.TestCase):
    def test_child_name_is_required(self):
        self.assertEqual(
            validate_learner_name("child", ""),
            "Enter the child's name or nickname.",
        )
        self.assertEqual(
            validate_learner_name("child", "   "),
            "Enter the child's name or nickname.",
        )

    def test_child_nickname_is_accepted(self):
        self.assertEqual(validate_learner_name("child", "Sam"), "")

    def test_self_registration_does_not_require_child_name(self):
        self.assertEqual(validate_learner_name("self", ""), "")


if __name__ == "__main__":
    unittest.main()
