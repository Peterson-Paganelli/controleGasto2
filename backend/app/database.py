import os

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


database_url = URL.create(
    "postgresql+psycopg",
    username=os.getenv("POSTGRES_USER", "cgp"),
    password=os.getenv("POSTGRES_PASSWORD", "cgp_local"),
    host=os.getenv("POSTGRES_HOST", "db"),
    database=os.getenv("POSTGRES_DB", "cgp"),
)

engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)
