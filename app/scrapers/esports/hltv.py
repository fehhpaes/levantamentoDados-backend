from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

from .base import BaseScraper, ScraperResult


class HLTVScraper(BaseScraper):
    """
    Scraper for HLTV.org (Counter-Strike).
    Provides: rankings, matches, player stats, map stats.
    Note: Uses internal API endpoints.
    """
    
    BASE_URL = "https://www.hltv.org"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Accept": "text/html,application/json",
            "Referer": "https://www.hltv.org/",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from HLTV."""
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse response - HLTV returns HTML, needs parsing."""
        # This would need BeautifulSoup parsing in production
        return [data] if data else []
    
    # ========== MATCHES ==========
    
    async def get_matches(self) -> ScraperResult:
        """Get upcoming and live matches."""
        return await self.scrape("matches")
    
    async def get_match_details(self, match_id: int) -> ScraperResult:
        """Get match details."""
        return await self.scrape(f"matches/{match_id}")
    
    async def get_results(self, offset: int = 0) -> ScraperResult:
        """Get match results."""
        return await self.scrape("results", {"offset": offset})
    
    # ========== RANKINGS ==========
    
    async def get_team_rankings(
        self, 
        date: Optional[str] = None  # YYYY-MM-DD
    ) -> ScraperResult:
        """Get world team rankings."""
        params = {}
        if date:
            params["date"] = date
        return await self.scrape("ranking/teams", params)
    
    async def get_player_rankings(self, year: int = None) -> ScraperResult:
        """Get player rankings."""
        if not year:
            year = datetime.now().year
        return await self.scrape(f"stats/players?startDate={year}-01-01&endDate={year}-12-31")
    
    # ========== TEAMS ==========
    
    async def get_team(self, team_id: int) -> ScraperResult:
        """Get team profile."""
        return await self.scrape(f"team/{team_id}")
    
    async def get_team_stats(
        self, 
        team_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ScraperResult:
        """Get team statistics."""
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self.scrape(f"stats/teams/{team_id}", params)
    
    async def get_team_maps(self, team_id: int) -> ScraperResult:
        """Get team map statistics."""
        return await self.scrape(f"stats/teams/maps/{team_id}")
    
    # ========== PLAYERS ==========
    
    async def get_player(self, player_id: int) -> ScraperResult:
        """Get player profile."""
        return await self.scrape(f"player/{player_id}")
    
    async def get_player_stats(
        self, 
        player_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ScraperResult:
        """Get player statistics."""
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self.scrape(f"stats/players/{player_id}", params)
    
    # ========== EVENTS/TOURNAMENTS ==========
    
    async def get_events(self, event_type: str = "ongoing") -> ScraperResult:
        """Get events (ongoing, upcoming, archive)."""
        return await self.scrape(f"events#{event_type}")
    
    async def get_event_details(self, event_id: int) -> ScraperResult:
        """Get event details."""
        return await self.scrape(f"events/{event_id}")
    
    # ========== TRANSFORMATIONS ==========
    
    def transform_match(self, data: Dict) -> Dict:
        """Transform HLTV match data to our schema."""
        return {
            "hltv_id": str(data.get("id")),
            "event_name": data.get("event", {}).get("name"),
            "team1_id": str(data.get("team1", {}).get("id")),
            "team1_name": data.get("team1", {}).get("name"),
            "team1_rank": data.get("team1", {}).get("rank"),
            "team2_id": str(data.get("team2", {}).get("id")),
            "team2_name": data.get("team2", {}).get("name"),
            "team2_rank": data.get("team2", {}).get("rank"),
            "match_date": data.get("date"),
            "format": data.get("format"),  # Bo1, Bo3, Bo5
            "maps": data.get("maps", []),
            "team1_score": data.get("team1", {}).get("score"),
            "team2_score": data.get("team2", {}).get("score"),
            "status": data.get("status"),
        }
    
    def transform_team_ranking(self, data: Dict) -> Dict:
        """Transform team ranking data."""
        return {
            "team_id": str(data.get("id")),
            "team_name": data.get("name"),
            "rank": data.get("rank"),
            "points": data.get("points"),
            "change": data.get("change"),  # rank change
            "players": data.get("players", []),
        }


class VLRScraper(BaseScraper):
    """
    Scraper for VLR.gg (Valorant).
    Provides: rankings, matches, player stats.
    """
    
    BASE_URL = "https://www.vlr.gg"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Accept": "text/html,application/json",
            "Referer": "https://www.vlr.gg/",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from VLR.gg."""
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse response."""
        return [data] if data else []
    
    async def get_matches(self) -> ScraperResult:
        """Get matches."""
        return await self.scrape("matches")
    
    async def get_results(self) -> ScraperResult:
        """Get results."""
        return await self.scrape("matches/results")
    
    async def get_rankings(self, region: str = "all") -> ScraperResult:
        """Get team rankings."""
        return await self.scrape(f"rankings/{region}")
    
    async def get_team(self, team_id: int) -> ScraperResult:
        """Get team profile."""
        return await self.scrape(f"team/{team_id}")
    
    async def get_player(self, player_id: int) -> ScraperResult:
        """Get player profile."""
        return await self.scrape(f"player/{player_id}")


class LoLEsportsScraper(BaseScraper):
    """
    Scraper for League of Legends Esports.
    Uses official Riot Games API.
    """
    
    BASE_URL = "https://esports-api.lolesports.com/persisted/gw"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z",  # Public key
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from LoL Esports API."""
        params = params or {}
        params["hl"] = "en-US"
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        if isinstance(data, dict) and "data" in data:
            return [data["data"]]
        return [data] if data else []
    
    async def get_leagues(self) -> ScraperResult:
        """Get all leagues (LCK, LEC, LCS, etc.)."""
        return await self.scrape("getLeagues")
    
    async def get_schedule(self, league_id: Optional[str] = None) -> ScraperResult:
        """Get match schedule."""
        params = {}
        if league_id:
            params["leagueId"] = league_id
        return await self.scrape("getSchedule", params)
    
    async def get_live(self) -> ScraperResult:
        """Get live matches."""
        return await self.scrape("getLive")
    
    async def get_standings(self, tournament_id: str) -> ScraperResult:
        """Get tournament standings."""
        return await self.scrape("getStandings", {"tournamentId": tournament_id})
    
    async def get_teams(self) -> ScraperResult:
        """Get all teams."""
        return await self.scrape("getTeams")
    
    async def get_event_details(self, match_id: str) -> ScraperResult:
        """Get match/event details."""
        return await self.scrape("getEventDetails", {"id": match_id})
