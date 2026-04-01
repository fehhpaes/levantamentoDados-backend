from typing import Any, Dict, List, Optional
from datetime import datetime
import re
from loguru import logger

from ..base import BaseScraper, ScraperResult


class FlashScoreScraper(BaseScraper):
    """
    Scraper for FlashScore website.
    Uses their internal API endpoints.
    Note: This is for educational purposes. Respect robots.txt and ToS.
    """
    
    BASE_URL = "https://www.flashscore.com"
    API_URL = "https://d.flashscore.com/x/feed"
    
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Referer": self.BASE_URL,
            "X-Fsign": "SW9D1eZo",  # This may need to be updated
        })
    
    async def scrape(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> ScraperResult:
        """Scrape data from FlashScore."""
        url = f"{self.API_URL}/{endpoint}"
        result = await self._make_request(url, params=params)
        await self._respect_rate_limit()
        return result
    
    async def parse(self, data: Any) -> List[Dict]:
        """Parse FlashScore response format."""
        if not isinstance(data, str):
            return []
        
        # FlashScore uses a custom delimited format
        # This is a simplified parser
        matches = []
        lines = data.split("~")
        
        current_match = {}
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.split("¬")
            for part in parts:
                if "÷" in part:
                    key, value = part.split("÷", 1)
                    current_match[key] = value
            
            if current_match.get("AA"):  # Match ID indicator
                matches.append(current_match.copy())
                current_match = {}
        
        return matches
    
    async def get_live_matches(self) -> ScraperResult:
        """Get all live matches."""
        return await self.scrape("live")
    
    async def get_matches_by_date(self, date: str) -> ScraperResult:
        """Get matches for a specific date (format: YYYYMMDD)."""
        return await self.scrape(f"d_{date}")
    
    async def get_match_details(self, match_id: str) -> ScraperResult:
        """Get detailed match information."""
        return await self.scrape(f"dc_{match_id}")
    
    async def get_match_statistics(self, match_id: str) -> ScraperResult:
        """Get match statistics."""
        return await self.scrape(f"st_{match_id}")
    
    async def get_match_lineups(self, match_id: str) -> ScraperResult:
        """Get match lineups."""
        return await self.scrape(f"lu_{match_id}")
    
    async def get_match_h2h(self, match_id: str) -> ScraperResult:
        """Get head-to-head data."""
        return await self.scrape(f"hh_{match_id}")
    
    async def get_match_odds(self, match_id: str) -> ScraperResult:
        """Get match odds."""
        return await self.scrape(f"o2_{match_id}")
    
    def transform_match(self, match_data: Dict) -> Dict:
        """Transform FlashScore match data to our schema."""
        # FlashScore key mappings (simplified)
        # AA = Match ID
        # AD = Unix timestamp
        # AE = Home team name
        # AF = Away team name
        # AG = Home score
        # AH = Away score
        
        match_date = None
        if match_data.get("AD"):
            try:
                match_date = datetime.fromtimestamp(int(match_data["AD"]))
            except:
                pass
        
        return {
            "flashscore_id": match_data.get("AA"),
            "home_team_name": match_data.get("AE"),
            "away_team_name": match_data.get("AF"),
            "home_score": int(match_data.get("AG", 0)) if match_data.get("AG") else None,
            "away_score": int(match_data.get("AH", 0)) if match_data.get("AH") else None,
            "match_date": match_date,
            "status": self._parse_status(match_data.get("AB", "")),
        }
    
    def _parse_status(self, status_code: str) -> str:
        """Parse FlashScore status code."""
        status_map = {
            "1": "scheduled",
            "2": "live",
            "3": "finished",
            "4": "postponed",
            "5": "cancelled",
        }
        return status_map.get(status_code, "scheduled")
