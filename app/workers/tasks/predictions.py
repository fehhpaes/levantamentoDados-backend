"""
Prediction tasks for generating and updating predictions.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from celery import shared_task
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Match, Prediction, PredictionResult
from app.ml.ensemble import EnsemblePredictor
from app.services.webhook import trigger_webhook_event
from app.schemas.webhook import WebhookEventType

logger = logging.getLogger(__name__)


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for Celery tasks."""
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _generate_predictions_async(
    match_ids: Optional[List[int]] = None,
    days_ahead: int = 3
) -> Dict[str, Any]:
    """
    Generate predictions for upcoming matches.
    
    Args:
        match_ids: Optional specific matches to predict
        days_ahead: Number of days ahead to predict
        
    Returns:
        Result summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            now = datetime.utcnow()
            
            # Get matches to predict
            query = select(Match).options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league)
            ).where(
                and_(
                    Match.match_date > now,
                    Match.match_date < now + timedelta(days=days_ahead),
                    Match.status == "scheduled"
                )
            )
            
            if match_ids:
                query = query.where(Match.id.in_(match_ids))
            
            result = await db.execute(query)
            matches = list(result.scalars().all())
            
            if not matches:
                return {"success": True, "predictions_generated": 0}
            
            # Initialize ensemble predictor
            predictor = EnsemblePredictor()
            
            predictions_generated = 0
            
            for match in matches:
                try:
                    # Check if prediction already exists
                    existing = await db.execute(
                        select(Prediction).where(
                            and_(
                                Prediction.match_id == match.id,
                                Prediction.created_at > now - timedelta(hours=24)
                            )
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        # Skip if recent prediction exists
                        continue
                    
                    # Generate prediction
                    pred_data = await predictor.predict(
                        home_team_id=match.home_team_id,
                        away_team_id=match.away_team_id,
                        league_id=match.league_id
                    )
                    
                    if not pred_data:
                        continue
                    
                    # Save prediction
                    prediction = Prediction(
                        match_id=match.id,
                        model_name=pred_data.get("model_name", "ensemble"),
                        home_win_prob=pred_data.get("home_win_prob"),
                        draw_prob=pred_data.get("draw_prob"),
                        away_win_prob=pred_data.get("away_win_prob"),
                        over_25_prob=pred_data.get("over_25_prob"),
                        btts_prob=pred_data.get("btts_prob"),
                        predicted_home_goals=pred_data.get("predicted_home_goals"),
                        predicted_away_goals=pred_data.get("predicted_away_goals"),
                        confidence=pred_data.get("confidence"),
                        features=pred_data.get("features"),
                    )
                    
                    db.add(prediction)
                    predictions_generated += 1
                    
                    # Trigger webhook
                    await trigger_webhook_event(
                        db,
                        WebhookEventType.PREDICTION_READY,
                        {
                            "match_id": match.id,
                            "match_name": f"{match.home_team.name} vs {match.away_team.name}" 
                                if match.home_team and match.away_team else "Unknown",
                            "match_date": match.match_date.isoformat(),
                            "prediction": {
                                "home_win": round(pred_data.get("home_win_prob", 0) * 100, 1),
                                "draw": round(pred_data.get("draw_prob", 0) * 100, 1),
                                "away_win": round(pred_data.get("away_win_prob", 0) * 100, 1),
                                "confidence": round(pred_data.get("confidence", 0) * 100, 1)
                            }
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to predict match {match.id}: {e}")
                    continue
            
            await db.commit()
            
            return {
                "success": True,
                "predictions_generated": predictions_generated,
                "matches_processed": len(matches)
            }
            
        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")
            await db.rollback()
            return {"success": False, "error": str(e)}


async def _update_prediction_results_async() -> Dict[str, Any]:
    """
    Update prediction results for finished matches.
    
    Returns:
        Result summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            # Get predictions without results for finished matches
            result = await db.execute(
                select(Prediction).options(
                    selectinload(Prediction.match)
                ).join(Match).where(
                    and_(
                        Match.status == "finished",
                        # Only get predictions that don't have results yet
                        ~Prediction.id.in_(
                            select(PredictionResult.prediction_id)
                        )
                    )
                )
            )
            
            predictions = list(result.scalars().all())
            
            if not predictions:
                return {"success": True, "results_updated": 0}
            
            updated = 0
            correct = 0
            
            for prediction in predictions:
                match = prediction.match
                
                if match.home_score is None or match.away_score is None:
                    continue
                
                # Determine actual result
                if match.home_score > match.away_score:
                    actual_result = "home_win"
                elif match.home_score < match.away_score:
                    actual_result = "away_win"
                else:
                    actual_result = "draw"
                
                # Determine predicted result
                probs = {
                    "home_win": prediction.home_win_prob or 0,
                    "draw": prediction.draw_prob or 0,
                    "away_win": prediction.away_win_prob or 0
                }
                predicted_result = max(probs, key=probs.get)
                
                is_correct = predicted_result == actual_result
                
                # Calculate other metrics
                over_25_actual = (match.home_score + match.away_score) > 2.5
                btts_actual = match.home_score > 0 and match.away_score > 0
                
                # Create result record
                pred_result = PredictionResult(
                    prediction_id=prediction.id,
                    actual_result=actual_result,
                    actual_home_score=match.home_score,
                    actual_away_score=match.away_score,
                    is_correct=is_correct,
                    over_25_correct=(prediction.over_25_prob or 0) > 0.5 == over_25_actual 
                        if prediction.over_25_prob else None,
                    btts_correct=(prediction.btts_prob or 0) > 0.5 == btts_actual 
                        if prediction.btts_prob else None,
                )
                
                db.add(pred_result)
                updated += 1
                
                if is_correct:
                    correct += 1
            
            await db.commit()
            
            return {
                "success": True,
                "results_updated": updated,
                "correct_predictions": correct,
                "accuracy": round(correct / updated * 100, 2) if updated > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Prediction results update failed: {e}")
            await db.rollback()
            return {"success": False, "error": str(e)}


async def _retrain_models_async() -> Dict[str, Any]:
    """
    Retrain ML models with new data.
    
    Returns:
        Training result
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            # Get historical match data for training
            cutoff_date = datetime.utcnow() - timedelta(days=365)
            
            result = await db.execute(
                select(Match).options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                    selectinload(Match.statistics)
                ).where(
                    and_(
                        Match.status == "finished",
                        Match.match_date > cutoff_date,
                        Match.home_score.isnot(None),
                        Match.away_score.isnot(None)
                    )
                )
            )
            
            matches = list(result.scalars().all())
            
            if len(matches) < 100:
                return {
                    "success": False,
                    "error": "Not enough data for training",
                    "matches_available": len(matches)
                }
            
            # Initialize predictor and train
            predictor = EnsemblePredictor()
            
            training_data = []
            for match in matches:
                training_data.append({
                    "home_team_id": match.home_team_id,
                    "away_team_id": match.away_team_id,
                    "league_id": match.league_id,
                    "home_score": match.home_score,
                    "away_score": match.away_score,
                    "match_date": match.match_date,
                    "statistics": match.statistics
                })
            
            metrics = await predictor.train(training_data)
            
            return {
                "success": True,
                "matches_used": len(matches),
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Model retraining failed: {e}")
            return {"success": False, "error": str(e)}


# Celery Tasks

@shared_task(
    bind=True,
    name="app.workers.tasks.predictions.generate_daily_predictions",
    max_retries=3,
    default_retry_delay=300
)
def generate_daily_predictions(self, days_ahead: int = 3) -> Dict[str, Any]:
    """
    Generate predictions for upcoming matches.
    
    Args:
        days_ahead: Number of days to look ahead
        
    Returns:
        Result summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            _generate_predictions_async(days_ahead=days_ahead)
        )
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Generate predictions task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="app.workers.tasks.predictions.update_prediction_results",
    max_retries=2,
    default_retry_delay=60
)
def update_prediction_results(self) -> Dict[str, Any]:
    """
    Update results for predictions of finished matches.
    
    Returns:
        Result summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_prediction_results_async())
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Update prediction results task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="app.workers.tasks.predictions.predict_match",
)
def predict_match(match_id: int) -> Dict[str, Any]:
    """
    Generate prediction for a specific match.
    
    Args:
        match_id: Match ID
        
    Returns:
        Prediction result
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        _generate_predictions_async(match_ids=[match_id])
    )
    loop.close()
    
    return result


@shared_task(
    name="app.workers.tasks.predictions.retrain_models",
)
def retrain_models() -> Dict[str, Any]:
    """
    Retrain ML models with latest data.
    
    Returns:
        Training metrics
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_retrain_models_async())
    loop.close()
    
    return result
