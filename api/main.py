"""
FastAPI — API для Mini App, вебхуки YooKassa.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import orders, stats, payments, crm

app = FastAPI(title="Freelance Radar API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(orders.router)
app.include_router(stats.router)
app.include_router(payments.router)
app.include_router(crm.router)


@app.get("/")
async def root():
    return {"name": "Freelance Radar API", "version": "2.0", "status": "ok"}
