from fastapi import APIRouter
from .endpoints import auth

api_router = APIRouter()

# Auth endpoints (converted to MongoDB)
api_router.include_router(auth.router, tags=["Authentication"])

# Health check endpoint
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running with MongoDB"}


# TEMPORARILY DISABLED - Routes still need MongoDB conversion:
# from .endpoints import (
#     sports,
#     matches,
#     odds,
#     predictions,
#     analytics,
#     ml,
#     backtesting,
#     bankroll,
#     export,
#     webhooks,
#     ws,
#     notifications,
# )

# # Sport data endpoints
# api_router.include_router(sports.router, prefix="/sports", tags=["Sports"])
# api_router.include_router(matches.router, prefix="/matches", tags=["Matches"])
# api_router.include_router(odds.router, prefix="/odds", tags=["Odds"])
# api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
# api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# # ML and advanced features
# api_router.include_router(ml.router, prefix="/ml", tags=["Machine Learning"])
# api_router.include_router(backtesting.router, prefix="/backtesting", tags=["Backtesting"])
# api_router.include_router(bankroll.router, prefix="/bankroll", tags=["Bankroll Management"])
# api_router.include_router(export.router, prefix="/export", tags=["Data Export"])

# # Notifications
# api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# # Webhooks
# api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# # WebSockets
# api_router.include_router(ws.router, tags=["WebSockets"])
