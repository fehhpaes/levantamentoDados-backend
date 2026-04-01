from fastapi import APIRouter
from .endpoints import (
    sports,
    matches,
    odds,
    predictions,
    analytics,
    auth,
    ml,
    backtesting,
    bankroll,
    export,
    webhooks,
    ws,
    notifications,
)

api_router = APIRouter()

# Auth endpoints (no prefix, includes /register, /login, /me, etc.)
api_router.include_router(auth.router, tags=["Authentication"])

# Sport data endpoints
api_router.include_router(sports.router, prefix="/sports", tags=["Sports"])
api_router.include_router(matches.router, prefix="/matches", tags=["Matches"])
api_router.include_router(odds.router, prefix="/odds", tags=["Odds"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# ML and advanced features
api_router.include_router(ml.router, prefix="/ml", tags=["Machine Learning"])
api_router.include_router(backtesting.router, prefix="/backtesting", tags=["Backtesting"])
api_router.include_router(bankroll.router, prefix="/bankroll", tags=["Bankroll Management"])
api_router.include_router(export.router, prefix="/export", tags=["Data Export"])

# Notifications
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# Webhooks
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# WebSockets
api_router.include_router(ws.router, tags=["WebSockets"])
