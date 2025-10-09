# server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.api.routes import router as api_router
from app.api.observatory import router as observatory_router
from app.api.telescope import router as telescope_router
from app.api.telescope import mount, lifespan
from contextlib import asynccontextmanager
import asyncio
import json
import time
import math

app = FastAPI(
    title="Tejas Thesis Backend",
    version="0.0.1",
    description="Backend server for real-time telescope and dome telemetry",
    docs_url="/docs",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api")
app.include_router(observatory_router, prefix="/api")
app.include_router(telescope_router, prefix="/api")





# app.mount("/static", StaticFiles(directory="static"), name="static")

# clients = set()

# @app.get("/")
# async def index():
#     html = open("static/index.html", "r").read()
#     return HTMLResponse(html)

# @app.websocket("/ws")
# async def websocket_endpoint(ws: WebSocket):
#     await ws.accept()
#     clients.add(ws)
#     try:
#         while True:
#             data = await ws.receive_text()  # you can receive commands from client
#             # echo back or process commands
#             # For now do nothing
#     except WebSocketDisconnect:
#         clients.remove(ws)

# async def broadcast(msg):
#     dead = []
#     for ws in list(clients):
#         try:
#             await ws.send_text(msg)
#         except:
#             dead.append(ws)
#     for d in dead:
#         clients.remove(d)

# # ---- Example real-time loop (replace with real device reads) ----
# async def telemetry_loop():
#     lat = math.radians(-33.917)  # UNSW lat example
#     dome_center = [0.0, 0.0, 0.0]
#     dome_radius = 3.0
#     mount_pos = [0.5, -0.2, 0.0]

#     while True:
#         # Replace the following with your actual mount/dome readings
#         now = time.time()
#         # Example: produce HA/Dec sweeping values
#         ha = math.radians((now * 10) % 360 - 180) # demo
#         dec = math.radians(20 * math.sin(now/60.0))

#         msg = {
#             "timestamp": now,
#             "mount": {"ha_deg": math.degrees(ha), "dec_deg": math.degrees(dec)},
#             "dome": {"az_deg": (now*0.1)%360, "slit_width_deg": 10, "shutter_open": True},
#             "pose": {
#                 "mount_xyz": mount_pos,
#                 "dome_center_xyz": dome_center,
#                 "dome_radius_m": dome_radius,
#                 "lat_deg": math.degrees(lat)
#             }
#         }
#         await broadcast(json.dumps(msg))
#         await asyncio.sleep(0.5)

# # Start background loop
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(telemetry_loop())
