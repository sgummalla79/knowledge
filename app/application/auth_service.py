from uuid import UUID

from app.domain.entities import User
from app.domain.errors import AuthenticationError
from app.domain.ports import UserRepositoryPort
from app.infrastructure.auth.passwords import hash_password, verify_password


class AuthService:
    def __init__(self, repository: UserRepositoryPort):
        self._repository = repository

    def login(self, username: str, password: str) -> User:
        user = self._repository.get()
        # Deliberately the same error for "no such user" and "wrong password" — standard practice,
        # doesn't tell an attacker which half was wrong.
        if user is None or user.username != username or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid username or password.")
        return user

    def change_password(self, user_id: UUID, new_password: str) -> None:
        self._repository.update_password(user_id, hash_password(new_password))
