import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_alerts, routes_cycle, routes_glaciers, routes_watersheds
from .db import Base, SessionLocal, engine
from .import_glaciers import import_glaciers
from .risk.scheduler import start_scheduler, stop_scheduler
from .seed_data import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed()
    db = SessionLocal()
    try:
        import_glaciers(db)
    except Exception as e:
        logging.getLogger("neonepal.startup").warning("Glacier import failed, continuing without it: %s", e)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NeoNepal Glacial Hazard Early Warning API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Dev convenience: Vite picks the next free port if 5173 is taken.
    # Production should pin this to the deployed frontend origin(s).
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_watersheds.router)
app.include_router(routes_alerts.router)
app.include_router(routes_cycle.router)
app.include_router(routes_glaciers.router)


@app.get("/health")
def health():
    return {"status": "ok"}
