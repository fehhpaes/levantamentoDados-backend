from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.match import Match, MatchStatistics
from app.models.sport import Team, League
from app.models.odds import Odds
from app.models.prediction import Prediction, PredictionResult

router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for the dashboard."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    # Count stats
    total_matches = await db.scalar(select(func.count(Match.id)))
    today_matches = await db.scalar(
        select(func.count(Match.id)).where(
            and_(Match.match_date >= today, Match.match_date < tomorrow)
        )
    )
    live_matches = await db.scalar(
        select(func.count(Match.id)).where(Match.status == "live")
    )
    total_teams = await db.scalar(select(func.count(Team.id)))
    total_leagues = await db.scalar(select(func.count(League.id)))
    total_predictions = await db.scalar(select(func.count(Prediction.id)))
    
    return {
        "total_matches": total_matches or 0,
        "today_matches": today_matches or 0,
        "live_matches": live_matches or 0,
        "total_teams": total_teams or 0,
        "total_leagues": total_leagues or 0,
        "total_predictions": total_predictions or 0,
    }


@router.get("/team/{team_id}/stats")
async def get_team_statistics(
    team_id: int,
    last_n_matches: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed statistics for a team."""
    # Get team
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    
    if not team:
        return {"error": "Team not found"}
    
    # Get last N matches
    home_matches = await db.execute(
        select(Match).where(
            and_(Match.home_team_id == team_id, Match.status == "finished")
        ).order_by(Match.match_date.desc()).limit(last_n_matches)
    )
    away_matches = await db.execute(
        select(Match).where(
            and_(Match.away_team_id == team_id, Match.status == "finished")
        ).order_by(Match.match_date.desc()).limit(last_n_matches)
    )
    
    home_list = home_matches.scalars().all()
    away_list = away_matches.scalars().all()
    
    # Calculate statistics
    home_wins = sum(1 for m in home_list if (m.home_score or 0) > (m.away_score or 0))
    home_draws = sum(1 for m in home_list if (m.home_score or 0) == (m.away_score or 0))
    home_losses = len(home_list) - home_wins - home_draws
    
    away_wins = sum(1 for m in away_list if (m.away_score or 0) > (m.home_score or 0))
    away_draws = sum(1 for m in away_list if (m.home_score or 0) == (m.away_score or 0))
    away_losses = len(away_list) - away_wins - away_draws
    
    home_goals_for = sum(m.home_score or 0 for m in home_list)
    home_goals_against = sum(m.away_score or 0 for m in home_list)
    away_goals_for = sum(m.away_score or 0 for m in away_list)
    away_goals_against = sum(m.home_score or 0 for m in away_list)
    
    total_matches = len(home_list) + len(away_list)
    total_goals_for = home_goals_for + away_goals_for
    total_goals_against = home_goals_against + away_goals_against
    
    # Over/Under stats
    over_2_5_count = sum(1 for m in home_list + away_list if ((m.home_score or 0) + (m.away_score or 0)) > 2.5)
    btts_count = sum(1 for m in home_list + away_list if (m.home_score or 0) > 0 and (m.away_score or 0) > 0)
    
    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "logo_url": team.logo_url,
        },
        "overall": {
            "matches": total_matches,
            "wins": home_wins + away_wins,
            "draws": home_draws + away_draws,
            "losses": home_losses + away_losses,
            "goals_for": total_goals_for,
            "goals_against": total_goals_against,
            "goal_difference": total_goals_for - total_goals_against,
            "avg_goals_for": round(total_goals_for / total_matches, 2) if total_matches > 0 else 0,
            "avg_goals_against": round(total_goals_against / total_matches, 2) if total_matches > 0 else 0,
            "win_rate": round((home_wins + away_wins) / total_matches * 100, 1) if total_matches > 0 else 0,
        },
        "home": {
            "matches": len(home_list),
            "wins": home_wins,
            "draws": home_draws,
            "losses": home_losses,
            "goals_for": home_goals_for,
            "goals_against": home_goals_against,
        },
        "away": {
            "matches": len(away_list),
            "wins": away_wins,
            "draws": away_draws,
            "losses": away_losses,
            "goals_for": away_goals_for,
            "goals_against": away_goals_against,
        },
        "trends": {
            "over_2_5_percentage": round(over_2_5_count / total_matches * 100, 1) if total_matches > 0 else 0,
            "btts_percentage": round(btts_count / total_matches * 100, 1) if total_matches > 0 else 0,
        },
    }


@router.get("/league/{league_id}/standings")
async def get_league_standings(
    league_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get league standings."""
    # Get all teams in the league
    result = await db.execute(
        select(Team).where(Team.league_id == league_id).order_by(Team.points.desc())
    )
    teams = result.scalars().all()
    
    standings = []
    for i, team in enumerate(teams, 1):
        standings.append({
            "position": i,
            "team": {
                "id": team.id,
                "name": team.name,
                "short_name": team.short_name,
                "logo_url": team.logo_url,
            },
            "played": team.matches_played,
            "won": team.wins,
            "drawn": team.draws,
            "lost": team.losses,
            "goals_for": team.goals_for,
            "goals_against": team.goals_against,
            "goal_difference": team.goals_for - team.goals_against,
            "points": team.points,
        })
    
    return {
        "league_id": league_id,
        "standings": standings,
    }


@router.get("/league/{league_id}/top-scorers")
async def get_top_scorers(
    league_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get top scorers in a league."""
    from app.models.sport import Player
    
    result = await db.execute(
        select(Player).join(Team).where(
            Team.league_id == league_id
        ).order_by(Player.goals.desc()).limit(limit)
    )
    players = result.scalars().all()
    
    return [
        {
            "position": i,
            "player": {
                "id": p.id,
                "name": p.name,
                "photo_url": p.photo_url,
            },
            "team": {
                "id": p.team_id,
            },
            "goals": p.goals,
            "assists": p.assists,
            "appearances": p.appearances,
            "goals_per_game": round(p.goals / p.appearances, 2) if p.appearances > 0 else 0,
        }
        for i, p in enumerate(players, 1)
    ]


@router.get("/odds/market-analysis")
async def get_market_analysis(
    league_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Analyze betting market trends."""
    start_date = datetime.now() - timedelta(days=days)
    
    # Get finished matches with odds
    query = select(Match, Odds).join(Odds).where(
        and_(
            Match.status == "finished",
            Match.match_date >= start_date,
        )
    )
    
    if league_id:
        query = query.where(Match.league_id == league_id)
    
    result = await db.execute(query)
    data = result.all()
    
    # Analyze results
    home_wins = 0
    draws = 0
    away_wins = 0
    over_2_5 = 0
    btts = 0
    total = 0
    
    favorite_wins = 0
    underdog_wins = 0
    
    for match, odds in data:
        if match.home_score is None or match.away_score is None:
            continue
            
        total += 1
        
        if match.home_score > match.away_score:
            home_wins += 1
            if odds.home_odds and odds.away_odds and odds.home_odds < odds.away_odds:
                favorite_wins += 1
            else:
                underdog_wins += 1
        elif match.home_score < match.away_score:
            away_wins += 1
            if odds.home_odds and odds.away_odds and odds.away_odds < odds.home_odds:
                favorite_wins += 1
            else:
                underdog_wins += 1
        else:
            draws += 1
        
        total_goals = match.home_score + match.away_score
        if total_goals > 2.5:
            over_2_5 += 1
        if match.home_score > 0 and match.away_score > 0:
            btts += 1
    
    return {
        "period_days": days,
        "total_matches": total,
        "results": {
            "home_wins": home_wins,
            "home_wins_pct": round(home_wins / total * 100, 1) if total > 0 else 0,
            "draws": draws,
            "draws_pct": round(draws / total * 100, 1) if total > 0 else 0,
            "away_wins": away_wins,
            "away_wins_pct": round(away_wins / total * 100, 1) if total > 0 else 0,
        },
        "goals": {
            "over_2_5": over_2_5,
            "over_2_5_pct": round(over_2_5 / total * 100, 1) if total > 0 else 0,
            "btts": btts,
            "btts_pct": round(btts / total * 100, 1) if total > 0 else 0,
        },
        "favorites": {
            "favorite_wins": favorite_wins,
            "favorite_wins_pct": round(favorite_wins / (favorite_wins + underdog_wins) * 100, 1) if (favorite_wins + underdog_wins) > 0 else 0,
            "underdog_wins": underdog_wins,
        },
    }
