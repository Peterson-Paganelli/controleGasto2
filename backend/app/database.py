import os
from pathlib import Path

import psycopg


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "cgp"),
        user=os.getenv("POSTGRES_USER", "cgp"),
        password=os.getenv("POSTGRES_PASSWORD", "cgp_local"),
        connect_timeout=5,
    )


def migrate() -> None:
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        raise RuntimeError("Nenhuma migration encontrada.")

    with connect() as connection:
        # Serializa a inicialização quando mais de uma API inicia ao mesmo tempo.
        connection.execute("SELECT pg_advisory_xact_lock(20261012, 1)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM public.schema_migrations"
            )
        }
        for migration in migrations:
            if migration.name in applied:
                continue
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)
            connection.execute(
                "INSERT INTO public.schema_migrations (version) VALUES (%s)",
                (migration.name,),
            )


if __name__ == "__main__":
    migrate()
