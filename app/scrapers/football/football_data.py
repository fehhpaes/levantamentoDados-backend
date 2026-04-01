from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..base import BaseScraper, ScraperResult
from app.core.config import settings


class FootballDataScraper(BaseScraper):
    """
    Scraper for Football-Data.org API.
    Free tier: 10 requests/minute
    Docs: https://www.football-data.org/documentation/quickstart
    """
    
    BASE_URL = "https://api.football-data.org/v4"
    
    def __init__(self):
        super().__init__()
        self.api_key = settings.FOOTBALL_DATA_API_KEY
        self.headers["X-Auth-Token"] = self.api_key or ""
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from Football-Data.org API."""
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        if isinstance(data, dict):
            # Handle different response structures
            if "matches" in data:
                return data["matches"]
            elif "teams" in data:
                return data["teams"]
            elif "standings" in data:
                return data["standings"]
            elif "competitions" in data:
                return data["competitions"]
        return [data] if data else []
    
    # ========== COMPETITIONS ==========
    
    async def get_competitions(self) -> ScraperResult:
        """Get all available competitions."""
        return await self.scrape("competitions")
    
    async def get_competition(self, competition_id: int) -> ScraperResult:
        """Get competition details."""
        return await self.scrape(f"competitions/{competition_id}")
    
    async def get_competition_standings(self, competition_id: int) -> ScraperResult:
        """Get standings for a competition."""
        return await self.scrape(f"competitions/{competition_id}/standings")
    
    async def get_competition_matches(
        self, 
        competition_id: int,
        matchday: Optional[int] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> ScraperResult:
        """Get matches for a competition."""
        params = {}
        if matchday:
            params["matchday"] = matchday
        if status:
            params["status"] = status
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        
        return await self.scrape(f"competitions/{competition_id}/matches", params)
    
    async def get_competition_teams(self, competition_id: int) -> ScraperResult:
        """Get teams in a competition."""
        return await self.scrape(f"competitions/{competition_id}/teams")
    
    async def get_competition_scorers(
        self, 
        competition_id: int, 
        limit: int = 10
    ) -> ScraperResult:
        """Get top scorers in a competition."""
        return await self.scrape(
            f"competitions/{competition_id}/scorers",
            params={"limit": limit}
        )
    
    # ========== MATCHES ==========
    
    async def get_matches(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ScraperResult:
        """Get matches across all competitions."""
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if status:
            params["status"] = status
        
        return await self.scrape("matches", params)
    
    async def get_match(self, match_id: int) -> ScraperResult:
        """Get match details."""
        return await self.scrape(f"matches/{match_id}")
    
    async def get_match_head_to_head(
        self, 
        match_id: int, 
        limit: int = 10
    ) -> ScraperResult:
        """Get head-to-head data for a match."""
        return await self.scrape(
            f"matches/{match_id}/head2head",
            params={"limit": limit}
        )
    
    async def get_today_matches(self) -> ScraperResult:
        """Get all matches for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return await self.get_matches(date_from=today, date_to=today)
    
    async def get_live_matches(self) -> ScraperResult:
        """Get all live matches."""
        return await self.get_matches(status="LIVE")
    
    # ========== TEAMS ==========
    
    async def get_team(self, team_id: int) -> ScraperResult:
        """Get team details."""
        return await self.scrape(f"teams/{team_id}")
    
    async def get_team_matches(
        self, 
        team_id: int,
        status: Optional[str] = None,
        venue: Optional[str] = None,
        limit: int = 10,
    ) -> ScraperResult:
        """Get matches for a team."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        if venue:
            params["venue"] = venue
        
        return await self.scrape(f"teams/{team_id}/matches", params)
    
    # ========== PLAYERS ==========
    
    async def get_player(self, player_id: int) -> ScraperResult:
        """Get player details."""
        return await self.scrape(f"persons/{player_id}")
    
    async def get_player_matches(
        self, 
        player_id: int,
        limit: int = 10,
    ) -> ScraperResult:
        """Get matches for a player."""
        return await self.scrape(
            f"persons/{player_id}/matches",
            params={"limit": limit}
        )
    
    # ========== DATA TRANSFORMATION ==========
    
    def transform_match(self, match_data: Dict) -> Dict:
        """Transform API match data to our schema."""
        return {
            "external_id": str(match_data.get("id")),
            "league_external_id": str(match_data.get("competition", {}).get("id")),
            "home_team_external_id": str(match_data.get("homeTeam", {}).get("id")),
            "away_team_external_id": str(match_data.get("awayTeam", {}).get("id")),
            "home_team_name": match_data.get("homeTeam", {}).get("name"),
            "away_team_name": match_data.get("awayTeam", {}).get("name"),
            "match_date": match_data.get("utcDate"),
            "status": self._map_status(match_data.get("status")),
            "matchday": match_data.get("matchday"),
            "home_score": match_data.get("score", {}).get("fullTime", {}).get("home"),
            "away_score": match_data.get("score", {}).get("fullTime", {}).get("away"),
            "home_score_ht": match_data.get("score", {}).get("halfTime", {}).get("home"),
            "away_score_ht": match_data.get("score", {}).get("halfTime", {}).get("away"),
            "venue": match_data.get("venue"),
            "referee": match_data.get("referees", [{}])[0].get("name") if match_data.get("referees") else None,
        }
    
    def transform_team(self, team_data: Dict) -> Dict:
        """Transform API team data to our schema."""
        return {
            "external_id": str(team_data.get("id")),
            "name": team_data.get("name"),
            "short_name": team_data.get("shortName") or team_data.get("tla"),
            "logo_url": team_data.get("crest"),
            "country": team_data.get("area", {}).get("name"),
            "founded_year": team_data.get("founded"),
            "venue_name": team_data.get("venue"),
            "website": team_data.get("website"),
        }
    
    def transform_competition(self, comp_data: Dict) -> Dict:
        """Transform API competition data to our schema."""
        return {
            "external_id": str(comp_data.get("id")),
            "name": comp_data.get("name"),
            "country": comp_data.get("area", {}).get("name"),
            "country_code": comp_data.get("area", {}).get("code"),
            "logo_url": comp_data.get("emblem"),
            "season": comp_data.get("currentSeason", {}).get("startDate", "")[:4],
        }
    
    def _map_status(self, api_status: str) -> str:
        """Map API status to our status."""
        status_map = {
            "SCHEDULED": "scheduled",
            "TIMED": "scheduled",
            "IN_PLAY": "live",
            "PAUSED": "halftime",
            "FINISHED": "finished",
            "SUSPENDED": "suspended",
            "POSTPONED": "postponed",
            "CANCELLED": "cancelled",
            "AWARDED": "finished",
        }
        return status_map.get(api_status, "scheduled")
