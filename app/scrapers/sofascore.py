from typing import Any, Dict, List, Optional
from datetime import datetime
import re
import json
from loguru import logger

from .base import BaseScraper, ScraperResult


class SofaScoreScraper(BaseScraper):
    """
    Scraper for SofaScore.
    Rich data: ratings, heatmaps, xG, detailed stats.
    Note: Uses internal API, may require updates.
    """
    
    BASE_URL = "https://api.sofascore.com/api/v1"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Accept": "application/json",
            "Origin": "https://www.sofascore.com",
            "Referer": "https://www.sofascore.com/",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from SofaScore API."""
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        if isinstance(data, dict):
            if "events" in data:
                return data["events"]
            if "tournaments" in data:
                return data["tournaments"]
        return [data] if data else []
    
    # ========== EVENTS/MATCHES ==========
    
    async def get_live_events(self, sport: str = "football") -> ScraperResult:
        """Get live events."""
        return await self.scrape(f"sport/{sport}/events/live")
    
    async def get_scheduled_events(
        self, 
        sport: str = "football",
        date: Optional[str] = None  # YYYY-MM-DD
    ) -> ScraperResult:
        """Get scheduled events for a date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return await self.scrape(f"sport/{sport}/scheduled-events/{date}")
    
    async def get_event_details(self, event_id: int) -> ScraperResult:
        """Get detailed event information."""
        return await self.scrape(f"event/{event_id}")
    
    async def get_event_statistics(self, event_id: int) -> ScraperResult:
        """Get event statistics."""
        return await self.scrape(f"event/{event_id}/statistics")
    
    async def get_event_lineups(self, event_id: int) -> ScraperResult:
        """Get event lineups with ratings."""
        return await self.scrape(f"event/{event_id}/lineups")
    
    async def get_event_incidents(self, event_id: int) -> ScraperResult:
        """Get event incidents (goals, cards, etc.)."""
        return await self.scrape(f"event/{event_id}/incidents")
    
    async def get_event_graph(self, event_id: int) -> ScraperResult:
        """Get momentum/pressure graph data."""
        return await self.scrape(f"event/{event_id}/graph")
    
    async def get_event_heatmap(
        self, 
        event_id: int, 
        player_id: int
    ) -> ScraperResult:
        """Get player heatmap for an event."""
        return await self.scrape(f"event/{event_id}/player/{player_id}/heatmap")
    
    async def get_event_shotmap(self, event_id: int) -> ScraperResult:
        """Get shot map with xG values."""
        return await self.scrape(f"event/{event_id}/shotmap")
    
    async def get_event_h2h(self, event_id: int) -> ScraperResult:
        """Get head-to-head data."""
        return await self.scrape(f"event/{event_id}/h2h")
    
    async def get_event_odds(self, event_id: int) -> ScraperResult:
        """Get odds for an event."""
        return await self.scrape(f"event/{event_id}/odds/1/all")
    
    # ========== TEAMS ==========
    
    async def get_team(self, team_id: int) -> ScraperResult:
        """Get team details."""
        return await self.scrape(f"team/{team_id}")
    
    async def get_team_events(
        self, 
        team_id: int, 
        page: int = 0,
        upcoming: bool = False
    ) -> ScraperResult:
        """Get team events (past or upcoming)."""
        endpoint = "next" if upcoming else "last"
        return await self.scrape(f"team/{team_id}/events/{endpoint}/{page}")
    
    async def get_team_players(self, team_id: int) -> ScraperResult:
        """Get team players."""
        return await self.scrape(f"team/{team_id}/players")
    
    async def get_team_statistics(
        self, 
        team_id: int, 
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get team statistics for a tournament."""
        return await self.scrape(
            f"team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
        )
    
    # ========== PLAYERS ==========
    
    async def get_player(self, player_id: int) -> ScraperResult:
        """Get player details."""
        return await self.scrape(f"player/{player_id}")
    
    async def get_player_statistics(
        self, 
        player_id: int,
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get player statistics for a tournament."""
        return await self.scrape(
            f"player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics"
        )
    
    async def get_player_transfer_history(self, player_id: int) -> ScraperResult:
        """Get player transfer history."""
        return await self.scrape(f"player/{player_id}/transfer-history")
    
    # ========== TOURNAMENTS ==========
    
    async def get_tournament(self, tournament_id: int) -> ScraperResult:
        """Get tournament details."""
        return await self.scrape(f"unique-tournament/{tournament_id}")
    
    async def get_tournament_standings(
        self, 
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get tournament standings."""
        return await self.scrape(
            f"unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        )
    
    async def get_tournament_top_players(
        self, 
        tournament_id: int,
        season_id: int,
        stat_type: str = "goals"  # goals, assists, rating
    ) -> ScraperResult:
        """Get top players in a tournament."""
        return await self.scrape(
            f"unique-tournament/{tournament_id}/season/{season_id}/top-players/{stat_type}"
        )
    
    # ========== TRANSFORMATIONS ==========
    
    def transform_event(self, data: Dict) -> Dict:
        """Transform SofaScore event to our schema."""
        home_team = data.get("homeTeam", {})
        away_team = data.get("awayTeam", {})
        home_score = data.get("homeScore", {})
        away_score = data.get("awayScore", {})
        
        return {
            "sofascore_id": str(data.get("id")),
            "tournament_id": str(data.get("tournament", {}).get("uniqueTournament", {}).get("id")),
            "tournament_name": data.get("tournament", {}).get("name"),
            "home_team_id": str(home_team.get("id")),
            "home_team_name": home_team.get("name"),
            "away_team_id": str(away_team.get("id")),
            "away_team_name": away_team.get("name"),
            "start_timestamp": data.get("startTimestamp"),
            "status": self._map_status(data.get("status", {}).get("code")),
            "home_score": home_score.get("current"),
            "away_score": away_score.get("current"),
            "home_score_ht": home_score.get("period1"),
            "away_score_ht": away_score.get("period1"),
            "has_xg": data.get("hasXg", False),
        }
    
    def transform_player_rating(self, data: Dict) -> Dict:
        """Transform player rating data."""
        return {
            "player_id": str(data.get("player", {}).get("id")),
            "player_name": data.get("player", {}).get("name"),
            "rating": data.get("statistics", {}).get("rating"),
            "minutes_played": data.get("statistics", {}).get("minutesPlayed"),
            "goals": data.get("statistics", {}).get("goals"),
            "assists": data.get("statistics", {}).get("assists"),
            "shots": data.get("statistics", {}).get("totalShots"),
            "shots_on_target": data.get("statistics", {}).get("shotsOnTarget"),
            "passes": data.get("statistics", {}).get("totalPasses"),
            "pass_accuracy": data.get("statistics", {}).get("accuratePasses"),
            "key_passes": data.get("statistics", {}).get("keyPasses"),
            "dribbles": data.get("statistics", {}).get("successfulDribbles"),
            "tackles": data.get("statistics", {}).get("tackles"),
            "interceptions": data.get("statistics", {}).get("interceptions"),
        }
    
    def _map_status(self, status_code: int) -> str:
        """Map SofaScore status code to our status."""
        status_map = {
            0: "scheduled",
            6: "live",
            7: "live",  # 1st half
            8: "halftime",
            9: "live",  # 2nd half
            11: "live",  # extra time
            12: "live",  # penalties
            100: "finished",
            60: "postponed",
            70: "cancelled",
            80: "suspended",
        }
        return status_map.get(status_code, "scheduled")
