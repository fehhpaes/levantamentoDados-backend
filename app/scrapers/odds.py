from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

from .base import BaseScraper, ScraperResult
from app.core.config import settings


class TheOddsAPIScraper(BaseScraper):
    """
    Scraper for The Odds API.
    Free tier: 500 requests/month
    Docs: https://the-odds-api.com/liveapi/guides/v4/
    """
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    # Available sports codes
    SPORTS = {
        "soccer": [
            "soccer_epl",           # English Premier League
            "soccer_spain_la_liga",  # La Liga
            "soccer_germany_bundesliga",  # Bundesliga
            "soccer_italy_serie_a",  # Serie A
            "soccer_france_ligue_one",  # Ligue 1
            "soccer_brazil_campeonato",  # Brasileirao
            "soccer_uefa_champs_league",  # Champions League
        ],
        "basketball": [
            "basketball_nba",
            "basketball_euroleague",
        ],
        "tennis": [
            "tennis_atp_french_open",
            "tennis_wta_french_open",
        ],
        "esports": [
            "esports_lol",
            "esports_csgo",
        ],
    }
    
    def __init__(self):
        super().__init__()
        self.api_key = settings.THE_ODDS_API_KEY
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from The Odds API."""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = self.api_key or ""
        
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        if isinstance(data, list):
            return data
        return [data] if data else []
    
    # ========== SPORTS ==========
    
    async def get_sports(self, all_sports: bool = False) -> ScraperResult:
        """Get all available sports."""
        params = {"all": "true"} if all_sports else {}
        return await self.scrape("sports", params)
    
    # ========== ODDS ==========
    
    async def get_odds(
        self,
        sport: str,
        regions: str = "eu",  # us, uk, eu, au
        markets: str = "h2h",  # h2h, spreads, totals
        odds_format: str = "decimal",  # decimal, american
        bookmakers: Optional[List[str]] = None,
    ) -> ScraperResult:
        """Get odds for a sport."""
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)
        
        return await self.scrape(f"sports/{sport}/odds", params)
    
    async def get_event_odds(
        self,
        sport: str,
        event_id: str,
        regions: str = "eu",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
    ) -> ScraperResult:
        """Get odds for a specific event."""
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        return await self.scrape(f"sports/{sport}/events/{event_id}/odds", params)
    
    # ========== HISTORICAL ODDS ==========
    
    async def get_historical_odds(
        self,
        sport: str,
        date: str,  # ISO format
        regions: str = "eu",
        markets: str = "h2h",
    ) -> ScraperResult:
        """Get historical odds (requires paid plan)."""
        params = {
            "date": date,
            "regions": regions,
            "markets": markets,
        }
        return await self.scrape(f"historical/sports/{sport}/odds", params)
    
    # ========== SCORES ==========
    
    async def get_scores(
        self,
        sport: str,
        days_from: int = 1,  # How many days back
    ) -> ScraperResult:
        """Get scores for a sport."""
        params = {"daysFrom": days_from}
        return await self.scrape(f"sports/{sport}/scores", params)
    
    # ========== DATA TRANSFORMATION ==========
    
    def transform_odds(self, event_data: Dict) -> List[Dict]:
        """Transform API odds data to our schema."""
        transformed = []
        
        event_id = event_data.get("id")
        home_team = event_data.get("home_team")
        away_team = event_data.get("away_team")
        commence_time = event_data.get("commence_time")
        
        for bookmaker in event_data.get("bookmakers", []):
            bookmaker_name = bookmaker.get("key")
            
            for market in bookmaker.get("markets", []):
                market_type = market.get("key")
                outcomes = market.get("outcomes", [])
                
                odds_data = {
                    "event_id": event_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": commence_time,
                    "bookmaker": bookmaker_name,
                    "market_type": market_type,
                    "last_update": bookmaker.get("last_update"),
                }
                
                if market_type == "h2h":
                    # 1X2 / Moneyline
                    for outcome in outcomes:
                        if outcome.get("name") == home_team:
                            odds_data["home_odds"] = outcome.get("price")
                        elif outcome.get("name") == away_team:
                            odds_data["away_odds"] = outcome.get("price")
                        elif outcome.get("name") == "Draw":
                            odds_data["draw_odds"] = outcome.get("price")
                
                elif market_type == "totals":
                    # Over/Under
                    for outcome in outcomes:
                        odds_data["line"] = outcome.get("point")
                        if outcome.get("name") == "Over":
                            odds_data["over_odds"] = outcome.get("price")
                        elif outcome.get("name") == "Under":
                            odds_data["under_odds"] = outcome.get("price")
                
                elif market_type == "spreads":
                    # Handicap/Spread
                    for outcome in outcomes:
                        if outcome.get("name") == home_team:
                            odds_data["home_spread"] = outcome.get("point")
                            odds_data["home_spread_odds"] = outcome.get("price")
                        elif outcome.get("name") == away_team:
                            odds_data["away_spread"] = outcome.get("point")
                            odds_data["away_spread_odds"] = outcome.get("price")
                
                transformed.append(odds_data)
        
        return transformed
    
    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """Calculate implied probability from decimal odds."""
        if decimal_odds <= 0:
            return 0.0
        return 1 / decimal_odds
    
    def calculate_margin(
        self, 
        home_odds: float, 
        draw_odds: Optional[float], 
        away_odds: float
    ) -> float:
        """Calculate bookmaker margin."""
        home_prob = self.calculate_implied_probability(home_odds)
        away_prob = self.calculate_implied_probability(away_odds)
        draw_prob = self.calculate_implied_probability(draw_odds) if draw_odds else 0
        
        total = home_prob + draw_prob + away_prob
        margin = (total - 1) * 100
        return round(margin, 2)
    
    def find_value_bets(
        self,
        bookmaker_odds: List[Dict],
        predicted_probs: Dict[str, float],
        min_edge: float = 0.05,  # 5% minimum edge
    ) -> List[Dict]:
        """Find value bets by comparing predicted vs implied probabilities."""
        value_bets = []
        
        for odds_data in bookmaker_odds:
            for selection in ["home", "draw", "away"]:
                odds_key = f"{selection}_odds"
                prob_key = f"{selection}_prob"
                
                if odds_data.get(odds_key) and predicted_probs.get(prob_key):
                    implied_prob = self.calculate_implied_probability(odds_data[odds_key])
                    predicted_prob = predicted_probs[prob_key]
                    
                    edge = predicted_prob - implied_prob
                    
                    if edge >= min_edge:
                        expected_value = (predicted_prob * odds_data[odds_key]) - 1
                        
                        value_bets.append({
                            "selection": selection,
                            "bookmaker": odds_data.get("bookmaker"),
                            "odds": odds_data[odds_key],
                            "implied_prob": round(implied_prob, 4),
                            "predicted_prob": round(predicted_prob, 4),
                            "edge": round(edge * 100, 2),  # as percentage
                            "expected_value": round(expected_value * 100, 2),  # as percentage
                        })
        
        return sorted(value_bets, key=lambda x: x["edge"], reverse=True)
