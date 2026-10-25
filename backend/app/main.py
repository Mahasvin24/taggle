from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.games.fruit_ninja.db import Store
from app.games.fruit_ninja.router import router
from app.games.wavelength.db import Store as WavelengthStore
from app.games.wavelength.router import router as wavelength_router


def create_app(database_path=None, wavelength_database_path=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.fruit_store = Store(database_path)
        app.state.wavelength_store = WavelengthStore(
            wavelength_database_path or database_path
        )
        yield

    app = FastAPI(title="Taggle API", version="0.2.0", lifespan=lifespan)
    app.include_router(router)
    app.include_router(wavelength_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
