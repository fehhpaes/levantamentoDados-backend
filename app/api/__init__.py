from fastapi import APIRouter
from .endpoints import auth, sports, matches, odds, predictions, analytics

api_router = APIRouter()

# Auth endpoints
api_router.include_router(auth.router, tags=["Authentication"])

# Sports data endpoints
api_router.include_router(sports.router, prefix="/sports", tags=["Sports"])
api_router.include_router(matches.router, prefix="/matches", tags=["Matches"])
api_router.include_router(odds.router, prefix="/odds", tags=["Odds"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# Health check endpoint
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running with MongoDB"}
