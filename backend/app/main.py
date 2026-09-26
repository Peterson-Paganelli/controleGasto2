from fastapi import FastAPI

app = FastAPI(title="CGP API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
