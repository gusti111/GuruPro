# Security architecture and deployment checklist

## Current repository changes

The security branch introduces an API-first architecture:

- The desktop application no longer initializes Firebase Admin SDK and no longer reads a service-account JSON file.
- Desktop login and data operations use the HTTPS Firebase Functions API through `backend/firebase_api.py`.
- The remote PWA no longer loads the Firebase Firestore SDK or accesses Firestore directly. It calls the same API.
- Firebase Authentication ID tokens identify a Firebase UID. NIP remains a profile attribute and legacy account lookup key.
- Firebase Functions owns privileged Firestore operations using server-side Admin SDK credentials supplied by the Firebase runtime.
- API operations verify the ID token, confirm the user profile, validate client type, and verify class/session ownership before reading or changing protected data.
- New remote pairing uses a cryptographically random, one-time token in the URL fragment. The server stores only its SHA-256 digest, expires it after 3 minutes, and marks it used atomically.
- Every paired remote device receives its own Firebase Auth UID, persistently bound to the teacher owner and one session. Refreshing the token does not remove this binding. Remote sessions expire after 12 hours and are checked on each API request. Browser refresh credentials are held in a Secure, HttpOnly, SameSite=Strict cookie; the access token is kept in page memory.
- A scheduled cleanup removes expired pairings and disconnected/expired device sessions, and revokes/deletes their Firebase Auth identities.
- Passwords use salted PBKDF2-HMAC-SHA256. Legacy plaintext hashes are upgraded only after a successful login; login errors do not disclose whether a NIP exists.
- Firestore Rules deny all direct client SDK access. Functions Admin SDK access is server-side and bypasses these rules by design.
- Firestore timestamp values are serialized as ISO-8601 strings for clients.

## Files changed

- `backend/firebase_api.py`: standard-library HTTPS client for the desktop app.
- `backend/database.py`: API-backed data-access wrapper; no Firebase Admin SDK.
- `gurupro_remote/functions/index.js`: server-side authentication, authorization, data and pairing API.
- `gurupro_remote/functions/package.json`: Functions runtime dependencies.
- `gurupro_remote/firestore.rules`: fail-closed client rules.
- `gurupro_remote/firebase.json`: Functions, Hosting API rewrites, Firestore rules, and emulator config.
- `gurupro_remote/remote-app.js` and `gurupro_remote/index.html`: API-backed PWA client.
- `gurupro_remote/service-worker.js`: API/auth requests are never cached.
- Desktop controllers: reports, attendance, and device management now call the API.
- GitHub Actions: Python compile/unit tests, Firestore Rules Emulator tests, and Node Functions syntax checks.

## Firebase project configuration required

The repository cannot set Firebase Console secrets, IAM policies, billing, API enablement, or deploy the live project. Before deployment:

1. Confirm that `gurupro-app-bc6cc` is the intended Firebase project and make a Firestore export/backup.
2. In Firebase Console > Project settings > General, copy the project's Web API key.
3. From `gurupro_remote/`, configure both Functions secrets:

   ```bash
   firebase functions:secrets:set FIREBASE_WEB_API_KEY
   firebase functions:secrets:set GURUPRO_REGISTRATION_CODE
   ```

   Paste the Web API key when prompted for the first secret. For the registration secret, use a long random value (at least 16 characters) and share it only with authorized teachers. It is required for new-account creation, so unauthenticated visitors cannot reserve arbitrary NIP values. Neither value belongs in Git or a client build. FIREBASE_WEB_API_KEY is used server-side to exchange Firebase custom tokens and refresh ID tokens.
4. Confirm Firebase Authentication is enabled and that the project's Identity Toolkit / Secure Token APIs are enabled.
5. Confirm Cloud Functions Gen 2 deployment prerequisites and billing are enabled for the project.
6. Review whether any other mobile/web client, integration, scheduled job, or third-party system still accesses Firestore directly. The deny-all rules will block all such client SDK access.
7. Review Firebase IAM roles and rotate/revoke any service-account key that was ever embedded in a desktop/mobile build or committed to source control. The new client must not ship any Admin SDK key.

## Deploy only after backup and client review

From `gurupro_remote/`:

```bash
npm install
cd functions && npm install && cd ..
```

For local emulators, create `functions/.secret.local` (already git-ignored) with the same variable names:

```dotenv
FIREBASE_WEB_API_KEY=your-firebase-web-api-key
GURUPRO_REGISTRATION_CODE=your-local-enrollment-code-at-least-16-chars
```

Then start the emulators:

```bash
firebase emulators:start --only auth,firestore,functions,hosting
```

For a deliberate production deployment after emulator and application-flow testing:

```bash
firebase deploy --only functions:api,hosting,firestore:rules
```

The Python desktop client can override the function URL with `GURUPRO_API_URL` if the deployment region/project changes. The default is `https://us-central1-gurupro-app-bc6cc.cloudfunctions.net/api`.

## Remaining external validation

This branch does not claim the live Firebase project has been migrated. Before treating the project as production-ready, verify:

- Successful deployment of the Functions API and Hosting rewrites.
- Firebase Auth sign-in, token refresh, password change, legacy-account migration, and revocation.
- Owner/non-owner class access, student import, attendance save/read/delete, and cross-account denial.
- One-time QR pairing, expired/reused pairing denial, device logout/revocation, and 12-hour expiry.
- All existing clients have been upgraded before deploying deny-all rules.
- Backup restore and production IAM/audit log review.

No production deployment, live database migration, real-account test, or full end-to-end Functions/Auth/Firestore emulator session was performed. The GitHub Actions Firestore Rules Emulator suite did pass on the latest rules-workflow revision; Python security/compile tests and Functions + both PWA syntax tests also passed on their latest relevant revisions. These checks validate source boundaries and rules behaviour, not the live Firebase project's configuration or deployed runtime.
