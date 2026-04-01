from .base import BaseScraper, ScraperResult
from .football import FootballDataScraper, FlashScoreScraper
from .odds import TheOddsAPIScraper

__all__ = [
    "BaseScraper",
    "ScraperResult",
    "FootballDataScraper",
    "FlashScoreScraper",
    "TheOddsAPIScraper",
]
