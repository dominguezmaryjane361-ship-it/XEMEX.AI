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
