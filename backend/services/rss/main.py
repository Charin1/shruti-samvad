from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from core.database.session import init_db

app = FastAPI(
    title="Shruti Samvad RSS API",
    description="API for RSS feed management and ingestion",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Attempt to initialize DB if not already done
    # Note: Migrations are preferred, but this is a fallback for local dev
    try:
        # await init_db()
        pass
    except Exception as e:
        print(f"Database initialization skipped or failed: {e}")

@app.get("/")
async def root():
    return {"message": "Shruti Samvad RSS API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

from .api import feeds, articles, rules, boards

app.include_router(feeds.router, prefix="/api/feeds", tags=["Feeds"])
app.include_router(articles.router, prefix="/api/articles", tags=["Articles"])
app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(boards.router, prefix="/api/boards", tags=["Boards"])
