"""JWT issuing and verification (HS256 by default).

Token claims follow the spec's securityScheme description:
'sub' - user identifier, 'exp' - Unix expiration time, plus 'role'
('user'/'admin') so admin rights are verified from the token itself.
"""

from datetime import datetime, timezone

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.domains import models as dm
from app.services.exceptions import InvalidToken, TokenExpired
from app.settings import Settings


class AuthService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def issue_token(self, user_id: int, role: dm.Role,
                    now: datetime | None = None) -> dm.AuthToken:
        issued_at = now or datetime.now(timezone.utc)
        exp = int(issued_at.timestamp()) + self._settings.access_token_ttl_seconds
        raw = jwt.encode(
            {"sub": str(user_id), "exp": exp, "role": role.value},
            self._settings.secret,
            algorithm=self._settings.jwt_algorithm,
        )
        return dm.AuthToken(sub=user_id, exp=exp, role=role, raw=raw)

    def decode_token(self, token: str) -> dm.AuthToken:
        try:
            payload = jwt.decode(
                token, self._settings.secret, algorithms=[self._settings.jwt_algorithm]
            )
        except ExpiredSignatureError:
            raise TokenExpired()
        except InvalidTokenError:
            raise InvalidToken()
        try:
            sub = int(payload["sub"])
            role = dm.Role(payload.get("role", dm.Role.USER.value))
        except (KeyError, TypeError, ValueError):
            raise InvalidToken()
        return dm.AuthToken(sub=sub, exp=payload["exp"], role=role, raw=token)
