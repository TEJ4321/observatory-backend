from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

from app.api import routes, telescope, dome, shutter, system
from app.api.telescope import mount, MountError

logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for managing startup and shutdown events.
    Connects to the telescope mount on startup and closes the connection on shutdown.
    """
    logger.info("Application startup: Connecting to telescope mount...")
    try:
        await mount.connect()
        logger.info("Successfully connected to telescope mount.")
    except MountError as e:
        logger.error(f"Failed to connect to mount on startup: {e}")
    yield # Application runs
    logger.info("Application shutdown: Disconnecting from telescope mount...")
    await mount.close()
    logger.info("Telescope mount connection closed.")

app = FastAPI(lifespan=lifespan)

app.include_router(routes.router, prefix="/api")
app.include_router(telescope.router, prefix="/api")
app.include_router(dome.router, prefix="/api")
app.include_router(shutter.router, prefix="/api")
app.include_router(system.router, prefix="/api")