from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.core.database import get_db
from app.models.prediction import Prediction, PredictionResult
from app.models.match import Match
from app.schemas.prediction import (
    PredictionCreate, PredictionResponse, PredictionWithMatchResponse,
    PredictionResultCreate, PredictionResultResponse,
    ModelPerformance, ValueBet,
)

router = APIRouter()


@router.get("/match/{match_id}", response_model=List[PredictionResponse])
async def get_match_predictions(
    match_id: int,
    model_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all predictions for a match."""
    query = select(Prediction).where(Prediction.match_id == match_id)
    
    if model_name:
        query = query.where(Prediction.model_name == model_name)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=PredictionResponse, status_code=201)
async def create_prediction(
    prediction: PredictionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new prediction."""
    # Validate match exists
    result = await db.execute(select(Match).where(Match.id == prediction.match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Convert dict fields to JSON strings
    data = prediction.model_dump()
    if data.get("features_used"):
        import json
        data["features_used"] = json.dumps(data["features_used"])
    if data.get("prediction_details"):
        import json
        data["prediction_details"] = json.dumps(data["prediction_details"])
    
    db_prediction = Prediction(**data)
    db.add(db_prediction)
    await db.commit()
    await db.refresh(db_prediction)
    return db_prediction


@router.post("/{prediction_id}/result", response_model=PredictionResultResponse, status_code=201)
async def record_prediction_result(
    prediction_id: int,
    result_data: PredictionResultCreate,
    db: AsyncSession = Depends(get_db)
):
    """Record the actual result of a prediction."""
    # Check if prediction exists
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    # Calculate correctness
    actual_result = None
    if result_data.actual_home_score is not None and result_data.actual_away_score is not None:
        if result_data.actual_home_score > result_data.actual_away_score:
            actual_result = "home"
        elif result_data.actual_home_score < result_data.actual_away_score:
            actual_result = "away"
        else:
            actual_result = "draw"
    
    # Determine if prediction was correct
    result_correct = None
    if actual_result and prediction.home_win_prob:
        predicted_result = "home" if prediction.home_win_prob > max(prediction.draw_prob or 0, prediction.away_win_prob or 0) else \
                          "away" if prediction.away_win_prob > max(prediction.draw_prob or 0, prediction.home_win_prob or 0) else "draw"
        result_correct = predicted_result == actual_result
    
    db_result = PredictionResult(
        prediction_id=prediction_id,
        match_id=prediction.match_id,
        actual_home_score=result_data.actual_home_score,
        actual_away_score=result_data.actual_away_score,
        actual_result=actual_result,
        result_correct=result_correct,
        score_correct=result_data.score_correct,
        over_under_correct=result_data.over_under_correct,
        btts_correct=result_data.btts_correct,
        bet_outcome=result_data.bet_outcome,
        profit_loss=result_data.profit_loss,
    )
    
    db.add(db_result)
    await db.commit()
    await db.refresh(db_result)
    return db_result


@router.get("/models/performance", response_model=List[ModelPerformance])
async def get_model_performance(
    model_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get performance metrics for prediction models."""
    # Get all prediction results with their predictions
    query = select(PredictionResult).options(
        selectinload(PredictionResult.prediction_id)
    )
    
    if model_name:
        query = query.join(Prediction).where(Prediction.model_name == model_name)
    
    result = await db.execute(query)
    results = result.scalars().all()
    
    # Group by model name and calculate metrics
    # This is a simplified version - in production, use SQL aggregations
    model_stats = {}
    
    for r in results:
        # Get the prediction for this result
        pred_result = await db.execute(
            select(Prediction).where(Prediction.id == r.prediction_id)
        )
        prediction = pred_result.scalar_one_or_none()
        if not prediction:
            continue
            
        name = prediction.model_name
        if name not in model_stats:
            model_stats[name] = {
                "total": 0,
                "correct_results": 0,
                "correct_scores": 0,
                "profit_loss": 0.0,
            }
        
        model_stats[name]["total"] += 1
        if r.result_correct:
            model_stats[name]["correct_results"] += 1
        if r.score_correct:
            model_stats[name]["correct_scores"] += 1
        if r.profit_loss:
            model_stats[name]["profit_loss"] += r.profit_loss
    
    return [
        ModelPerformance(
            model_name=name,
            total_predictions=stats["total"],
            correct_results=stats["correct_results"],
            correct_scores=stats["correct_scores"],
            accuracy_result=stats["correct_results"] / stats["total"] if stats["total"] > 0 else 0,
            accuracy_score=stats["correct_scores"] / stats["total"] if stats["total"] > 0 else 0,
            total_profit_loss=stats["profit_loss"],
            roi_percentage=(stats["profit_loss"] / stats["total"]) * 100 if stats["total"] > 0 else 0,
        )
        for name, stats in model_stats.items()
    ]


@router.get("/value-bets", response_model=List[ValueBet])
async def get_predicted_value_bets(
    min_confidence: float = Query(0.6, ge=0, le=1),
    min_edge: float = Query(5.0, description="Minimum expected value %"),
    db: AsyncSession = Depends(get_db)
):
    """Get value bets based on prediction models."""
    query = select(Prediction).options(
        selectinload(Prediction.match)
    ).where(
        and_(
            Prediction.confidence_score >= min_confidence,
            Prediction.expected_value >= min_edge,
        )
    )
    
    result = await db.execute(query)
    predictions = result.scalars().all()
    
    value_bets = []
    for p in predictions:
        if p.recommended_bet:
            value_bets.append(ValueBet(
                match_id=p.match_id,
                match_info={
                    "match_date": str(p.match.match_date) if p.match else None,
                },
                market=p.recommended_bet.split(" ")[0] if p.recommended_bet else "1X2",
                selection=p.recommended_bet,
                predicted_prob=max(p.home_win_prob or 0, p.draw_prob or 0, p.away_win_prob or 0),
                bookmaker_odds=0,  # Would need to join with odds table
                bookmaker_name="",
                implied_prob=0,
                edge_percentage=p.expected_value or 0,
                expected_value=p.expected_value or 0,
                confidence=p.confidence_score or 0,
            ))
    
    return value_bets
