from fastapi import APIRouter
from typing import Optional
import httpx
from datetime import datetime, timedelta
import random

from app.core.config import settings
from app.models.sport import Sport, League, Team
from app.models.match import Match, MatchStatus
from app.models.odds import Bookmaker, Odds
from app.models.prediction import Prediction

router = APIRouter()


async def seed_demo_data():
    sport = await Sport.find_one({"slug": "football"})
    if not sport:
        sport = Sport(
            name="Football",
            slug="football",
            description="Association Football",
            icon="⚽",
            is_active=True,
        )
        await sport.save()

    leagues_data = [
        {"name": "Premier League", "slug": "premier-league", "country": "England", "country_code": "GB"},
        {"name": "La Liga", "slug": "la-liga", "country": "Spain", "country_code": "ES"},
        {"name": "Serie A", "slug": "serie-a", "country": "Italy", "country_code": "IT"},
        {"name": "Bundesliga", "slug": "bundesliga", "country": "Germany", "country_code": "DE"},
        {"name": "Ligue 1", "slug": "ligue-1", "country": "France", "country_code": "FR"},
        {"name": "Brasileirão", "slug": "brasileirao", "country": "Brazil", "country_code": "BR"},
    ]

    leagues = {}
    for ld in leagues_data:
        existing = await League.find_one({"slug": ld["slug"]})
        if not existing:
            league = League(
                sport_id=str(sport.id),
                name=ld["name"],
                slug=ld["slug"],
                country=ld["country"],
                country_code=ld["country_code"],
                season="2024/2025",
            )
            await league.save()
        else:
            league = existing
        leagues[ld["slug"]] = league

    teams_data = {
        "premier-league": [
            {"name": "Arsenal", "short_name": "ARS"},
            {"name": "Chelsea", "short_name": "CHE"},
            {"name": "Liverpool", "short_name": "LIV"},
            {"name": "Manchester City", "short_name": "MCI"},
            {"name": "Manchester United", "short_name": "MUN"},
            {"name": "Tottenham", "short_name": "TOT"},
            {"name": "Aston Villa", "short_name": "AVL"},
            {"name": "Newcastle", "short_name": "NEW"},
        ],
        "la-liga": [
            {"name": "Barcelona", "short_name": "BAR"},
            {"name": "Real Madrid", "short_name": "RMA"},
            {"name": "Atletico Madrid", "short_name": "ATM"},
            {"name": "Real Sociedad", "short_name": "RSO"},
            {"name": "Athletic Bilbao", "short_name": "ATH"},
            {"name": "Villarreal", "short_name": "VIL"},
        ],
        "brasileirao": [
            {"name": "Flamengo", "short_name": "FLA"},
            {"name": "Palmeiras", "short_name": "PAL"},
            {"name": "São Paulo", "short_name": "SAO"},
            {"name": "Corinthians", "short_name": "COR"},
            {"name": "Atlético Mineiro", "short_name": "CAM"},
            {"name": "Botafogo", "short_name": "BOT"},
            {"name": "Fluminense", "short_name": "FLU"},
            {"name": "Grêmio", "short_name": "GRE"},
        ],
    }

    all_teams = {}
    for league_slug, league in leagues.items():
        if league_slug in teams_data:
            for td in teams_data[league_slug]:
                existing = await Team.find_one({"name": td["name"]})
                if not existing:
                    team = Team(
                        league_id=str(league.id),
                        name=td["name"],
                        short_name=td["short_name"],
                        slug=td["name"].lower().replace(" ", "-"),
                        country=league.country,
                        matches_played=random.randint(10, 30),
                        wins=random.randint(5, 20),
                        draws=random.randint(2, 8),
                        losses=random.randint(1, 10),
                        goals_for=random.randint(20, 60),
                        goals_against=random.randint(10, 40),
                        points=random.randint(20, 65),
                    )
                    await team.save()
                else:
                    team = existing
                all_teams[td["short_name"]] = team

    bookmakers_data = ["Bet365", "Betfair", "Pinnacle", "William Hill", "1xBet"]
    for bm_name in bookmakers_data:
        existing = await Bookmaker.find_one({"name": bm_name})
        if not existing:
            bm = Bookmaker(
                name=bm_name,
                slug=bm_name.lower().replace(" ", "-"),
                is_active=True,
            )
            await bm.save()
        else:
            bm = existing

    bookmakers = await Bookmaker.find().to_list()

    existing_matches = await Match.find().count()
    if existing_matches > 0:
        return {"message": "Data already exists", "matches": existing_matches}

    now = datetime.utcnow()
    match_count = 0

    for league_slug, league in leagues.items():
        if league_slug not in teams_data:
            continue
        league_teams = teams_data[league_slug]
        for i in range(len(league_teams)):
            for j in range(i + 1, len(league_teams)):
                home_td = league_teams[i]
                away_td = league_teams[j]
                home_team = all_teams.get(home_td["short_name"])
                away_team = all_teams.get(away_td["short_name"])
                if not home_team or not away_team:
                    continue

                days_offset = random.randint(-5, 14)
                match_date = now + timedelta(days=days_offset, hours=random.randint(12, 21))

                if days_offset < 0:
                    status = MatchStatus.FINISHED.value
                    home_score = random.randint(0, 4)
                    away_score = random.randint(0, 3)
                elif days_offset == 0 and match_date < now:
                    status = MatchStatus.FINISHED.value
                    home_score = random.randint(0, 4)
                    away_score = random.randint(0, 3)
                else:
                    status = MatchStatus.SCHEDULED.value
                    home_score = None
                    away_score = None

                match = Match(
                    league_id=str(league.id),
                    home_team_id=str(home_team.id),
                    away_team_id=str(away_team.id),
                    match_date=match_date,
                    status=status,
                    home_score=home_score,
                    away_score=away_score,
                    home_team={"id": str(home_team.id), "name": home_team.name, "logo_url": None},
                    away_team={"id": str(away_team.id), "name": away_team.name, "logo_url": None},
                    league={"id": str(league.id), "name": league.name},
                )
                await match.save()
                match_count += 1

                if status == MatchStatus.SCHEDULED.value:
                    for bm in bookmakers[:3]:
                        home_odds = round(random.uniform(1.3, 4.5), 2)
                        draw_odds = round(random.uniform(2.8, 4.2), 2)
                        away_odds = round(random.uniform(1.3, 5.0), 2)
                        odds = Odds(
                            match_id=str(match.id),
                            bookmaker_id=str(bm.id),
                            market_type="1X2",
                            market_name="Match Result",
                            home_odds=home_odds,
                            draw_odds=draw_odds,
                            away_odds=away_odds,
                            home_prob=round((1/home_odds) / ((1/home_odds)+(1/draw_odds)+(1/away_odds)), 3),
                            draw_prob=round((1/draw_odds) / ((1/home_odds)+(1/draw_odds)+(1/away_odds)), 3),
                            away_prob=round((1/away_odds) / ((1/home_odds)+(1/draw_odds)+(1/away_odds)), 3),
                            odds_updated_at=datetime.utcnow(),
                        )
                        await odds.save()

                        over_odds = round(random.uniform(1.5, 2.3), 2)
                        under_odds = round(random.uniform(1.5, 2.5), 2)
                        odds_ou = Odds(
                            match_id=str(match.id),
                            bookmaker_id=str(bm.id),
                            market_type="Over/Under",
                            market_name="Total Goals",
                            over_odds=over_odds,
                            under_odds=under_odds,
                            line=2.5,
                            odds_updated_at=datetime.utcnow(),
                        )
                        await odds_ou.save()

                    home_prob = random.uniform(0.25, 0.55)
                    draw_prob = random.uniform(0.20, 0.30)
                    away_prob = 1 - home_prob - draw_prob
                    prediction = Prediction(
                        match_id=str(match.id),
                        model_name="ensemble",
                        model_version="v1.0",
                        home_win_prob=round(home_prob, 3),
                        draw_prob=round(draw_prob, 3),
                        away_win_prob=round(away_prob, 3),
                        predicted_home_score=round(random.uniform(1.0, 2.5), 1),
                        predicted_away_score=round(random.uniform(0.5, 1.8), 1),
                        over_2_5_prob=round(random.uniform(0.35, 0.65), 3),
                        under_2_5_prob=round(1 - random.uniform(0.35, 0.65), 3),
                        btts_yes_prob=round(random.uniform(0.40, 0.65), 3),
                        btts_no_prob=round(1 - random.uniform(0.40, 0.65), 3),
                        confidence_score=round(random.uniform(0.55, 0.85), 3),
                        recommended_bet=random.choice(["Home Win", "Draw", "Away Win", "Over 2.5", "BTTS Yes"]),
                        expected_value=round(random.uniform(3, 15), 1),
                    )
                    await prediction.save()

    return {"message": "Demo data seeded successfully", "matches": match_count}


@router.get("/")
@router.post("/")
async def seed():
    result = await seed_demo_data()
    return result
