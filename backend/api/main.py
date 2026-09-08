"""
Main FastAPI Application
========================
Jalankan dengan: uvicorn backend.api.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router as rate_router

app = FastAPI(
    title="Multi-Carrier Rate Engine",
    description="API untuk kalkulasi rate FedEx & UPS",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rate_router, prefix="/api/rates", tags=["Rates"])

@app.get("/")
def root():
    return {"message": "Multi-Carrier Rate Engine is running."}
