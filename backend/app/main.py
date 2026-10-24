from fastapi import FastAPI

from app.games.fruit_ninja.router import router as fruit_ninja_router

app = FastAPI(title="Taggle API", version="0.1.0")

app.include_router(fruit_ninja_router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
