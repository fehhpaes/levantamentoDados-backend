from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

from ..base import BaseScraper, ScraperResult
from app.core.config import settings


class APISportsScraper(BaseScraper):
    """
    Scraper for API-Sports.io
    Covers 15+ sports with detailed data.
    Free tier: 100 requests/day
    Docs: https://api-sports.io/documentation
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    
    # Sport-specific base URLs
    SPORT_URLS = {
        "football": "https://v3.football.api-sports.io",
        "basketball": "https://v1.basketball.api-sports.io",
        "baseball": "https://v1.baseball.api-sports.io",
        "hockey": "https://v1.hockey.api-sports.io",
        "rugby": "https://v1.rugby.api-sports.io",
        "handball": "https://v1.handball.api-sports.io",
        "volleyball": "https://v1.volleyball.api-sports.io",
        "afl": "https://v1.afl.api-sports.io",
        "nfl": "https://v1.american-football.api-sports.io",
        "mma": "https://v1.mma.api-sports.io",
        "formula1": "https://v1.formula-1.api-sports.io",
    }
    
    def __init__(self, sport: str = "football"):
        super().__init__()
        self.api_key = settings.API_SPORTS_KEY
        self.sport = sport
        self.base_url = self.SPORT_URLS.get(sport, self.BASE_URL)
        self.headers.update({
            "x-apisports-key": self.api_key or "",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from API-Sports."""
        url = f"{self.base_url}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        if isinstance(data, dict) and "response" in data:
            return data["response"]
        return [data] if data else []
    
    # ========== FIXTURES/MATCHES ==========
    
    async def get_fixtures(
        self,
        league: Optional[int] = None,
        season: Optional[int] = None,
        team: Optional[int] = None,
        date: Optional[str] = None,
        live: bool = False,
        next_n: Optional[int] = None,
        last_n: Optional[int] = None,
    ) -> ScraperResult:
        """Get fixtures/matches."""
        params = {}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        if team:
            params["team"] = team
        if date:
            params["date"] = date
        if live:
            params["live"] = "all"
        if next_n:
            params["next"] = next_n
        if last_n:
            params["last"] = last_n
        
        return await self.scrape("fixtures", params)
    
    async def get_fixture_by_id(self, fixture_id: int) -> ScraperResult:
        """Get single fixture details."""
        return await self.scrape("fixtures", {"id": fixture_id})
    
    async def get_fixture_statistics(self, fixture_id: int) -> ScraperResult:
        """Get match statistics."""
        return await self.scrape("fixtures/statistics", {"fixture": fixture_id})
    
    async def get_fixture_events(self, fixture_id: int) -> ScraperResult:
        """Get match events (goals, cards, etc.)."""
        return await self.scrape("fixtures/events", {"fixture": fixture_id})
    
    async def get_fixture_lineups(self, fixture_id: int) -> ScraperResult:
        """Get match lineups."""
        return await self.scrape("fixtures/lineups", {"fixture": fixture_id})
    
    async def get_fixture_players(self, fixture_id: int) -> ScraperResult:
        """Get player statistics for a match."""
        return await self.scrape("fixtures/players", {"fixture": fixture_id})
    
    async def get_head_to_head(
        self, 
        team1: int, 
        team2: int, 
        last_n: int = 10
    ) -> ScraperResult:
        """Get head-to-head matches."""
        return await self.scrape("fixtures/headtohead", {
            "h2h": f"{team1}-{team2}",
            "last": last_n
        })
    
    # ========== LEAGUES ==========
    
    async def get_leagues(
        self,
        country: Optional[str] = None,
        season: Optional[int] = None,
        current: bool = True,
    ) -> ScraperResult:
        """Get leagues/competitions."""
        params = {}
        if country:
            params["country"] = country
        if season:
            params["season"] = season
        if current:
            params["current"] = "true"
        
        return await self.scrape("leagues", params)
    
    async def get_league_standings(
        self, 
        league: int, 
        season: int
    ) -> ScraperResult:
        """Get league standings."""
        return await self.scrape("standings", {
            "league": league,
            "season": season
        })
    
    # ========== TEAMS ==========
    
    async def get_teams(
        self,
        league: Optional[int] = None,
        season: Optional[int] = None,
        country: Optional[str] = None,
        search: Optional[str] = None,
    ) -> ScraperResult:
        """Get teams."""
        params = {}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        if country:
            params["country"] = country
        if search:
            params["search"] = search
        
        return await self.scrape("teams", params)
    
    async def get_team_statistics(
        self, 
        team: int, 
        league: int, 
        season: int
    ) -> ScraperResult:
        """Get team statistics for a season."""
        return await self.scrape("teams/statistics", {
            "team": team,
            "league": league,
            "season": season
        })
    
    # ========== PLAYERS ==========
    
    async def get_players(
        self,
        team: Optional[int] = None,
        league: Optional[int] = None,
        season: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
    ) -> ScraperResult:
        """Get players."""
        params = {"page": page}
        if team:
            params["team"] = team
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        if search:
            params["search"] = search
        
        return await self.scrape("players", params)
    
    async def get_top_scorers(self, league: int, season: int) -> ScraperResult:
        """Get top scorers."""
        return await self.scrape("players/topscorers", {
            "league": league,
            "season": season
        })
    
    async def get_top_assists(self, league: int, season: int) -> ScraperResult:
        """Get top assists."""
        return await self.scrape("players/topassists", {
            "league": league,
            "season": season
        })
    
    # ========== PREDICTIONS ==========
    
    async def get_predictions(self, fixture_id: int) -> ScraperResult:
        """Get AI predictions for a fixture."""
        return await self.scrape("predictions", {"fixture": fixture_id})
    
    # ========== ODDS ==========
    
    async def get_odds(
        self,
        fixture: Optional[int] = None,
        league: Optional[int] = None,
        season: Optional[int] = None,
        bookmaker: Optional[int] = None,
    ) -> ScraperResult:
        """Get odds."""
        params = {}
        if fixture:
            params["fixture"] = fixture
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        if bookmaker:
            params["bookmaker"] = bookmaker
        
        return await self.scrape("odds", params)
    
    async def get_bookmakers(self) -> ScraperResult:
        """Get available bookmakers."""
        return await self.scrape("odds/bookmakers")
    
    # ========== TRANSFORMATIONS ==========
    
    def transform_fixture(self, data: Dict) -> Dict:
        """Transform API fixture to our schema."""
        fixture = data.get("fixture", {})
        league = data.get("league", {})
        teams = data.get("teams", {})
        goals = data.get("goals", {})
        score = data.get("score", {})
        
        return {
            "external_id": str(fixture.get("id")),
            "league_external_id": str(league.get("id")),
            "league_name": league.get("name"),
            "home_team_external_id": str(teams.get("home", {}).get("id")),
            "home_team_name": teams.get("home", {}).get("name"),
            "home_team_logo": teams.get("home", {}).get("logo"),
            "away_team_external_id": str(teams.get("away", {}).get("id")),
            "away_team_name": teams.get("away", {}).get("name"),
            "away_team_logo": teams.get("away", {}).get("logo"),
            "match_date": fixture.get("date"),
            "timestamp": fixture.get("timestamp"),
            "venue": fixture.get("venue", {}).get("name"),
            "referee": fixture.get("referee"),
            "status": self._map_status(fixture.get("status", {}).get("short")),
            "elapsed": fixture.get("status", {}).get("elapsed"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "home_score_ht": score.get("halftime", {}).get("home"),
            "away_score_ht": score.get("halftime", {}).get("away"),
        }
    
    def _map_status(self, status_code: str) -> str:
        """Map API status to our status."""
        status_map = {
            "NS": "scheduled",
            "1H": "live",
            "HT": "halftime",
            "2H": "live",
            "ET": "live",
            "P": "live",
            "FT": "finished",
            "AET": "finished",
            "PEN": "finished",
            "PST": "postponed",
            "CANC": "cancelled",
            "ABD": "suspended",
            "AWD": "finished",
            "WO": "finished",
        }
        return status_map.get(status_code, "scheduled")
