from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger

from .base import BaseScraper, ScraperResult


class TransfermarktScraper(BaseScraper):
    """
    Scraper for Transfermarkt.
    Provides: player values, transfers, contracts.
    """
    
    BASE_URL = "https://www.transfermarkt.com"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Accept": "text/html,application/json",
            "Referer": "https://www.transfermarkt.com/",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from Transfermarkt."""
        url = f"{self.BASE_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse HTML response - needs BeautifulSoup."""
        return [data] if data else []
    
    # ========== PLAYERS ==========
    
    async def get_player(self, player_id: int, player_name: str) -> ScraperResult:
        """Get player profile."""
        slug = player_name.lower().replace(" ", "-")
        return await self.scrape(f"{slug}/profil/spieler/{player_id}")
    
    async def get_player_market_value(
        self, 
        player_id: int, 
        player_name: str
    ) -> ScraperResult:
        """Get player market value history."""
        slug = player_name.lower().replace(" ", "-")
        return await self.scrape(f"{slug}/marktwertverlauf/spieler/{player_id}")
    
    async def get_player_transfers(
        self, 
        player_id: int, 
        player_name: str
    ) -> ScraperResult:
        """Get player transfer history."""
        slug = player_name.lower().replace(" ", "-")
        return await self.scrape(f"{slug}/transfers/spieler/{player_id}")
    
    # ========== TEAMS ==========
    
    async def get_team(self, team_id: int, team_name: str) -> ScraperResult:
        """Get team profile."""
        slug = team_name.lower().replace(" ", "-")
        return await self.scrape(f"{slug}/startseite/verein/{team_id}")
    
    async def get_team_squad(self, team_id: int, team_name: str) -> ScraperResult:
        """Get team squad with market values."""
        slug = team_name.lower().replace(" ", "-")
        return await self.scrape(f"{slug}/kader/verein/{team_id}")
    
    async def get_team_transfers(
        self, 
        team_id: int, 
        team_name: str,
        season: Optional[str] = None
    ) -> ScraperResult:
        """Get team transfers."""
        slug = team_name.lower().replace(" ", "-")
        endpoint = f"{slug}/transfers/verein/{team_id}"
        if season:
            endpoint += f"/saison_id/{season}"
        return await self.scrape(endpoint)
    
    # ========== MARKET VALUES ==========
    
    async def get_most_valuable_players(
        self, 
        position: Optional[str] = None
    ) -> ScraperResult:
        """Get most valuable players."""
        endpoint = "spieler-statistik/wertvollstespieler/marktwertetop"
        params = {}
        if position:
            params["pos"] = position
        return await self.scrape(endpoint, params)
    
    async def get_league_market_values(self, league_id: int) -> ScraperResult:
        """Get market values for a league."""
        return await self.scrape(f"wettbewerb/marktwerte/wettbewerb/{league_id}")
    
    # ========== TRANSFERS ==========
    
    async def get_latest_transfers(self, top: int = 25) -> ScraperResult:
        """Get latest transfers."""
        return await self.scrape("transfers/transferticker", {"top": top})
    
    async def get_transfer_records(self) -> ScraperResult:
        """Get transfer records."""
        return await self.scrape("transferrekorde/statistik/top-transferrekorde")
    
    async def get_rumours(self) -> ScraperResult:
        """Get transfer rumours."""
        return await self.scrape("transfergeruechte/detail/aktuelle-geruechte")


