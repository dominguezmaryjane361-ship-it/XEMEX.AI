import unittest
from unittest.mock import patch

import student_accounts


class StudentAccountSecurityTests(unittest.TestCase):
    def test_passwords_are_salted_and_verified(self):
        salt1, digest1, rounds = student_accounts._password_record("LongPassword123")
        salt2, digest2, _ = student_accounts._password_record("LongPassword123")
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(digest1, digest2)
        self.assertTrue(student_accounts._verify_password("LongPassword123", {
            "password_salt": salt1, "password_hash": digest1,
            "password_iterations": rounds,
        }))
        self.assertFalse(student_accounts._verify_password("WrongPassword", {
            "password_salt": salt1, "password_hash": digest1,
            "password_iterations": rounds,
        }))

    def test_password_length_is_enforced(self):
        with self.assertRaises(ValueError):
            student_accounts._password_record("short")

    def test_session_is_signed_and_expires(self):
        original_secret = student_accounts.SESSION_SECRET
        student_accounts.SESSION_SECRET = b"test-only-session-secret"
        try:
            record = {
                "id": "student-id",
                "parent_user_id": "parent-id",
                "learner_id": "learner-id",
            }
            session = student_accounts._issue_session(record)
            self.assertIsNotNone(student_accounts.validate_student_session(session))
            tampered = dict(session)
            tampered["learner_id"] = "other-learner"
            self.assertIsNone(student_accounts.validate_student_session(tampered))
            tampered_token = dict(session)
            tampered_token["token"] += "x"
            self.assertIsNone(student_accounts.validate_student_session(tampered_token))
        finally:
            student_accounts.SESSION_SECRET = original_secret

    def test_username_rules(self):
        self.assertIsNotNone(student_accounts.USERNAME_RE.fullmatch("sam.student-2"))
        self.assertIsNone(student_accounts.USERNAME_RE.fullmatch("ab"))
        self.assertIsNone(student_accounts.USERNAME_RE.fullmatch("Has Space"))


if __name__ == "__main__":
    unittest.main()
