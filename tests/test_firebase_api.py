import unittest
from unittest.mock import patch

from backend import firebase_api
from backend.firebase_api import ApiError


class FirebaseApiClientTests(unittest.TestCase):
    def tearDown(self):
        firebase_api.clear_session()

    def test_login_stores_access_and_refresh_tokens(self):
        response = {
            "idToken": "test-id-token",
            "refreshToken": "test-refresh-token",
            "profile": {"nip": "123456"},
        }
        with patch.object(firebase_api, "_raw_post", return_value=response):
            profile = firebase_api.login("123456", "password")
        self.assertEqual(profile["nip"], "123456")
        self.assertTrue(firebase_api.has_session())
        self.assertEqual(firebase_api._refresh_token, "test-refresh-token")

    def test_api_call_refreshes_once_after_unauthorized(self):
        firebase_api.set_tokens("expired-token", "valid-refresh")
        with patch.object(
            firebase_api,
            "_raw_post",
            side_effect=[
                ApiError("expired", status=401, code="invalid_token"),
                {"idToken": "new-id-token", "refreshToken": "rotated-refresh"},
                {"success": True},
            ],
        ) as post:
            result = firebase_api.api_call("profile.get")
        self.assertTrue(result["success"])
        self.assertEqual(post.call_count, 3)
        self.assertEqual(firebase_api._id_token, "new-id-token")
        self.assertEqual(firebase_api._refresh_token, "rotated-refresh")

    def test_transient_refresh_error_does_not_clear_session(self):
        firebase_api.set_tokens("expired-id-token", "refresh-token")
        with patch.object(firebase_api, "_raw_post", side_effect=[
            ApiError("expired", status=401),
            ApiError("temporarily unavailable", status=503),
        ]):
            with self.assertRaises(ApiError) as context:
                firebase_api.api_call("profile.get")
        self.assertEqual(context.exception.status, 503)
        self.assertTrue(firebase_api.has_session())
        self.assertEqual(firebase_api._refresh_token, "refresh-token")

    def test_logout_calls_server_and_clears_tokens(self):
        firebase_api.set_tokens("active-id-token", "active-refresh-token")
        with patch.object(firebase_api, "api_call", return_value={"success": True}) as call:
            firebase_api.logout()
        call.assert_called_once_with("auth.logout")
        self.assertFalse(firebase_api.has_session())
        self.assertIsNone(firebase_api._refresh_token)

    def test_logout_clears_local_tokens_when_server_is_unavailable(self):
        firebase_api.set_tokens("active-id-token", "active-refresh-token")
        with patch.object(firebase_api, "api_call", side_effect=ApiError("offline", status=503)):
            with self.assertRaises(ApiError):
                firebase_api.logout()
        self.assertFalse(firebase_api.has_session())
        self.assertIsNone(firebase_api._refresh_token)

    def test_api_call_fails_without_login(self):
        with self.assertRaises(ApiError) as context:
            firebase_api.api_call("profile.get")
        self.assertEqual(context.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
