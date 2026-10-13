from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException

from app.database import connect, migrate


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    yield


app = FastAPI(title="CGP API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error
    return {"status": "ok"}
