# Security review & remediation status

## Scope

This source review does not inspect live Firebase Console configuration, production Firestore data, deployed Hosting configuration, or credentials.

## Confirmed risks in current architecture

- The desktop application initializes Firestore using Firebase Admin SDK credentials. Admin SDK access bypasses Firestore Security Rules. A service-account credential distributed with a desktop executable can be extracted and abused.
- The browser-based remote control reads/writes Firestore directly and does not currently authenticate with Firebase Authentication. A token stored in a URL or browser storage is a bearer credential and must be treated as sensitive.
- Desktop data operations rely on client-supplied document IDs and NIP values without server-enforced ownership checks. Admin SDK operations are not constrained by Firestore Rules.
- Password hashing in Firestore is an interim improvement only. It is not a substitute for Firebase Authentication and still leaves credential verification in client code.
- Desktop and remote web clients have separate trust boundaries; securing one does not secure the other.

## Changes in branch `security/firebase-auth-hardening`

- Adds `gurupro_remote/firestore.rules` as a fail-closed baseline: all client SDK reads/writes are denied.
- Configures Firestore Rules and Firebase Emulator Suite in `gurupro_remote/firebase.json`.
- Adds emulator-based tests that verify unauthenticated and authenticated client requests are denied.
- Adds Node test tooling under `gurupro_remote/package.json`.
- These files are not deployed to any Firebase project by this repository change.

## Important: not yet a production-ready migration

The current application still uses the legacy client architecture. The fail-closed rules are a protective baseline, not an app-compatible final ruleset. **Do not deploy these rules against the live project before migrating the clients/backend**, because current direct-client reads and writes will stop working.

## Required steps before production use

1. Create a trusted backend (Cloud Functions or Cloud Run) that owns privileged Firestore operations. Never bundle a service-account JSON or Admin SDK credential in desktop/mobile/web clients.
2. Migrate account identities to Firebase Authentication. Keep NIP as a profile attribute; do not use NIP/password pairs as a substitute for Auth UID.
3. Store authenticated UID as the owner field on each user's classes, attendance, profiles, and sessions. Enforce ownership in Firestore Rules or backend authorization.
4. Replace direct browser access to privileged collections with authenticated operations. Remote-control sessions must be short-lived, scoped to one user/device, revocable, validated server-side, and must not use bearer tokens in query strings.
5. Migrate existing accounts/data with a trusted one-time script. Do not silently reset passwords or publish existing data.
6. Revoke and rotate any service-account key ever included in a distributed build or public repository. Review Firebase IAM audit logs and production rules.
7. Run emulator tests for unauthenticated, authenticated-owner, authenticated-non-owner, expired-session, and backend/admin scenarios.
8. Deploy rules/backend only after the migrated clients and backend are verified together.

## Local validation

From `gurupro_remote/`:

```bash
npm install
npm run test:rules
```

The test command runs Firestore Emulator Suite. Java and Firebase CLI dependencies are required. This branch has not been executed in a local runtime; CI is configured to run the tests. No live Firebase deployment or integration test has been performed.
