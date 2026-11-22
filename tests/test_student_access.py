import unittest

from student_access import make_pin_record, verify_pin


class StudentAccessTests(unittest.TestCase):
    def test_pin_is_hashed_and_verifies(self):
        record = make_pin_record("123456")
        self.assertNotIn("123456", str(record))
        self.assertTrue(verify_pin("123456", record))
        self.assertFalse(verify_pin("654321", record))

    def test_pin_requires_six_digits(self):
        for invalid in ("12345", "1234567", "12ab56", ""):
            with self.subTest(pin=invalid):
                with self.assertRaises(ValueError):
                    make_pin_record(invalid)

    def test_malformed_pin_record_fails_closed(self):
        self.assertFalse(verify_pin("123456", {"salt": "bad", "hash": "bad"}))


if __name__ == "__main__":
    unittest.main()
