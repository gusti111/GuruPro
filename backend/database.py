"""GuruPro data-access layer.

All protected Firestore operations are executed by the Firebase Functions API.
The desktop application never initializes Firebase Admin SDK and never loads a
service-account JSON file.
"""
from __future__ import annotations

from typing import Any

from backend import firebase_api
from backend.firebase_api import ApiError


# Kept as None during the migration to make accidental direct Firestore access
# fail visibly instead of silently reverting to a bundled Admin credential.
db = None
firestore = None


def cek_login(nip: str, password: str):
    try:
        user = firebase_api.login(nip.strip(), password)
        return True, user
    except ApiError as exc:
        return False, str(exc)


def daftar_guru_baru(data_guru: dict[str, Any]):
    try:
        result = firebase_api.register(data_guru)
        return bool(result.get("success")), result.get("message", "Pendaftaran selesai.")
    except ApiError as exc:
        return False, str(exc)


def logout():
    firebase_api.logout()


def update_profil_guru(doc_id: str, data_baru: dict[str, Any]):
    try:
        result = firebase_api.update_profile(data_baru)
        profile = result.get("profile") if isinstance(result, dict) else None
        return True, profile or "Profil diperbarui."
    except ApiError as exc:
        return False, str(exc)


def update_password(doc_id: str, password_baru: str, password_lama: str | None = None):
    if not password_lama:
        return False, "Password saat ini wajib dimasukkan."
    try:
        firebase_api.change_password(password_lama, password_baru)
        firebase_api.clear_session()
        return True, "Password berhasil diubah. Silakan login kembali."
    except ApiError as exc:
        return False, str(exc)


def tambah_kelas(data_kelas: dict[str, Any]):
    try:
        result = firebase_api.api_call("class.create", data=data_kelas)
        return bool(result.get("success")), result.get("message", "Kelas berhasil dibuat.")
    except ApiError as exc:
        return False, str(exc)


def ambil_daftar_kelas(nip_guru: str | None = None):
    try:
        result = firebase_api.api_call("class.list")
        return result if isinstance(result, list) else []
    except ApiError:
        return []


def hapus_kelas(doc_id: str):
    try:
        result = firebase_api.api_call("class.delete", classId=doc_id)
        return bool(result.get("success"))
    except ApiError:
        return False


def simpan_daftar_siswa_massal(id_kelas: str, list_siswa: list[dict[str, Any]]):
    try:
        result = firebase_api.api_call(
            "students.import", classId=id_kelas, students=list_siswa
        )
        return bool(result.get("success"))
    except ApiError:
        return False


def ambil_jumlah_siswa(id_kelas: str):
    try:
        result = firebase_api.api_call("students.count", classId=id_kelas)
        return int(result.get("count", 0))
    except (ApiError, TypeError, ValueError):
        return 0


def ambil_siswa_per_kelas(id_kelas: str):
    try:
        result = firebase_api.api_call("students.list", classId=id_kelas)
        return result if isinstance(result, list) else []
    except ApiError:
        return []


def simpan_absensi_ke_db(data_absensi: dict[str, Any]):
    try:
        result = firebase_api.api_call("attendance.save", data=data_absensi)
        return True, result.get("message", "Absensi tersimpan.")
    except ApiError as exc:
        return False, str(exc)


def ambil_absensi_pertemuan(id_kelas: str, pertemuan: str):
    try:
        return firebase_api.api_call(
            "attendance.get", classId=id_kelas, pertemuan=pertemuan
        )
    except ApiError:
        return None


def ambil_rekap_absensi(id_kelas: str):
    try:
        result = firebase_api.api_call("attendance.list", classId=id_kelas)
        return result if isinstance(result, list) else []
    except ApiError:
        return []


# Remote-device lifecycle. The API creates high-entropy, one-time QR pairing
# tokens; the short session document ID is not exposed as an authentication key.
def buat_sesi_remote():
    return firebase_api.api_call("remote.createPairing")


def ambil_sesi_remote():
    result = firebase_api.api_call("remote.sessions.list")
    return result if isinstance(result, list) else []


def ambil_sesi_remote_id(session_id: str):
    return firebase_api.api_call("remote.session.get", sessionId=session_id)


def update_sesi_remote(session_id: str, **changes: Any):
    return firebase_api.api_call(
        "remote.session.update", sessionId=session_id, **changes
    )


def hapus_sesi_remote(session_id: str):
    result = firebase_api.api_call("remote.session.delete", sessionId=session_id)
    return bool(result.get("success"))


def poll_perintah_remote():
    result = firebase_api.api_call("remote.pollCommands")
    return result if isinstance(result, list) else []


def inisialisasi_sesi_remote(token: str, user_data: dict[str, Any]):
    """Deprecated compatibility wrapper; use buat_sesi_remote()."""
    return buat_sesi_remote()


def update_status_remote(session_id: str, status_baru: str):
    try:
        update_sesi_remote(session_id, status=status_baru)
        return True
    except ApiError:
        return False


def pantau_sesi_remote(session_id: str, callback):
    """Deprecated: desktop now polls the authenticated API instead of listening to Firestore."""
    return None
