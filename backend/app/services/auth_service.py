"""JWT authentication and user management for Weave."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserRecord
from app.db.session import db_session, get_session_factory

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
PRIMARY_ADMIN_USERNAME = "Saurabh"
ROLE_ADMIN = "admin"
ROLE_USER = "user"

FEATURE_USER_MANAGEMENT = "user_management"

FEATURE_CATALOG: List[Dict[str, str]] = [
    {"key": "dashboard", "label": "Dashboard", "description": "Platform overview"},
    {"key": "create_knowledge", "label": "Create Knowledge", "description": "Fabric builder and uploads"},
    {"key": "train_ml", "label": "Train ML Models", "description": "Model training and distribution"},
    {"key": "fabrics", "label": "Available Fabrics", "description": "Fabric catalog and knowledge graphs"},
    {"key": "test_llm", "label": "Test with LLM", "description": "Agent testing and fabric queries"},
    {"key": "context", "label": "Context Analysis", "description": "Semantic insights"},
    {"key": "ontology", "label": "Ontology Discovery", "description": "Schema explorer and workspace"},
    {"key": "ontology_enrichment", "label": "Ontology Enrichment", "description": "AI governance queue"},
    {"key": "agent_utilities", "label": "Agent Data Utilities", "description": "Agent toolkit"},
    {
        "key": FEATURE_USER_MANAGEMENT,
        "label": "User Management",
        "description": "Create and manage platform users (admins only)",
    },
]

ALL_FEATURE_KEYS = [item["key"] for item in FEATURE_CATALOG]
GRANTABLE_FEATURE_KEYS = [k for k in ALL_FEATURE_KEYS if k != FEATURE_USER_MANAGEMENT]
DEFAULT_USER_FEATURES = ["dashboard", "fabrics"]

SEED_USERS = (
    {
        "username": PRIMARY_ADMIN_USERNAME,
        "password": "admin123",
        "display_name": "Saurabh",
        "role": ROLE_ADMIN,
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

    def normalize_features(self, features: Optional[Sequence[str]], *, role: str) -> List[str]:
        if role == ROLE_ADMIN:
            return list(ALL_FEATURE_KEYS)
        allowed = set(GRANTABLE_FEATURE_KEYS)
        cleaned: List[str] = []
        for key in features or []:
            key = str(key).strip()
            if key in allowed and key not in cleaned:
                cleaned.append(key)
        # Dashboard is always available so users are never locked out of home
        if "dashboard" not in cleaned:
            cleaned.insert(0, "dashboard")
        return cleaned

    def user_has_feature(self, user: UserRecord, feature_key: str) -> bool:
        if not user or not user.is_active:
            return False
        if feature_key == "dashboard":
            return True
        if (user.role or ROLE_USER) == ROLE_ADMIN:
            return True
        features = user.allowed_features or []
        return feature_key in features

    def is_admin(self, user: UserRecord) -> bool:
        return bool(user and user.is_active and (user.role or ROLE_USER) == ROLE_ADMIN)

    def create_access_token(self, user: UserRecord) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role or ROLE_USER,
            "allowed_features": self.effective_features(user),
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

    def effective_features(self, user: UserRecord) -> List[str]:
        if self.is_admin(user):
            return list(ALL_FEATURE_KEYS)
        return list(user.allowed_features or [])

    def _count_active_admins(self, session: Session, exclude_user_id: Optional[str] = None) -> int:
        query = session.query(UserRecord).filter(
            UserRecord.role == ROLE_ADMIN,
            UserRecord.is_active.is_(True),
        )
        if exclude_user_id:
            query = query.filter(UserRecord.id != exclude_user_id)
        return query.count()

    def ensure_seed_users(self) -> None:
        with db_session() as session:
            # Backfill role for rows created before RBAC columns existed
            for row in session.query(UserRecord).all():
                if not row.role:
                    row.role = ROLE_USER
                if row.allowed_features is None:
                    row.allowed_features = list(DEFAULT_USER_FEATURES)

            for spec in SEED_USERS:
                existing = (
                    session.query(UserRecord)
                    .filter(UserRecord.username == spec["username"])
                    .one_or_none()
                )
                if existing is None:
                    user = UserRecord(
                        id=f"usr_{uuid.uuid4().hex[:12]}",
                        username=spec["username"],
                        display_name=spec["display_name"],
                        password_hash=self.hash_password(spec["password"]),
                        role=spec.get("role", ROLE_ADMIN),
                        allowed_features=list(ALL_FEATURE_KEYS),
                        is_active=True,
                    )
                    session.add(user)
                    logger.info("Created Weave seed user %s", spec["username"])
                else:
                    existing.role = ROLE_ADMIN
                    existing.is_active = True
                    existing.allowed_features = list(ALL_FEATURE_KEYS)
                    if not existing.display_name:
                        existing.display_name = spec["display_name"]
                    logger.info("Ensured Weave admin user %s", spec["username"])

    def list_users(self) -> List[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            users = session.query(UserRecord).order_by(UserRecord.created_at.asc()).all()
            return [self.user_to_dict(u, include_admin_fields=True) for u in users]
        finally:
            session.close()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        role: str = ROLE_USER,
        allowed_features: Optional[Sequence[str]] = None,
    ) -> UserRecord:
        username = username.strip()
        display_name = (display_name or username).strip()
        role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER
        if not username:
            raise ValueError("Username is required.")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")

        features = self.normalize_features(
            allowed_features if role == ROLE_USER else ALL_FEATURE_KEYS,
            role=role,
        )
        if role == ROLE_USER and not features:
            features = list(DEFAULT_USER_FEATURES)

        with db_session() as session:
            existing = (
                session.query(UserRecord)
                .filter(UserRecord.username == username)
                .one_or_none()
            )
            if existing:
                raise ValueError(f"Username '{username}' is already taken.")
            user = UserRecord(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                username=username,
                display_name=display_name,
                password_hash=self.hash_password(password),
                role=role,
                allowed_features=features if role == ROLE_USER else list(ALL_FEATURE_KEYS),
                is_active=True,
            )
            session.add(user)
            session.flush()
            session.refresh(user)
            logger.info("Created Weave user %s role=%s", username, role)
            # Detach a plain copy for return outside session
            return self._detached_copy(user)

    def update_user(
        self,
        user_id: str,
        *,
        actor_id: str,
        display_name: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[str] = None,
        allowed_features: Optional[Sequence[str]] = None,
        is_active: Optional[bool] = None,
    ) -> UserRecord:
        with db_session() as session:
            user = session.get(UserRecord, user_id)
            if not user:
                raise ValueError("User not found.")

            next_role = user.role or ROLE_USER
            if role is not None:
                next_role = ROLE_ADMIN if role == ROLE_ADMIN else ROLE_USER

            if user_id == actor_id:
                if is_active is False:
                    raise ValueError("You cannot deactivate your own account.")
                if next_role != ROLE_ADMIN and self.is_admin(user):
                    raise ValueError("You cannot demote your own admin account.")

            if (
                (user.role or ROLE_USER) == ROLE_ADMIN
                and (next_role != ROLE_ADMIN or is_active is False)
                and self._count_active_admins(session, exclude_user_id=user_id) < 1
            ):
                raise ValueError("Cannot remove or demote the last active admin.")

            if display_name is not None:
                cleaned = display_name.strip()
                if not cleaned:
                    raise ValueError("Display name cannot be empty.")
                user.display_name = cleaned

            if password is not None:
                if len(password) < 6:
                    raise ValueError("Password must be at least 6 characters.")
                user.password_hash = self.hash_password(password)

            if role is not None:
                user.role = next_role

            if allowed_features is not None or role is not None:
                features_source = (
                    allowed_features
                    if allowed_features is not None
                    else (user.allowed_features or [])
                )
                user.allowed_features = self.normalize_features(
                    features_source,
                    role=user.role or ROLE_USER,
                )

            if is_active is not None:
                user.is_active = bool(is_active)

            if (user.role or ROLE_USER) == ROLE_ADMIN:
                user.allowed_features = list(ALL_FEATURE_KEYS)

            user.updated_at = datetime.utcnow()
            session.flush()
            session.refresh(user)
            logger.info("Updated Weave user %s", user.username)
            return self._detached_copy(user)

    def delete_user(self, user_id: str, *, actor_id: str) -> Dict[str, Any]:
        with db_session() as session:
            user = session.get(UserRecord, user_id)
            if not user:
                raise ValueError("User not found.")
            if user_id == actor_id:
                raise ValueError("You cannot delete your own account.")
            if (user.role or ROLE_USER) == ROLE_ADMIN and self._count_active_admins(
                session, exclude_user_id=user_id
            ) < 1:
                raise ValueError("Cannot delete the last active admin.")

            snapshot = self.user_to_dict(user, include_admin_fields=True)
            session.delete(user)
            logger.info("Deleted Weave user %s", snapshot.get("username"))
            return snapshot

    def _detached_copy(self, user: UserRecord) -> UserRecord:
        copy = UserRecord(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            password_hash=user.password_hash,
            role=user.role or ROLE_USER,
            allowed_features=list(user.allowed_features or []),
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        return copy

    def user_to_dict(self, user: UserRecord, *, include_admin_fields: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role or ROLE_USER,
            "allowed_features": self.effective_features(user),
            "is_active": bool(user.is_active),
        }
        if include_admin_fields:
            data["created_at"] = user.created_at.isoformat() if user.created_at else None
            data["updated_at"] = user.updated_at.isoformat() if user.updated_at else None
        return data

    def feature_catalog(self, *, for_admin_ui: bool = True) -> List[Dict[str, Any]]:
        items = []
        for item in FEATURE_CATALOG:
            if not for_admin_ui and item["key"] == FEATURE_USER_MANAGEMENT:
                continue
            items.append(
                {
                    **item,
                    "grantable": item["key"] != FEATURE_USER_MANAGEMENT,
                    "default_for_user": item["key"] in DEFAULT_USER_FEATURES,
                }
            )
        return items


auth_service = AuthService()
