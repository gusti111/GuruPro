import unittest

from backend.password_utils import hash_password, verify_password


class PasswordUtilsTests(unittest.TestCase):
    def test_hash_is_not_plaintext_and_is_salted(self):
        first = hash_password("StrongPass!123")
        second = hash_password("StrongPass!123")
        self.assertNotEqual(first, "StrongPass!123")
        self.assertNotEqual(first, second)

    def test_correct_password_verifies(self):
        encoded = hash_password("StrongPass!123")
        self.assertEqual(verify_password("StrongPass!123", encoded), (True, False))

    def test_wrong_password_fails(self):
        encoded = hash_password("StrongPass!123")
        self.assertEqual(verify_password("wrong", encoded), (False, False))

    def test_legacy_plaintext_is_flagged_for_migration(self):
        self.assertEqual(verify_password("legacy", "legacy"), (True, True))
        self.assertEqual(verify_password("wrong", "legacy"), (False, True))

    def test_malformed_hash_fails_closed(self):
        self.assertEqual(verify_password("anything", "pbkdf2_sha256$broken"), (False, False))

    def test_empty_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("")


if __name__ == "__main__":
    unittest.main()
