from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import secrets
import sqlite3
from typing import Literal
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .provisioning import ProvisionedStudent, provision_students


Role = Literal["platform_admin", "organization_admin", "teacher", "student"]
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    organization_id: str
    role: Role
    password_hash: str
    enabled: bool = True
    expires_at: datetime | None = None
    class_id: str | None = None


@dataclass(frozen=True)
class SessionContext:
    user_id: str
    organization_id: str
    role: Role


@dataclass(frozen=True)
class AccessSession:
    context: SessionContext
    expires_at: datetime


class AuthService:
    def __init__(self, users: dict[str, UserRecord], session_ttl: timedelta | None = None, storage_path: str | Path | None = None) -> None:
        self._users = users
        self._sessions: dict[str, AccessSession] = {}
        self._session_ttl = session_ttl or timedelta(days=1)
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_users()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("identity persistence is not configured")
        return sqlite3.connect(self._storage_path)

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists platform_users (username text primary key, user_id text not null, organization_id text not null, role text not null, password_hash text not null)")
            columns = {row[1] for row in connection.execute("pragma table_info(platform_users)")}
            if "enabled" not in columns:
                connection.execute("alter table platform_users add column enabled integer not null default 1")
            if "expires_at" not in columns:
                connection.execute("alter table platform_users add column expires_at text")
            if "class_id" not in columns:
                connection.execute("alter table platform_users add column class_id text")
            connection.execute("create table if not exists access_sessions (token_hash text primary key, user_id text not null, organization_id text not null, role text not null, expires_at text not null)")
            for username, user in self._users.items():
                connection.execute("insert or ignore into platform_users (username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id) values (?, ?, ?, ?, ?, ?, ?, ?)", (username, user.user_id, user.organization_id, user.role, user.password_hash, int(user.enabled), self._serialize_expiry(user.expires_at), user.class_id))

    def _load_users(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id from platform_users").fetchall()
        self._users.update({row[0]: UserRecord(row[1], row[2], row[3], row[4], bool(row[5]), self._parse_expiry(row[6]), row[7]) for row in rows})

    def _persist_user(self, username: str, user: UserRecord) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into platform_users (username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id) values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(username) do update set user_id=excluded.user_id, organization_id=excluded.organization_id, role=excluded.role, password_hash=excluded.password_hash, enabled=excluded.enabled, expires_at=excluded.expires_at, class_id=excluded.class_id", (username, user.user_id, user.organization_id, user.role, user.password_hash, int(user.enabled), self._serialize_expiry(user.expires_at), user.class_id))

    def login(self, username: str, password: str) -> SessionContext:
        user = self._users.get(username)
        if user is None or not self._is_active(user) or not verify_password(user.password_hash, password):
            raise PermissionError("invalid credentials")
        return SessionContext(
            user_id=user.user_id,
            organization_id=user.organization_id,
            role=user.role,
        )

    def create_access_session(self, context: SessionContext) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + self._session_ttl
        self._sessions[token] = AccessSession(context=context, expires_at=expires_at)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from access_sessions where expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
                connection.execute(
                    "insert into access_sessions values (?, ?, ?, ?, ?)",
                    (self._token_hash(token), context.user_id, context.organization_id, context.role, expires_at.isoformat()),
                )
        return token, expires_at

    def resolve_access_session(self, token: str) -> SessionContext:
        session = self._sessions.get(token)
        if session is None and self._storage_path:
            with self._connect() as connection:
                row = connection.execute(
                    "select user_id, organization_id, role, expires_at from access_sessions where token_hash = ?",
                    (self._token_hash(token),),
                ).fetchone()
            if row is not None:
                session = AccessSession(
                    context=SessionContext(user_id=row[0], organization_id=row[1], role=row[2]),
                    expires_at=datetime.fromisoformat(row[3]),
                )
        user = self._user_for_id(session.context.user_id) if session else None
        if session is None or session.expires_at <= datetime.now(timezone.utc) or user is None or not self._is_active(user):
            self._sessions.pop(token, None)
            if self._storage_path:
                with self._connect() as connection:
                    connection.execute("delete from access_sessions where token_hash = ?", (self._token_hash(token),))
            raise PermissionError("authentication required")
        return session.context

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def provision_students(
        self,
        *,
        prefix: str,
        count: int,
        class_id: str,
        initial_password: str,
        organization_id: str,
        expires_at: datetime | None = None,
    ) -> list[ProvisionedStudent]:
        students = provision_students(
            prefix=prefix,
            count=count,
            class_id=class_id,
            initial_password=initial_password,
            existing_usernames=set(self._users),
        )
        for student in students:
            self._users[student.username] = UserRecord(
                user_id=student.username,
                organization_id=organization_id,
                role="student",
                password_hash=hash_password(student.initial_password),
                expires_at=expires_at,
                class_id=student.class_id,
            )
            self._persist_user(student.username, self._users[student.username])
        return students

    def create_staff_user(
        self,
        *,
        username: str,
        password: str,
        organization_id: str,
        role: Literal["teacher", "organization_admin"],
        expires_at: datetime | None = None,
    ) -> UserRecord:
        normalized_username = username.strip()
        if not normalized_username or len(password) < 8:
            raise ValueError("username and an 8 character password are required")
        if normalized_username in self._users:
            raise ValueError("username already exists")
        user = UserRecord(
            user_id=f"{role}-{uuid.uuid4().hex[:12]}",
            organization_id=organization_id,
            role=role,
            password_hash=hash_password(password),
            expires_at=expires_at,
        )
        self._users[normalized_username] = user
        self._persist_user(normalized_username, user)
        return user

    def set_enabled_bulk(self, usernames: list[str], organization_id: str, enabled: bool) -> int:
        changed = 0
        for username in dict.fromkeys(usernames):
            user = self._users.get(username)
            if user is None or user.organization_id != organization_id:
                continue
            self.set_enabled(username, organization_id, enabled)
            changed += 1
        return changed

    def set_expiry_bulk(self, usernames: list[str], organization_id: str, expires_at: datetime | None) -> int:
        changed = 0
        for username in dict.fromkeys(usernames):
            user = self._users.get(username)
            if user is None or user.organization_id != organization_id:
                continue
            self.set_expiry(username, organization_id, expires_at)
            changed += 1
        return changed

    def users_for_organization(self, organization_id: str, *, role: Role | None = None, search: str | None = None, class_id: str | None = None, enabled: bool | None = None, expired: bool | None = None, offset: int = 0, limit: int | None = None) -> list[tuple[str, UserRecord]]:
        now = datetime.now(timezone.utc)
        normalized_search = search.strip().lower() if search else None
        users = []
        for username, user in self._users.items():
            if user.organization_id != organization_id or (role is not None and user.role != role):
                continue
            if normalized_search and normalized_search not in username.lower() and normalized_search not in user.user_id.lower():
                continue
            if class_id and user.class_id != class_id:
                continue
            if enabled is not None and user.enabled != enabled:
                continue
            is_expired = user.expires_at is not None and user.expires_at <= now
            if expired is not None and is_expired != expired:
                continue
            users.append((username, user))
        users.sort(key=lambda item: item[0])
        if offset:
            users = users[offset:]
        if limit is not None:
            users = users[:limit]
        return users

    def has_role(self, user_id: str, organization_id: str, role: Role) -> bool:
        return any(user.user_id == user_id and user.organization_id == organization_id and user.role == role for user in self._users.values())

    def has_active_role(self, user_id: str, organization_id: str, role: Role) -> bool:
        return any(user.user_id == user_id and self._is_active(user) for _, user in self.users_for_organization(organization_id, role=role))

    def user_for_id(self, user_id: str) -> UserRecord | None:
        return self._user_for_id(user_id)

    def set_class(self, user_id: str, organization_id: str, class_id: str | None) -> UserRecord:
        for username, user in self._users.items():
            if user.user_id == user_id and user.organization_id == organization_id:
                updated = UserRecord(user.user_id, user.organization_id, user.role, user.password_hash, user.enabled, user.expires_at, class_id)
                self._users[username] = updated
                self._persist_user(username, updated)
                return updated
        raise KeyError(user_id)

    @property
    def storage_path(self) -> Path | None:
        return self._storage_path

    def refresh_from_storage(self) -> None:
        if self._storage_path:
            self._load_users()
            self._sessions.clear()

    def has_platform_admin(self) -> bool:
        return any(user.role == "platform_admin" for user in self._users.values())

    def bootstrap_platform_admin(self, username: str, password: str, organization_id: str) -> SessionContext:
        if self.has_platform_admin():
            raise PermissionError("platform administrator already exists")
        if username in self._users:
            raise ValueError("username already exists")
        user = UserRecord(f"admin-{uuid.uuid4().hex[:12]}", organization_id, "platform_admin", hash_password(password))
        self._users[username] = user
        self._persist_user(username, user)
        return SessionContext(user.user_id, user.organization_id, user.role)

    def reset_password(self, username: str, organization_id: str, password: str) -> None:
        user = self._users.get(username)
        if user is None or user.organization_id != organization_id:
            raise KeyError(username)
        updated = UserRecord(user.user_id, user.organization_id, user.role, hash_password(password), user.enabled, user.expires_at, user.class_id)
        self._replace_user_and_revoke_sessions(username, updated)

    def _replace_user_and_revoke_sessions(self, username: str, user: UserRecord) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("update platform_users set password_hash = ?, enabled = ?, expires_at = ? where username = ? and organization_id = ?", (user.password_hash, int(user.enabled), self._serialize_expiry(user.expires_at), username, user.organization_id))
                connection.execute("delete from access_sessions where user_id = ?", (user.user_id,))
            self._users[username] = user
            self._sessions = {token: session for token, session in self._sessions.items() if session.context.user_id != user.user_id}
        else:
            self._persist_user(username, user)
            self._users[username] = user
            self.revoke_user_sessions(user.user_id)

    def set_enabled(self, username: str, organization_id: str, enabled: bool) -> None:
        user = self._users.get(username)
        if user is None or user.organization_id != organization_id:
            raise KeyError(username)
        updated = UserRecord(user.user_id, user.organization_id, user.role, user.password_hash, enabled, user.expires_at, user.class_id)
        if not enabled:
            self._replace_user_and_revoke_sessions(username, updated)
        else:
            self._persist_user(username, updated)
            self._users[username] = updated

    def set_expiry(self, username: str, organization_id: str, expires_at: datetime | None) -> None:
        user = self._users.get(username)
        if user is None or user.organization_id != organization_id:
            raise KeyError(username)
        updated = UserRecord(user.user_id, user.organization_id, user.role, user.password_hash, user.enabled, expires_at, user.class_id)
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            self._replace_user_and_revoke_sessions(username, updated)
        else:
            self._persist_user(username, updated)
            self._users[username] = updated

    def revoke_access_session(self, token: str) -> None:
        self._sessions.pop(token, None)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from access_sessions where token_hash = ?", (self._token_hash(token),))

    def revoke_user_sessions(self, user_id: str) -> None:
        self._sessions = {token: session for token, session in self._sessions.items() if session.context.user_id != user_id}
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from access_sessions where user_id = ?", (user_id,))

    def revoke_organization_sessions(self, organization_id: str, *, except_user_id: str | None = None) -> int:
        affected_users = {user.user_id for user in self._users.values() if user.organization_id == organization_id and user.user_id != except_user_id}
        in_memory_count = sum(session.context.user_id in affected_users for session in self._sessions.values())
        self._sessions = {token: session for token, session in self._sessions.items() if session.context.user_id not in affected_users}
        if self._storage_path:
            with self._connect() as connection:
                if except_user_id is None:
                    count = connection.execute("select count(*) from access_sessions where organization_id = ?", (organization_id,)).fetchone()[0]
                    connection.execute("delete from access_sessions where organization_id = ?", (organization_id,))
                else:
                    count = connection.execute("select count(*) from access_sessions where organization_id = ? and user_id != ?", (organization_id, except_user_id)).fetchone()[0]
                    connection.execute("delete from access_sessions where organization_id = ? and user_id != ?", (organization_id, except_user_id))
                return count
        return in_memory_count

    def _user_for_id(self, user_id: str) -> UserRecord | None:
        return next((user for user in self._users.values() if user.user_id == user_id), None)

    @staticmethod
    def _serialize_expiry(expires_at: datetime | None) -> str | None:
        return expires_at.astimezone(timezone.utc).isoformat() if expires_at else None

    @staticmethod
    def _parse_expiry(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    @staticmethod
    def _is_active(user: UserRecord) -> bool:
        return user.enabled and (user.expires_at is None or user.expires_at > datetime.now(timezone.utc))

    @staticmethod
    def require_organization(session: SessionContext, organization_id: str) -> None:
        if session.organization_id != organization_id:
            raise PermissionError("organization access denied")


class PostgresAuthService(AuthService):
    """Shared identity and session storage for horizontally scaled API instances."""

    def __init__(self, users: dict[str, UserRecord], database_url: str, session_ttl: timedelta | None = None) -> None:
        super().__init__(users, session_ttl=session_ttl)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL identity storage requires psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""create table if not exists platform_users (
                username text primary key, user_id text not null unique, organization_id text not null,
                role text not null, password_hash text not null, enabled boolean not null default true,
                expires_at text, class_id text)""")
            cursor.execute("""create table if not exists access_sessions (
                token_hash text primary key, user_id text not null, organization_id text not null,
                role text not null, expires_at text not null)""")
        for username, user in users.items():
            self._persist_user(username, user)
        self._refresh_users()

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)

    @staticmethod
    def _record(row: tuple[object, ...]) -> UserRecord:
        return UserRecord(str(row[1]), str(row[2]), row[3], str(row[4]), bool(row[5]), AuthService._parse_expiry(row[6]), row[7])

    def _refresh_users(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id from platform_users")
            rows = cursor.fetchall()
        self._users = {str(row[0]): self._record(row) for row in rows}

    def _persist_user(self, username: str, user: UserRecord) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into platform_users (username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict(username) do update set user_id=excluded.user_id, organization_id=excluded.organization_id,
                role=excluded.role, password_hash=excluded.password_hash, enabled=excluded.enabled,
                expires_at=excluded.expires_at, class_id=excluded.class_id""", (username, user.user_id, user.organization_id, user.role, user.password_hash, user.enabled, self._serialize_expiry(user.expires_at), user.class_id))

    def _user_by_username(self, username: str) -> UserRecord | None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id from platform_users where username = %s", (username,))
            row = cursor.fetchone()
        if row is None:
            return None
        user = self._record(row)
        self._users[username] = user
        return user

    def login(self, username: str, password: str) -> SessionContext:
        user = self._user_by_username(username)
        if user is None or not self._is_active(user) or not verify_password(user.password_hash, password):
            raise PermissionError("invalid credentials")
        return SessionContext(user.user_id, user.organization_id, user.role)

    def create_access_session(self, context: SessionContext) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + self._session_ttl
        self._sessions[token] = AccessSession(context=context, expires_at=expires_at)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from access_sessions where expires_at <= %s", (datetime.now(timezone.utc).isoformat(),))
            cursor.execute("insert into access_sessions values (%s, %s, %s, %s, %s)", (self._token_hash(token), context.user_id, context.organization_id, context.role, expires_at.isoformat()))
        return token, expires_at

    def resolve_access_session(self, token: str) -> SessionContext:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select user_id, organization_id, role, expires_at from access_sessions where token_hash = %s", (self._token_hash(token),))
            row = cursor.fetchone()
        session = AccessSession(SessionContext(str(row[0]), str(row[1]), row[2]), datetime.fromisoformat(row[3])) if row else None
        user = self._user_for_id(session.context.user_id) if session else None
        if session is None or session.expires_at <= datetime.now(timezone.utc) or user is None or not self._is_active(user):
            self.revoke_access_session(token)
            raise PermissionError("authentication required")
        return session.context

    def _user_for_id(self, user_id: str) -> UserRecord | None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select username, user_id, organization_id, role, password_hash, enabled, expires_at, class_id from platform_users where user_id = %s", (user_id,))
            row = cursor.fetchone()
        return self._record(row) if row else None

    def revoke_access_session(self, token: str) -> None:
        self._sessions.pop(token, None)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from access_sessions where token_hash = %s", (self._token_hash(token),))

    def revoke_user_sessions(self, user_id: str) -> None:
        self._sessions = {token: session for token, session in self._sessions.items() if session.context.user_id != user_id}
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from access_sessions where user_id = %s", (user_id,))

    def revoke_organization_sessions(self, organization_id: str, *, except_user_id: str | None = None) -> int:
        self._refresh_users()
        affected_users = {user.user_id for user in self._users.values() if user.organization_id == organization_id and user.user_id != except_user_id}
        self._sessions = {token: session for token, session in self._sessions.items() if session.context.user_id not in affected_users}
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            if except_user_id is None:
                cursor.execute("select count(*) from access_sessions where organization_id = %s", (organization_id,))
                count = cursor.fetchone()[0]
                cursor.execute("delete from access_sessions where organization_id = %s", (organization_id,))
            else:
                cursor.execute("select count(*) from access_sessions where organization_id = %s and user_id != %s", (organization_id, except_user_id))
                count = cursor.fetchone()[0]
                cursor.execute("delete from access_sessions where organization_id = %s and user_id != %s", (organization_id, except_user_id))
        return count

    def users_for_organization(self, *args, **kwargs):
        self._refresh_users()
        return super().users_for_organization(*args, **kwargs)

    def has_platform_admin(self) -> bool:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select 1 from platform_users where role = %s", ("platform_admin",))
            return cursor.fetchone() is not None
