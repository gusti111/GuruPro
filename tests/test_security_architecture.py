from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityArchitectureTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_desktop_backend_does_not_initialize_firebase_admin(self):
        source = self.read("backend/database.py") + self.read("backend/firebase_api.py")
        forbidden = (
            "firebase_admin",
            "credentials.Certificate",
            "firestore.client(",
            "serviceAccount",
            "toko_kunci.json",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_desktop_controllers_do_not_access_firestore_directly(self):
        controller_dir = ROOT / "controllers"
        for path in controller_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            forbidden = (
                "database.db.collection",
                "database.firestore.SERVER_TIMESTAMP",
                "firebase_admin",
                "FieldFilter",
            )
            for marker in forbidden:
                with self.subTest(file=path.name, marker=marker):
                    self.assertNotIn(marker, source)

    def test_remote_clients_do_not_use_firestore_sdk_or_browser_storage(self):
        for relative_path in (
            "gurupro_remote/index.html",
            "gurupro_remote/remote-app.js",
            "remote_web/index.html",
            "remote_web/remote-app.js",
        ):
            source = self.read(relative_path)
            forbidden = (
                "firebase-app-compat",
                "firebase-firestore-compat",
                "firebase.firestore(",
                "localStorage",
                "sessionStorage",
            )
            for marker in forbidden:
                with self.subTest(file=relative_path, marker=marker):
                    self.assertNotIn(marker, source)
            self.assertIn('fetch(API_URL', source) if relative_path.endswith("remote-app.js") else None

    def test_server_requires_one_time_approved_nip_and_per_device_auth(self):
        functions = self.read("gurupro_remote/functions/index.js")
        self.assertIn('db.collection("approved_nips").doc(nip)', functions)
        self.assertIn("tx.delete(approvalRef)", functions)
        self.assertIn("auth.setCustomUserClaims(deviceUid, claims)", functions)
        self.assertIn("cleanupExpiredRemoteSessions", functions)
        self.assertIn("auth.deleteUser(deviceUid)", functions)

    def test_desktop_logout_revokes_server_refresh_tokens(self):
        functions = self.read("gurupro_remote/functions/index.js")
        api_client = self.read("backend/firebase_api.py")
        self.assertIn('case "auth.logout"', functions)
        self.assertIn("auth.revokeRefreshTokens(claims.uid)", functions)
        self.assertIn('api_call("auth.logout")', api_client)

    def test_remote_sessions_are_revoked_after_password_change(self):
        functions = self.read("gurupro_remote/functions/index.js")
        password_case = functions.split('case "profile.password":', 1)[1].split('case "class.create":', 1)[0]
        self.assertIn('where("uid", "==", claims.uid)', password_case)
        self.assertIn("revokeAndDeleteAuthUser(deviceUid)", password_case)

    def test_attendance_composite_index_is_configured(self):
        config = self.read("gurupro_remote/firebase.json")
        indexes = self.read("gurupro_remote/firestore.indexes.json")
        self.assertIn('"indexes": "firestore.indexes.json"', config)
        self.assertIn('"collectionGroup": "absensi"', indexes)
        self.assertIn('"fieldPath": "id_kelas"', indexes)
        self.assertIn('"fieldPath": "pertemuan"', indexes)

    def test_remote_controller_parses_api_timestamp_strings(self):
        source = self.read("controllers/perangkat_controller.py")
        self.assertIn("datetime.fromisoformat(value.strip().replace(\"Z\", \"+00:00\"))", source)
        self.assertIn("self.parse_timestamp(last_update_ts)", source)

    def test_profile_does_not_allow_nip_to_appear_editable(self):
        source = self.read("controllers/pengaturan_controller.py")
        self.assertIn("inputEditNIP.setReadOnly(True)", source)
        self.assertIn("NIP Tidak Dapat Diubah", source)

    def test_attendance_validation_rejects_invalid_status_and_scores(self):
        source = self.read("gurupro_remote/functions/index.js")
        self.assertIn("invalid_attendance_status", source)
        self.assertIn("invalid_attendance_score", source)

    def test_student_import_rejects_duplicates_and_empty_rosters(self):
        source = self.read("gurupro_remote/functions/index.js")
        self.assertIn("duplicate_student_nis", source)
        self.assertIn("1–2.000 baris", source)

    def test_firestore_rules_fail_closed_for_client_sdk(self):
        rules = self.read("gurupro_remote/firestore.rules")
        self.assertIn("allow read, write: if false;", rules)


if __name__ == "__main__":
    unittest.main()