class WhoScoredScraper(BaseScraper):
    """
    Scraper for WhoScored.com
    Provides: advanced stats, ratings, heatmaps, pass maps.
    """
    
    BASE_URL = "https://www.whoscored.com"
    API_URL = "https://1.www.whoscored.com"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Accept": "application/json",
            "Referer": "https://www.whoscored.com/",
            "Model-Last-Mode": "g",
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from WhoScored."""
        url = f"{self.API_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        return [data] if data else []
    
    # ========== MATCHES ==========
    
    async def get_match(self, match_id: int) -> ScraperResult:
        """Get match details."""
        return await self.scrape(f"Matches/{match_id}/Live")
    
    async def get_match_centre(self, match_id: int) -> ScraperResult:
        """Get match centre data (full stats)."""
        return await self.scrape(f"Matches/{match_id}/MatchCentre")
    
    async def get_match_preview(self, match_id: int) -> ScraperResult:
        """Get match preview with predictions."""
        return await self.scrape(f"Matches/{match_id}/Preview")
    
    # ========== TEAMS ==========
    
    async def get_team_statistics(
        self, 
        team_id: int,
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get team statistics."""
        return await self.scrape(
            f"StatisticsFeed/1/GetTeamStatistics",
            {
                "teamId": team_id,
                "tournamentId": tournament_id,
                "seasonId": season_id,
            }
        )
    
    async def get_team_fixtures(self, team_id: int) -> ScraperResult:
        """Get team fixtures."""
        return await self.scrape(f"Teams/{team_id}/Fixtures")
    
    # ========== PLAYERS ==========
    
    async def get_player_statistics(
        self, 
        player_id: int,
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get player statistics."""
        return await self.scrape(
            f"StatisticsFeed/1/GetPlayerStatistics",
            {
                "playerId": player_id,
                "tournamentId": tournament_id,
                "seasonId": season_id,
            }
        )
    
    async def get_player_heatmap(
        self, 
        player_id: int,
        match_id: int
    ) -> ScraperResult:
        """Get player heatmap for a match."""
        return await self.scrape(
            f"StatisticsFeed/1/GetPlayerHeatmap",
            {"playerId": player_id, "matchId": match_id}
        )
    
    # ========== TOURNAMENTS ==========
    
    async def get_tournament_standings(
        self, 
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get tournament standings."""
        return await self.scrape(
            f"Regions/252/Tournaments/{tournament_id}/Seasons/{season_id}/Stages"
        )
    
    async def get_tournament_fixtures(
        self, 
        tournament_id: int,
        season_id: int
    ) -> ScraperResult:
        """Get tournament fixtures."""
        return await self.scrape(
            f"tournamentsfeed/1/GetTournamentFixtures",
            {"tournamentId": tournament_id, "seasonId": season_id}
        )
    
    async def get_top_players(
        self, 
        tournament_id: int,
        season_id: int,
        category: str = "Rating"  # Rating, Goals, Assists, etc.
    ) -> ScraperResult:
        """Get top players by category."""
        return await self.scrape(
            f"StatisticsFeed/1/GetPlayerStatistics",
            {
                "tournamentId": tournament_id,
                "seasonId": season_id,
                "category": category,
                "subcategory": "Summary",
                "field": "Overall",
            }
        )


class BetfairExchangeScraper(BaseScraper):
    """
    Scraper for Betfair Exchange.
    Provides: exchange odds, volume, liquidity.
    Requires Betfair API credentials.
    """
    
    LOGIN_URL = "https://identitysso.betfair.com/api/login"
    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0"
    
    def __init__(self, app_key: str = None, username: str = None, password: str = None):
        super().__init__()
        self.app_key = app_key or ""
        self.username = username or ""
        self.password = password or ""
        self.session_token = None
    
    async def login(self) -> bool:
        """Login to Betfair and get session token."""
        result = await self._make_request(
            self.LOGIN_URL,
            method="POST",
            headers={
                "X-Application": self.app_key,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            params={
                "username": self.username,
                "password": self.password,
            }
        )
        
        if result.success and result.data:
            self.session_token = result.data.get("token")
            self.headers.update({
                "X-Application": self.app_key,
                "X-Authentication": self.session_token,
            })
            return True
        return False
    
    async def scrape(
        self, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> ScraperResult:
        """Make API request."""
        if not self.session_token:
            await self.login()
        
        url = f"{self.BASE_URL}/{endpoint}/"
        result = await self._make_request(
            url, 
            method="POST",
            json_data=data or {}
        )
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse API response."""
        return data if isinstance(data, list) else [data] if data else []
    
    # ========== MARKETS ==========
    
    async def list_event_types(self) -> ScraperResult:
        """List all event types (sports)."""
        return await self.scrape("listEventTypes", {
            "filter": {}
        })
    
    async def list_competitions(self, event_type_id: int = 1) -> ScraperResult:
        """List competitions for a sport."""
        return await self.scrape("listCompetitions", {
            "filter": {"eventTypeIds": [event_type_id]}
        })
    
    async def list_events(
        self, 
        competition_ids: List[int] = None,
        event_type_ids: List[int] = None,
    ) -> ScraperResult:
        """List events."""
        filter_data = {}
        if competition_ids:
            filter_data["competitionIds"] = competition_ids
        if event_type_ids:
            filter_data["eventTypeIds"] = event_type_ids
        
        return await self.scrape("listEvents", {"filter": filter_data})
    
    async def list_market_catalogue(
        self,
        event_ids: List[str] = None,
        market_types: List[str] = None,
        max_results: int = 100,
    ) -> ScraperResult:
        """List market catalogue."""
        filter_data = {}
        if event_ids:
            filter_data["eventIds"] = event_ids
        if market_types:
            filter_data["marketTypeCodes"] = market_types
        
        return await self.scrape("listMarketCatalogue", {
            "filter": filter_data,
            "maxResults": max_results,
            "marketProjection": [
                "COMPETITION", "EVENT", "EVENT_TYPE", 
                "MARKET_START_TIME", "RUNNER_DESCRIPTION"
            ]
        })
    
    async def list_market_book(
        self,
        market_ids: List[str],
        price_projection: Dict = None,
    ) -> ScraperResult:
        """Get market prices and volume."""
        return await self.scrape("listMarketBook", {
            "marketIds": market_ids,
            "priceProjection": price_projection or {
                "priceData": ["EX_BEST_OFFERS", "EX_TRADED"],
                "virtualise": True,
            }
        })
    
    # ========== TRANSFORMATIONS ==========
    
    def transform_market_odds(self, market_data: Dict) -> Dict:
        """Transform Betfair market data to our schema."""
        runners = market_data.get("runners", [])
        
        return {
            "market_id": market_data.get("marketId"),
            "status": market_data.get("status"),
            "total_matched": market_data.get("totalMatched"),
            "total_available": market_data.get("totalAvailable"),
            "runners": [
                {
                    "selection_id": r.get("selectionId"),
                    "status": r.get("status"),
                    "last_price_traded": r.get("lastPriceTraded"),
                    "total_matched": r.get("totalMatched"),
                    "back_prices": [
                        {"price": p.get("price"), "size": p.get("size")}
                        for p in r.get("ex", {}).get("availableToBack", [])
                    ],
                    "lay_prices": [
                        {"price": p.get("price"), "size": p.get("size")}
                        for p in r.get("ex", {}).get("availableToLay", [])
                    ],
                }
                for r in runners
            ]
        }
