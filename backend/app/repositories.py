from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


password_hasher = PasswordHash.recommended()


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, email: str, password: str) -> User:
        user = User(email=email, password_hash=password_hasher.hash(password))
        self.session.add(user)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))
