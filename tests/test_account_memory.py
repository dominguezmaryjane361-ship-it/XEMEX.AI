import unittest
from unittest.mock import patch

import account_memory


class AccountMemoryTests(unittest.TestCase):
    def test_default_memory_has_private_sections(self):
        data = account_memory.default_user_memory()
        self.assertEqual(data["profile"]["name"], "")
        self.assertEqual(data["facts"], [])
        self.assertEqual(data["chat_history"], [])
        self.assertIn("emotional_state", data)

    def test_normalize_memory_limits_history_and_name(self):
        data = account_memory._normalize_memory({
            "profile": {"name": "A" * 150},
            "facts": list(range(120)),
            "chat_history": list(range(120)),
            "interaction_count": 9,
            "emotional_state": {"trust": 4},
        })
        self.assertEqual(len(data["profile"]["name"]), 100)
        self.assertEqual(len(data["facts"]), 100)
        self.assertEqual(len(data["chat_history"]), 100)
        self.assertEqual(data["interaction_count"], 9)
        self.assertEqual(data["emotional_state"]["trust"], 1.0)

    def test_tutoring_data_is_account_scoped_and_bounded(self):
        data = account_memory._normalize_memory({
            "tutor_settings": {
                "age_group": "teen",
                "subject": "Science",
                "learning_goal": "Understand ecosystems",
            },
            "learning_progress": [{"topic": str(i)} for i in range(125)],
        })
        self.assertEqual(data["tutor_settings"]["age_group"], "teen")
        self.assertEqual(data["tutor_settings"]["subject"], "Science")
        self.assertEqual(len(data["learning_progress"]), 100)

    def test_learner_profiles_are_bounded_and_validated(self):
        data = account_memory._normalize_memory({
            "learners": [
                {"id": "learner-1", "name": "Student One", "age_group": "early_elementary"},
                {"id": "learner-1", "name": "Duplicate ID", "age_group": "teen"},
                {"id": "learner-2", "name": " " * 2, "age_group": "teen"},
                {"id": "learner-3", "name": "Student Three", "age_group": "teen"},
            ],
            "learning_progress": [
                {"learner_id": "learner-1", "topic": "Math"},
                {"learner_id": "learner-3", "topic": "Reading"},
            ],
        })
        self.assertEqual(
            data["learners"],
            [
                {"id": "learner-1", "name": "Student One", "age_group": "early_elementary",
                 "student_pin": None, "pin_failed_attempts": 0, "pin_locked_until": 0,
                 "parent_controls": {"allow_chat": True, "allow_practice": True, "allow_hints": True, "daily_activity_limit": 20}},
                {"id": "learner-3", "name": "Student Three", "age_group": "teen",
                 "student_pin": None, "pin_failed_attempts": 0, "pin_locked_until": 0,
                 "parent_controls": {"allow_practice": True, "allow_hints": True, "daily_activity_limit": 20}},
            ],
        )
        self.assertEqual(len(data["learning_progress"]), 2)

    def test_parent_controls_are_validated_and_defaulted(self):
        data = account_memory._normalize_memory({
            "learners": [
                {"id": "learner-1", "name": "Student One", "age_group": "teen",
                 "parent_controls": {"allow_practice": False, "allow_hints": "no",
                                     "daily_activity_limit": 999}}
            ]
        })
        controls = data["learners"][0]["parent_controls"]
        self.assertFalse(controls["allow_practice"])
        self.assertTrue(controls["allow_hints"])
        self.assertEqual(controls["daily_activity_limit"], 20)

    @patch.object(account_memory, "refresh_session")
    @patch.object(account_memory.time, "time", return_value=2000)
    def test_valid_session_is_reused_before_expiry(self, mock_time, mock_refresh):
        session = {
            "user_id": "11111111-1111-4111-8111-111111111111",
            "access_token": "active-token",
            "refresh_token": "refresh-token",
            "expires_at": 2100,
        }
        renewed, status = account_memory.ensure_valid_session(session)
        self.assertIs(renewed, session)
        self.assertEqual(status, "Session active.")
        mock_refresh.assert_not_called()

    @patch.object(account_memory, "refresh_session")
    @patch.object(account_memory.time, "time", return_value=2000)
    def test_expired_session_is_refreshed(self, mock_time, mock_refresh):
        session = {
            "user_id": "11111111-1111-4111-8111-111111111111",
            "access_token": "old-token",
            "refresh_token": "refresh-token",
            "expires_at": 1900,
        }
        refreshed = {
            "user_id": session["user_id"],
            "access_token": "new-token",
            "refresh_token": "rotated-refresh-token",
            "expires_at": 5500,
        }
        mock_refresh.return_value = refreshed
        renewed, status = account_memory.ensure_valid_session(session)
        self.assertEqual(renewed["access_token"], "new-token")
        self.assertEqual(status, "Your session was securely renewed.")
        mock_refresh.assert_called_once_with(session)

    @patch.object(account_memory, "refresh_session", return_value=None)
    @patch.object(account_memory.time, "time", return_value=2000)
    def test_expired_session_requires_sign_in_if_refresh_fails(self, mock_time, mock_refresh):
        session = {
            "user_id": "11111111-1111-4111-8111-111111111111",
            "access_token": "expired-token",
            "refresh_token": "invalid-refresh-token",
            "expires_at": 1900,
        }
        renewed, status = account_memory.ensure_valid_session(session)
        self.assertIsNone(renewed)
        self.assertEqual(status, "Your session expired. Please sign in again.")

    def test_user_file_requires_uuid(self):
        with self.assertRaises(ValueError):
            account_memory._user_file("../../other-user")

    def test_different_users_get_different_files(self):
        first = account_memory._user_file("11111111-1111-4111-8111-111111111111")
        second = account_memory._user_file("22222222-2222-4222-8222-222222222222")
        self.assertNotEqual(first, second)

    @patch.object(account_memory, "_write_local")
    @patch.object(account_memory.requests, "post")
    def test_save_uses_authenticated_user_row(self, mock_post, mock_write):
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = []
        session = {
            "user_id": "11111111-1111-4111-8111-111111111111",
            "access_token": "test-user-jwt",
        }
        with patch.object(account_memory, "SUPABASE_URL", "https://example.supabase.co"), \
             patch.object(account_memory, "SUPABASE_KEY", "sb_publishable_test"):
            ok, message = account_memory.save_user_memory(session, {"facts": ["private fact"]})
        self.assertTrue(ok, message)
        self.assertEqual(mock_post.call_args.kwargs["json"]["user_id"], session["user_id"])
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-user-jwt",
        )


if __name__ == "__main__":
    unittest.main()
