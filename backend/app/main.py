import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as api_router
from app.database import init_db

app = FastAPI(
    title="Ultimate Boun Scraper & Dashboard API",
    description="Backend API services for scraping registration details, managing database records, and tracking quotas.",
    version="1.0.0"
)

# Enable CORS for frontend Vite React app
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes under /api
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def startup_event():
    # Initialize SQLite database schema
    init_db()
    print("[+] Database initialized successfully.")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Ultimate Boun Fullstack Scraper API Service",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    # Bind to port 8000 on all interfaces
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
