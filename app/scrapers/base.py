from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import httpx
import asyncio
from loguru import logger
from app.core.config import settings


@dataclass
class ScraperResult:
    """Result from a scraping operation."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    source: str = ""


class BaseScraper(ABC):
    """Base class for all scrapers."""
    
    def __init__(self):
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.delay = settings.SCRAPING_DELAY
    
    async def _make_request(
        self, 
        url: str, 
        method: str = "GET",
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> ScraperResult:
        """Make an HTTP request with error handling."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers or self.headers,
                    params=params,
                    json=json_data,
                )
                response.raise_for_status()
                
                return ScraperResult(
                    success=True,
                    data=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                    source=url,
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return ScraperResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {str(e)}",
                source=url,
            )
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            return ScraperResult(
                success=False,
                error=str(e),
                source=url,
            )
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return ScraperResult(
                success=False,
                error=str(e),
                source=url,
            )
    
    async def _respect_rate_limit(self):
        """Add delay between requests to respect rate limits."""
        await asyncio.sleep(self.delay)
    
    @abstractmethod
    async def scrape(self, *args, **kwargs) -> ScraperResult:
        """Main scraping method to be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def parse(self, data: Any) -> List[Dict]:
        """Parse scraped data into structured format."""
        pass
