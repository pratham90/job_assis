from fastapi import FastAPI
from app.routers import recommendations
from app.core.db import db
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Job Recommender API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Add startup event
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Job Recommender API...")
    logger.info("📊 Database connections initialized")
    
    # Create unique indexes to prevent duplicate job actions
    try:
        await db.ensure_indexes()
        logger.info("✅ Database indexes ensured")
    except Exception as e:
        logger.warning(f"⚠️  Index creation warning: {e}")
    
    logger.info("🔗 API endpoints registered")
    logger.info("✨ Job Recommender API is ready!")

@app.get("/")
async def root():
    return {"message": "Welcome to the Job Recommender API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/debug")
async def debug_info():
    """Debug endpoint to check API status and database connections"""
    try:
        # Test database connections
        mongo_status = "connected" if db.mongo_client else "disconnected"
        redis_status = "connected" if db.redis_client else "disconnected"
        
        return {
            "api_status": "running",
            "mongodb_status": mongo_status,
            "redis_status": redis_status,
            "endpoints": [
                "/",
                "/health", 
                "/debug",
                "/api/recommend/{clerk_id}",
                "/api/recommend/create-user",
                "/api/recommend/swipe"
            ]
        }
    except Exception as e:
        return {"error": str(e), "api_status": "error"}

app.include_router(
    recommendations.router,
    prefix="/api/recommend",
    tags=["recommendations"]
)

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", 3000))  # Use PORT from environment, default to 3000 if unset
    uvicorn.run(app, host="0.0.0.0", port=port) ##Test 