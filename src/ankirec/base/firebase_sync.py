"""
firebase_sync.py — keep a per-user JSON file in sync across devices
using Firebase Authentication + Realtime Database, over plain HTTPS.

Only dependency:  pip install requests

Fill in API_KEY and DB_URL from your Firebase project (see setup notes).
Both are safe to ship in your app; the database rules do the protecting.
"""

import json
import os
import sys
import time
from pathlib import Path
 
import requests
 
API_KEY = "AIzaSyD7UyDDxMxVc0UOrChRXQmKUATAu1s1Y9A" # this is not secret
DB_URL = "https://ankirec-58465-default-rtdb.europe-west1.firebasedatabase.app"
APP_NAME = "ankirec"
MAX_CHARS = 200_000  # must match the ".validate" rule
 
AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"
TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
 
 
class SyncError(Exception):
    pass
 
 
class ConflictError(SyncError):
    """Another device saved since you loaded. Call load() again, re-apply, save."""
 
 
def _session_file() -> Path:
    base = os.environ.get("APPDATA") if sys.platform == "win32" else None
    base = Path(base) if base else Path.home() / ".config"
    return base / APP_NAME / "session.json"
 
 
def _check(r: requests.Response) -> dict:
    if r.ok:
        return r.json()
    try:
        msg = r.json()["error"]
        msg = msg.get("message", msg) if isinstance(msg, dict) else msg
    except Exception:
        msg = r.text
    raise SyncError(f"{r.status_code}: {msg}")
 
 
class FirebaseStore:
    def __init__(self):
        self.s = requests.Session()
        self.uid = self.id_token = self.refresh_token = None
        self.expires_at = 0.0
        self._etag = None
        self._load_session()
 
    # ------------------------------------------------------------ accounts
 
    @property
    def signed_in(self) -> bool:
        return self.refresh_token is not None

    @property
    def email(self) -> str | None:
        """Return the email address of the signed-in user."""
        if not self.signed_in:
            return None

        d = _check(self.s.post(
            f"{AUTH_URL}:lookup",
            params={"key": API_KEY},
            json={"idToken": self._token()},
            timeout=10
        ))

        return d["users"][0].get("email")
 
    def sign_up(self, email: str, password: str) -> None:
        """Create an account and send the verification email."""
        self._auth("signUp", email, password)
        self.send_verification_email()
 
    def sign_in(self, email: str, password: str) -> None:
        self._auth("signInWithPassword", email, password)
 
    def sign_out(self) -> None:
        self.uid = self.id_token = self.refresh_token = None
        _session_file().unlink(missing_ok=True)
 
    def send_password_reset(self, email: str) -> None:
        _check(self.s.post(f"{AUTH_URL}:sendOobCode", params={"key": API_KEY},
                           json={"requestType": "PASSWORD_RESET", "email": email}, timeout=10))
 
    def send_verification_email(self) -> None:
        _check(self.s.post(f"{AUTH_URL}:sendOobCode", params={"key": API_KEY},
                           json={"requestType": "VERIFY_EMAIL", "idToken": self._token()},
                           timeout=10))
 
    def email_verified(self) -> bool:
        """Ask Firebase whether the user has clicked the verification link yet."""
        d = _check(self.s.post(f"{AUTH_URL}:lookup", params={"key": API_KEY},
                               json={"idToken": self._token()}, timeout=10))
        verified = d["users"][0].get("emailVerified", False)
        if verified:
            self.expires_at = 0  # get a fresh token that carries the verified flag
        return verified
 
    def _auth(self, action: str, email: str, password: str) -> None:
        d = _check(self.s.post(f"{AUTH_URL}:{action}", params={"key": API_KEY},
                               json={"email": email.strip(), "password": password,
                                     "returnSecureToken": True}, timeout=10))
        self._set_tokens(d["localId"], d["idToken"], d["refreshToken"], d["expiresIn"])
 
    def _set_tokens(self, uid, id_token, refresh_token, expires_in) -> None:
        self.uid, self.id_token, self.refresh_token = uid, id_token, refresh_token
        self.expires_at = time.time() + int(expires_in) - 60  # refresh a minute early
        self._save_session()
 
    def _token(self) -> str:
        """A valid ID token, refreshed silently when it is about to expire."""
        if not self.signed_in:
            raise SyncError("Not signed in")
        if time.time() >= self.expires_at:
            d = _check(self.s.post(TOKEN_URL, params={"key": API_KEY}, timeout=10, data={
                "grant_type": "refresh_token", "refresh_token": self.refresh_token}))
            self._set_tokens(d["user_id"], d["id_token"], d["refresh_token"], d["expires_in"])
        return self.id_token
 
    # ------------------------------------------------------------ session file
 
    def _save_session(self) -> None:
        f = _session_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"uid": self.uid, "refresh_token": self.refresh_token}))
        if sys.platform != "win32":
            f.chmod(0o600)  # readable by this user only
 
    def _load_session(self) -> None:
        try:
            d = json.loads(_session_file().read_text())
            self.uid, self.refresh_token = d["uid"], d["refresh_token"]
        except (OSError, ValueError, KeyError):
            pass  # not signed in on this device yet
 
    # ------------------------------------------------------------ data
 
    def _db(self, method: str, **kw) -> requests.Response:
        url = f"{DB_URL}/users/{self.uid}.json"
        for attempt in (1, 2):
            r = self.s.request(method, url, params={"auth": self._token()}, timeout=10, **kw)
            if r.status_code != 401 or attempt == 2:
                break
            self.expires_at = 0  # token may predate email verification: refresh and retry
        if r.status_code == 401:
            raise SyncError("Permission denied. Has this account's email been verified?")
        return r
 
    def load(self, default=None):
        r = self._db("GET", headers={"X-Firebase-ETag": "true"})
        data = _check(r)
        self._etag = r.headers.get("ETag")
        if data is None:
            return {} if default is None else default
        return json.loads(data) if isinstance(data, str) else data  # dict = old format
 
    def save(self, data) -> None:
        """Save, refusing to overwrite changes another device made since load()."""
        payload = json.dumps(data, separators=(",", ":"))
        if len(payload) > MAX_CHARS:
            raise SyncError(f"Data too large ({len(payload):,} characters, limit {MAX_CHARS:,})")
        headers = {"if-match": self._etag} if self._etag else {}
        r = self._db("PUT", json=payload, headers=headers)
        if r.status_code == 412:
            raise ConflictError("Data changed on another device since it was loaded")
        _check(r)
        self._etag = r.headers.get("ETag")
 
 
# ---------------------------------------------------------------- example
 
if __name__ == "__main__":
    import getpass
 
    store = FirebaseStore()
    just_signed_up = False
    if not store.signed_in:
        email = input("Email: ").strip().strip("\"'")
        password = getpass.getpass("Password: ")
        if input("New account? [y/N] ").strip().lower() == "y":
            store.sign_up(email, password)
            just_signed_up = True
        else:
            store.sign_in(email, password)
 
    if not store.email_verified():
        if not just_signed_up:
            store.send_verification_email()
        print("A verification email has been sent (check your spam folder too).")
        while not store.email_verified():
            if input("Press Enter once you've clicked the link (r = resend): ").strip().lower() == "r":
                store.send_verification_email()
 
    data = store.load(default={"settings": {}, "count": 0})
    data["count"] = data.get("count", 0) + 1
    store.save(data)
    print("Synced:", data)
 
