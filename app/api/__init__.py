from fastapi import APIRouter
from .endpoints import auth

api_router = APIRouter()

# Auth endpoints (converted to MongoDB)
api_router.include_router(auth.router, tags=["Authentication"])

# Health check endpoint
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running with MongoDB"}


# Stub endpoints for disabled routes (prevent 404 errors on dashboard)

@api_router.get("/analytics/dashboard/summary")
async def dashboard_summary():
    return {
        "total_predictions": 0,
        "accuracy": 0,
        "roi": 0,
        "profit": 0,
        "active_bets": 0,
        "won_bets": 0,
        "lost_bets": 0,
        "pending_bets": 0,
    }

@api_router.get("/matches/today")
async def today_matches():
    return []

@api_router.get("/matches/live")
async def live_matches():
    return []

@api_router.get("/predictions/value-bets")
async def value_bets(min_confidence: int = 60, min_edge: int = 5):
    return []

@api_router.get("/sports/")
async def list_sports():
    return []

@api_router.get("/sports/leagues/")
async def list_leagues(sport_id: int = None):
    return []

@api_router.get("/sports/teams/")
async def list_teams(league_id: int = None, search: str = None):
    return []

@api_router.get("/matches/")
async def list_matches(league_id: int = None, team_id: int = None, status: str = None, date_from: str = None, date_to: str = None):
    return []

@api_router.get("/matches/{match_id}")
async def get_match(match_id: int):
    return None

@api_router.get("/odds/match/{match_id}")
async def get_match_odds(match_id: int, market_type: str = None):
    return []

@api_router.get("/odds/match/{match_id}/comparison")
async def odds_comparison(match_id: int, market_type: str = None):
    return []

@api_router.get("/odds/value-bets")
async def get_value_bets(min_edge: int = None):
    return []

@api_router.get("/predictions/match/{match_id}")
async def match_predictions(match_id: int):
    return None

@api_router.get("/predictions/models/performance")
async def model_performance():
    return []

@api_router.get("/analytics/team/{team_id}/stats")
async def team_stats(team_id: int, last_n_matches: int = None):
    return None

@api_router.get("/analytics/league/{league_id}/standings")
async def league_standings(league_id: int):
    return []

@api_router.get("/analytics/league/{league_id}/top-scorers")
async def top_scorers(league_id: int, limit: int = None):
    return []

@api_router.get("/analytics/odds/market-analysis")
async def market_analysis(league_id: int = None, days: int = None):
    return None

@api_router.get("/settings/")
async def get_settings():
    return {}

@api_router.put("/settings/")
async def update_settings(settings: dict):
    return {"message": "Settings updated"}

@api_router.get("/settings/notifications")
async def get_notification_settings():
    return {}

@api_router.put("/settings/notifications")
async def update_notification_settings(settings: dict):
    return {"message": "Notification settings updated"}

@api_router.get("/backtesting/strategies")
async def list_strategies():
    return []

@api_router.get("/backtesting/strategies/{strategy_id}")
async def get_strategy(strategy_id: int):
    return None

@api_router.post("/backtesting/strategies")
async def create_strategy(strategy: dict):
    return {"message": "Strategy created"}

@api_router.patch("/backtesting/strategies/{strategy_id}")
async def update_strategy(strategy_id: int, strategy: dict):
    return {"message": "Strategy updated"}

@api_router.delete("/backtesting/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int):
    return {"message": "Strategy deleted"}

@api_router.post("/backtesting/run/{strategy_id}")
async def run_backtest(strategy_id: int, params: dict = None):
    return {"message": "Backtest started"}

@api_router.get("/backtesting/results")
async def backtest_results(strategy_id: int = None):
    return []

@api_router.get("/backtesting/results/{result_id}")
async def get_backtest_result(result_id: int):
    return None

@api_router.post("/backtesting/compare")
async def compare_strategies(strategy_ids: list = None, params: dict = None):
    return []

@api_router.get("/bankroll/")
async def get_bankroll():
    return {"balance": 0, "initial_balance": 0, "profit": 0, "roi": 0}

@api_router.post("/bankroll/initialize")
async def initialize_bankroll(initial_balance: float = None):
    return {"message": "Bankroll initialized"}

@api_router.post("/bankroll/deposit")
async def deposit(amount: float = None, description: str = None):
    return {"message": "Deposit recorded"}

@api_router.post("/bankroll/withdraw")
async def withdraw(amount: float = None, description: str = None):
    return {"message": "Withdrawal recorded"}

@api_router.get("/bankroll/transactions")
async def get_transactions(type: str = None, date_from: str = None, date_to: str = None, limit: int = None):
    return []

@api_router.get("/bankroll/settings")
async def get_bankroll_settings():
    return {}

@api_router.put("/bankroll/settings")
async def update_bankroll_settings(settings: dict):
    return {"message": "Settings updated"}

@api_router.post("/bankroll/calculate-stake")
async def calculate_stake(odds: float = None, confidence: float = None):
    return {"stake": 0}

@api_router.get("/bankroll/stats")
async def bankroll_stats(period: str = None):
    return {"balance": 0, "profit": 0, "roi": 0}

@api_router.post("/export/")
async def export_data(config: dict):
    return {"message": "Export started"}

@api_router.get("/export/jobs")
async def export_jobs():
    return []

@api_router.get("/export/jobs/{job_id}")
async def get_export_job(job_id: str):
    return None

@api_router.get("/export/download/{job_id}")
async def download_export(job_id: str):
    return None

@api_router.get("/export/formats")
async def export_formats():
    return ["csv", "json", "xlsx"]

@api_router.get("/notifications/")
async def list_notifications(page: int = None, page_size: int = None, notification_type: str = None, channel: str = None, status: str = None, unread_only: bool = None):
    return []

@api_router.get("/notifications/{notification_id}")
async def get_notification(notification_id: int):
    return None

@api_router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: int):
    return {"message": "Marked as read"}

@api_router.post("/notifications/mark-all-read")
async def mark_all_read():
    return {"message": "All marked as read"}

@api_router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: int):
    return {"message": "Deleted"}

@api_router.delete("/notifications/")
async def delete_all(older_than_days: int = None):
    return {"message": "Deleted"}

@api_router.get("/notifications/stats")
async def notification_stats():
    return {"total": 0, "unread": 0}

@api_router.get("/notifications/preferences")
async def get_notification_preferences():
    return {}

@api_router.put("/notifications/preferences")
async def update_notification_preferences(preferences: dict):
    return {"message": "Preferences updated"}

@api_router.post("/notifications/preferences/reset")
async def reset_notification_preferences():
    return {"message": "Preferences reset"}

@api_router.post("/notifications/telegram/link")
async def link_telegram():
    return {"message": "Telegram link initiated"}

@api_router.delete("/notifications/telegram/unlink")
async def unlink_telegram():
    return {"message": "Telegram unlinked"}


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
