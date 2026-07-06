"""JWT authentication and user management for Weave."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserRecord
from app.db.session import db_session, get_session_factory

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
PRIMARY_ADMIN_USERNAME = "Saurabh"
SEED_USERS = (
    {
        "username": PRIMARY_ADMIN_USERNAME,
        "password": "admin123",
        "display_name": "Saurabh",
    },
)


class AuthService:
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except ValueError:
            return False

    def create_access_token(self, user: UserRecord) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "exp": expire,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            return None

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        session = get_session_factory()()
        try:
            return session.get(UserRecord, user_id)
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[UserRecord]:
        session = get_session_factory()()
        try:
            return (
                session.query(UserRecord)
                .filter(UserRecord.username == username)
                .one_or_none()
            )
        finally:
            session.close()

    def authenticate(self, username: str, password: str) -> Optional[UserRecord]:
        user = self.get_user_by_username(username.strip())
        if not user or not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def _upsert_user(self, session: Session, username: str, password: str, display_name: str) -> UserRecord:
        user = (
            session.query(UserRecord)
            .filter(UserRecord.username == username)
            .one_or_none()
        )
        if user is None:
            user = UserRecord(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                username=username,
                display_name=display_name,
                password_hash=self.hash_password(password),
                is_active=True,
            )
            session.add(user)
            logger.info("Created Weave user %s", username)
        else:
            user.display_name = display_name
            user.password_hash = self.hash_password(password)
            user.is_active = True
            logger.info("Updated Weave seed user %s", username)
        return user

    def ensure_seed_users(self) -> None:
        with db_session() as session:
            for spec in SEED_USERS:
                self._upsert_user(
                    session,
                    username=spec["username"],
                    password=spec["password"],
                    display_name=spec["display_name"],
                )

    def user_to_dict(self, user: UserRecord) -> Dict[str, Any]:
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
        }


auth_service = AuthService()
