import base64
import hashlib
import hmac
import json
import os
import random
from typing import Any

from Crypto.Cipher import ARC4


def generate_nonce(millis: int):
    nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder="big")
    return base64.b64encode(nonce_bytes).decode()


def generate_agent() -> str:
    agent_id = random_text(65, 69, 13)
    prefix = random_text(97, 122, 18)
    return f"{prefix}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"


def generate_device_id() -> str:
    return random_text(97, 122, 6)


def generate_signature(
    url, signed_nonce: str, nonce: str, params: dict[str, str]
) -> str:
    signature_params = [url.split("com")[1], signed_nonce, nonce]
    for k, v in params.items():
        signature_params.append(f"{k}={v}")
    signature_string = "&".join(signature_params)
    signature = hmac.new(
        base64.b64decode(signed_nonce),
        msg=signature_string.encode(),
        digestmod=hashlib.sha256,
    )
    return base64.b64encode(signature.digest()).decode()


def generate_enc_signature(
    url, method: str, signed_nonce: str, params: dict[str, str]
) -> str:
    signature_params = [str(method).upper(), url.split("com")[1].replace("/app/", "/")]
    for k, v in params.items():
        signature_params.append(f"{k}={v}")
    signature_params.append(signed_nonce)
    signature_string = "&".join(signature_params)
    return base64.b64encode(
        hashlib.sha1(signature_string.encode("utf-8")).digest()
    ).decode()


def generate_enc_params(
    url: str,
    method: str,
    signed_nonce: str,
    nonce: str,
    params: dict[str, str],
    ssecurity: str,
) -> dict[str, str]:
    params["rc4_hash__"] = generate_enc_signature(url, method, signed_nonce, params)
    for k, v in params.items():
        params[k] = encrypt_rc4(signed_nonce, v)
    params.update(
        {
            "signature": generate_enc_signature(url, method, signed_nonce, params),
            "ssecurity": ssecurity,
            "_nonce": nonce,
        }
    )
    return params


def to_json(response_text: str) -> any:
    return json.loads(response_text.replace("&&&START&&&", ""))


# The keys whose values in Xiaomi's login requests and responses give the
# session away: its secrets, the signatures a login is built on, and the URLs
# that carry either in their query.
_SECRET_KEYS = frozenset(
    {
        "_sign",
        "clientSign",
        "context",
        "ick",
        "location",
        "loginUrl",
        "lp",
        "nonce",
        "notificationUrl",
        "passToken",
        "psecurity",
        "qr",
        "serviceToken",
        "ssecurity",
        "ticket",
    }
)
REDACTED = "**REDACTED**"


def redacted(value: Any) -> Any:
    """A login request or response, as it may be logged.

    JSON text and dictionaries keep their shape, with the secret values
    masked. Any other text is logged only by its length, since a page can
    carry the same secrets.
    """
    if isinstance(value, str):
        try:
            value = to_json(value)
        except ValueError:
            return f"<{len(value)} characters>"
    return _masked(value)


def _masked(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if key in _SECRET_KEYS else _masked(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_masked(item) for item in value]
    return value


def without_query(url: Any) -> Any:
    """A URL as it may be logged: its query carries signatures and tokens."""
    return str(url).split("?", 1)[0] if url else url


def encrypt_rc4(password: str, payload: str) -> str:
    r = ARC4.new(base64.b64decode(password))
    r.encrypt(bytes(1024))
    return base64.b64encode(r.encrypt(payload.encode())).decode()


def decrypt_rc4(password: str, payload: str) -> bytes:
    r = ARC4.new(base64.b64decode(password))
    r.encrypt(bytes(1024))
    return r.encrypt(base64.b64decode(payload))


def random_text(chr_from: int, chr_to: int, length: int) -> str:
    return "".join([chr(random.randint(chr_from, chr_to)) for _ in range(length)])
