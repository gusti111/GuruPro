# Security review & remediation status

## Scope

This review covers the repository source code only. It does not inspect the live Firebase Console configuration, production Firestore data, deployed Hosting configuration, or credentials.

## Confirmed risks in current architecture

- The desktop application initializes Firestore using Firebase Admin SDK credentials. Admin SDK access bypasses Firestore Security Rules. A service-account credential distributed with a desktop executable can be extracted and abused.
- The browser-based remote control reads/writes Firestore directly and does not currently authenticate with Firebase Authentication. A token stored in a URL or browser storage is a bearer credential and must be treated as sensitive.
- Data operations in the desktop app rely on client-supplied document IDs and NIP values without server-enforced ownership checks. Admin SDK operations are not constrained by Firestore Rules.
- Password hashing in Firestore is an interim improvement only. It is not a substitute for Firebase Authentication and still leaves credential verification in client code.
- The desktop app and remote web app have separate trust boundaries; securing one does not secure the other.

## Changes in this branch

- Adds a fail-closed Firestore Rules baseline: client SDK access is denied until the app is migrated to Firebase Authentication and ownership rules.
- Adds Firebase Emulator configuration for Auth, Firestore, Hosting, and UI.
- This configuration is not deployed to any Firebase project by this repository change.

## Required migration before production use

1. Create a trusted backend (Cloud Functions or Cloud Run) that owns all privileged Firestore operations. Never bundle a service-account JSON or Admin SDK credential in desktop/mobile/web clients.
2. Migrate account identities to Firebase Authentication. Keep NIP as a profile attribute; do not use NIP/password pairs as a substitute for Auth UID.
3. Store the authenticated UID as the owner field on each user's classes, attendance, profiles, and sessions. Enforce ownership in Firestore Rules or backend authorization.
4. Replace direct browser access to privileged collections with authenticated operations. Remote-control sessions must be short-lived, scoped to one user/device, revocable, and validated server-side. Do not put session bearer tokens in query strings.
5. Implement and run Emulator Suite tests for unauthenticated, authenticated-owner, authenticated-non-owner, expired-session, and admin/backend scenarios.
6. Migrate existing accounts/data with a one-time trusted script. Do not silently reset passwords or publish existing data.
7. Revoke and rotate any service-account key that has ever been included in a distributed build or public repository. Review Firebase IAM audit logs and production rules.
8. Deploy rules and backend only after the new client and backend have been verified together. The deny-all rules intentionally break current direct-client reads/writes if deployed before migration.

## Local validation

Install Firebase CLI and run:

```bash
cd gurupro_remote
firebase emulators:start --only auth,firestore,hosting
```

Before deploying any rules, add emulator tests and validate all application flows. No live Firebase deployment or integration test has been performed by this change.
