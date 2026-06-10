from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import intersections, phases, detectors, timing_plans, arterials, optimization


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="交通信号配时优化系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intersections.router, prefix="/api")
app.include_router(phases.router, prefix="/api")
app.include_router(detectors.router, prefix="/api")
app.include_router(timing_plans.router, prefix="/api")
app.include_router(arterials.router, prefix="/api")
app.include_router(optimization.router, prefix="/api")
