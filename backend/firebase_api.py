"""Small standard-library HTTP client for GuruPro's trusted Firebase Functions API.

No Firebase service-account key or Admin SDK is shipped with the desktop client.
Tokens are held in memory only and must be reacquired by signing in after restart.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any

API_BASE_URL = os.environ.get(
    "GURUPRO_API_URL",
    "https://us-central1-gurupro-app-bc6cc.cloudfunctions.net/api",
).rstrip("/")
_TIMEOUT_SECONDS = 25

_lock = threading.RLock()
_id_token: str | None = None
_refresh_token: str | None = None


class ApiError(RuntimeError):
    """An HTTP/API failure returned by the trusted GuruPro backend."""

    def __init__(self, message: str, status: int = 0, code: str = "api_error"):
        super().__init__(message)
        self.status = status
        self.code = code


def set_tokens(id_token: str | None, refresh_token: str | None = None) -> None:
    global _id_token, _refresh_token
    with _lock:
        _id_token = id_token or None
        if refresh_token is not None:
            _refresh_token = refresh_token or None


def clear_session() -> None:
    global _id_token, _refresh_token
    with _lock:
        _id_token = None
        _refresh_token = None


def has_session() -> bool:
    with _lock:
        return bool(_id_token)


def _raw_post(payload: dict[str, Any], token: str | None = None) -> Any:
    url = API_BASE_URL
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read().decode("utf-8"))
        except Exception:
            result = {}
        raise ApiError(
            result.get("error", f"Server menolak permintaan (HTTP {exc.code})."),
            status=exc.code,
            code=result.get("code", "http_error"),
        ) from exc
    except urllib.error.URLError as exc:
        raise ApiError(
            "Tidak dapat terhubung ke server GuruPro. Periksa koneksi internet dan URL API.",
            code="network_error",
        ) from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise ApiError("Respons server tidak valid atau waktu koneksi habis.", code="invalid_response") from exc

    if not isinstance(result, dict) or "data" not in result:
        raise ApiError("Format respons API tidak dikenali.", code="invalid_response")
    return result["data"]


def _refresh() -> bool:
    global _id_token, _refresh_token
    with _lock:
        refresh_token = _refresh_token
    if not refresh_token:
        return False
    try:
        result = _raw_post({"action": "auth.refresh", "refreshToken": refresh_token})
        if not isinstance(result, dict) or not result.get("idToken"):
            return False
        set_tokens(result["idToken"], result.get("refreshToken", refresh_token))
        return True
    except ApiError as exc:
        if exc.status in (401, 403):
            clear_session()
            return False
        # A transient server/network error must not erase a still-valid refresh token.
        raise


def api_call(action: str, **payload: Any) -> Any:
    """Call a backend action, refreshing an expired access token once."""
    with _lock:
        token = _id_token
    body = {"action": action, **payload}
    if not token:
        raise ApiError("Sesi login tidak tersedia. Silakan masuk kembali.", 401, "unauthenticated")
    try:
        return _raw_post(body, token)
    except ApiError as exc:
        if exc.status != 401 or not _refresh():
            raise
        with _lock:
            token = _id_token
        return _raw_post(body, token)


def login(nip: str, password: str) -> dict[str, Any]:
    result = _raw_post({"action": "auth.login", "nip": nip, "password": password})
    if not isinstance(result, dict) or not result.get("idToken") or not result.get("profile"):
        raise ApiError("Server tidak mengembalikan sesi login yang valid.", code="invalid_login_response")
    set_tokens(result["idToken"], result.get("refreshToken"))
    return result["profile"]


def register(data: dict[str, Any]) -> dict[str, Any]:
    return _raw_post({"action": "auth.register", **data})


def update_profile(data: dict[str, Any]) -> Any:
    return api_call("profile.update", data=data)


def change_password(current_password: str, new_password: str) -> Any:
    return api_call(
        "profile.password",
        currentPassword=current_password,
        newPassword=new_password,
    )


def logout() -> None:
    clear_session()
