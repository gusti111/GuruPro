# GuruPro

GuruPro is a teacher-oriented application project with a PyQt6 desktop interface and a remote web interface for selected workflows.

## Project areas
- Teacher profile and account registration
- Class and student management
- Teaching and attendance workflows
- Reports
- Remote device/session functionality

## Technology
- Python
- PyQt6
- Firebase Admin SDK / Cloud Firestore
- HTML, CSS, and JavaScript for the remote interface

## Setup
1. Install Python 3.10 or newer.
2. Create a virtual environment and install the project's Python dependencies.
3. Configure Firebase credentials locally. Keep service-account JSON files out of Git.
4. Run the desktop entry point with `python main.py`.

## Security notes
This is a development project. Do not use it with real student or teacher data until authentication, authorization, and Firestore security rules have been reviewed and tested. New and updated passwords are stored as salted PBKDF2-HMAC-SHA256 hashes. Legacy plaintext passwords are migrated after a successful login. Review any other clients or integrations that read the Firestore password field before deploying this change. Firebase Admin SDK credentials must remain server-side and must never be bundled into a public client application.

## Author
Gusty Faqikh
