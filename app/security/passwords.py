import base64
import hashlib
import hmac
import secrets

_N = 2**14
_R = 8
_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=64)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"scrypt${_N}${_R}${_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, digest_value = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        n_value, r_value, p_value = int(n), int(r), int(p)
        if (n_value, r_value, p_value) != (_N, _R, _P):
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        expected = hashlib.scrypt(
            password.encode(),
            salt=decode(salt_value),
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=64,
        )
        return hmac.compare_digest(expected, decode(digest_value))
    except (ValueError, TypeError):
        return False
