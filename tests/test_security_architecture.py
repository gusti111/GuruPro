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

    def test_firestore_rules_fail_closed_for_client_sdk(self):
        rules = self.read("gurupro_remote/firestore.rules")
        self.assertIn("allow read, write: if false;", rules)


if __name__ == "__main__":
    unittest.main()
