# server.py
from fastapi import FastAPI
from app.api.routes import router as api_router
from app.api.dome import router as dome_router
from app.api.shutter import router as shutter_router
from app.api.FAKEtelescope import router as telescope_router
# from app.api.telescope import router as telescope_router
from app.api.system import router as system_router
from app.api.telescope import lifespan


app = FastAPI(
    title="Tejas Thesis Backend",
    version="0.1.0",
    description="Backend server for real-time telescope and dome telemetry",
    docs_url="/docs",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api")
app.include_router(dome_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(shutter_router, prefix="/api")
app.include_router(telescope_router, prefix="/api")

