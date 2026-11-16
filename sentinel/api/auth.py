"""JWT and password primitives. Verification is strict: fixed algorithm, required claims, real expiry.

The old Sentinel shipped auth that never ran (it passed the wrong object into the verifier, the error
was swallowed, and every request became an anonymous viewer). Here verification either returns a valid
claim set or raises TokenError — there is no silent anonymous fallback anywhere.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

import jwt  # PyJWT

ALGORITHM = "HS256"
ROLE_LEVELS = {"viewer": 0, "analyst": 1, "admin": 2}


class TokenError(Exception):
    pass


def create_access_token(secret: str, sub: str, org_id: str, role: str,
                        ttl_seconds: int, now: int | None = None) -> str:
    if role not in ROLE_LEVELS:
        raise ValueError(f"unknown role {role}")
    issued = int(time.time()) if now is None else now
    payload = {"sub": sub, "org_id": org_id, "role": role,
               "iat": issued, "exp": issued + ttl_seconds, "type": "access"}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_token(secret: str, token: str) -> dict:
    if not secret:
        raise TokenError("server misconfigured: empty secret")
    try:
        # algorithms is pinned, so alg=none and alg-confusion attacks are rejected.
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM],
                             options={"require": ["exp", "iat", "sub"]})
    except jwt.ExpiredSignatureError:
        raise TokenError("token expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"invalid token: {e}")
    if payload.get("type") != "access":
        raise TokenError("not an access token")
    for claim in ("sub", "org_id", "role"):
        if not payload.get(claim):
            raise TokenError(f"missing claim: {claim}")
    if payload["role"] not in ROLE_LEVELS:
        raise TokenError("unknown role")
    return payload


def role_at_least(user_role: str, required: str) -> bool:
    return ROLE_LEVELS.get(user_role, -1) >= ROLE_LEVELS[required]


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = os.urandom(16) if salt is None else salt
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split(":")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(dk.hex(), dk_hex)
