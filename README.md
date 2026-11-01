# GuruPro

GuruPro is a teacher-oriented desktop and remote web application for managing profiles, classes, students, teaching sessions, attendance, reports, and paired devices.

## Architecture

- **Desktop:** Python + PyQt6.
- **Remote PWA:** HTML, CSS, and JavaScript.
- **Authentication:** Firebase Authentication ID tokens. NIP remains a profile identifier; it is not an authorization token.
- **Trusted backend:** Firebase Cloud Functions Gen 2 + Firebase Admin SDK.
- **Data store:** Cloud Firestore, accessed only by the server-side Functions API.
- **Passwords:** salted PBKDF2-HMAC-SHA256 hashes with legacy plaintext upgrade on successful login.

The desktop and browser clients do not initialize Firebase Admin SDK and do not contain a service-account key. They communicate with the trusted API. API requests validate Firebase ID tokens and enforce UID/NIP ownership of classes, students, attendance, and remote sessions.

## Repository layout

- `backend/firebase_api.py`: HTTPS client used by the desktop app.
- `backend/database.py`: desktop data access facade; calls the API.
- `controllers/`: desktop application controllers.
- `gurupro_remote/`: Firebase Hosting PWA, Firestore rules, emulator config, and Functions backend.
- `tests/`: Python unit tests.

## Local setup

### Desktop client

1. Use Python 3.10+.
2. Install the project's desktop dependencies (PyQt6, pandas, openpyxl, qrcode, and any optional reporting/export packages used by your local build).
3. Set `GURUPRO_API_URL` when testing against a local emulator or a non-default deployment.
4. Run `python main.py`.

The desktop client holds its ID and refresh tokens in memory only. It asks the user to sign in again after the application restarts.

### Firebase backend and PWA

From `gurupro_remote/`:

```bash
npm install
cd functions
npm install
cd ..
firebase emulators:start --only auth,firestore,functions,hosting
```

The Functions runtime requires Node.js 20. The Firestore Rules test command is:

```bash
npm run test:rules
```

The Functions source check is:

```bash
cd functions
npm test
```

## Firebase configuration

The default Firebase project alias is `gurupro-app-bc6cc`. Set the Web API Key as a Functions secret before deployment:

```bash
firebase functions:secrets:set FIREBASE_WEB_API_KEY
```

Retrieve the Web API Key from Firebase Console > Project settings > General. Never place a service-account JSON in a client or commit one to Git.

A deployment should only happen after a Firestore backup, review of every client that uses the project, and end-to-end emulator testing. The Firestore Rules intentionally deny direct client SDK access. Existing clients that still access Firestore directly will stop working after those rules are deployed.

When ready to deploy:

```bash
firebase deploy --only functions:api,hosting,firestore:rules
```

The desktop API endpoint defaults to `https://us-central1-gurupro-app-bc6cc.cloudfunctions.net/api`; set `GURUPRO_API_URL` to override it.

## Security and project status

See [SECURITY.md](SECURITY.md) for the threat review, migration design, required Firebase Console configuration, deployment gates, and remaining production validation.

This repository contains source-level changes and CI checks. It does not assert that the live Firebase project has been deployed, its rules changed, credentials rotated, or real account/data migration completed.

## Author

Gusty Faqikh
