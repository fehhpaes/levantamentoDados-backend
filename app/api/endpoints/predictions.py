from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.prediction import Prediction, PredictionResult
from app.models.match import Match

router = APIRouter()


@router.get("/match/{match_id}", response_model=List[Prediction])
async def get_match_predictions(
    match_id: str,
    model_name: Optional[str] = None,
):
    query = {"match_id": match_id}
    if model_name:
        query["model_name"] = model_name
    return await Prediction.find(query).to_list()


@router.post("/", response_model=Prediction, status_code=201)
async def create_prediction(prediction: Prediction):
    match = await Match.get(prediction.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    await prediction.save()
    return prediction


@router.post("/{prediction_id}/result", response_model=PredictionResult, status_code=201)
async def record_prediction_result(
    prediction_id: str,
    actual_home_score: Optional[int] = None,
    actual_away_score: Optional[int] = None,
    score_correct: Optional[bool] = None,
    over_under_correct: Optional[bool] = None,
    btts_correct: Optional[bool] = None,
    bet_outcome: Optional[str] = None,
    profit_loss: Optional[float] = None,
):
    prediction = await Prediction.get(prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    actual_result = None
    if actual_home_score is not None and actual_away_score is not None:
        if actual_home_score > actual_away_score:
            actual_result = "home"
        elif actual_home_score < actual_away_score:
            actual_result = "away"
        else:
            actual_result = "draw"
    result_correct = None
    if actual_result and prediction.home_win_prob:
        predicted_result = "home" if prediction.home_win_prob > max(prediction.draw_prob or 0, prediction.away_win_prob or 0) else \
                          "away" if prediction.away_win_prob > max(prediction.draw_prob or 0, prediction.home_win_prob or 0) else "draw"
        result_correct = predicted_result == actual_result
    result = PredictionResult(
        prediction_id=prediction_id,
        match_id=prediction.match_id,
        actual_home_score=actual_home_score,
        actual_away_score=actual_away_score,
        actual_result=actual_result,
        result_correct=result_correct,
        score_correct=score_correct,
        over_under_correct=over_under_correct,
        btts_correct=btts_correct,
        bet_outcome=bet_outcome,
        profit_loss=profit_loss,
    )
    await result.save()
    return result


@router.get("/models/performance")
async def get_model_performance(
    model_name: Optional[str] = None,
):
    predictions = await Prediction.find().to_list()
    results = await PredictionResult.find().to_list()
    model_stats = {}
    for r in results:
        prediction = next((p for p in predictions if str(p.id) == r.prediction_id), None)
        if not prediction:
            continue
        if model_name and prediction.model_name != model_name:
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
        {
            "model_name": name,
            "total_predictions": stats["total"],
            "correct_results": stats["correct_results"],
            "correct_scores": stats["correct_scores"],
            "accuracy_result": stats["correct_results"] / stats["total"] if stats["total"] > 0 else 0,
            "accuracy_score": stats["correct_scores"] / stats["total"] if stats["total"] > 0 else 0,
            "total_profit_loss": stats["profit_loss"],
            "roi_percentage": (stats["profit_loss"] / stats["total"]) * 100 if stats["total"] > 0 else 0,
        }
        for name, stats in model_stats.items()
    ]


@router.get("/value-bets")
async def get_predicted_value_bets(
    min_confidence: float = Query(0.6, ge=0, le=1),
    min_edge: float = Query(5.0, description="Minimum expected value %"),
):
    predictions = await Prediction.find(
        {"confidence_score": {"$gte": min_confidence}, "expected_value": {"$gte": min_edge}}
    ).to_list()
    value_bets = []
    for p in predictions:
        if p.recommended_bet:
            match = await Match.get(p.match_id)
            value_bets.append({
                "match_id": p.match_id,
                "match_info": {
                    "match_date": str(match.match_date) if match else None,
                    "home_team": match.home_team if match else None,
                    "away_team": match.away_team if match else None,
                },
                "market": p.recommended_bet.split(" ")[0] if p.recommended_bet else "1X2",
                "selection": p.recommended_bet,
                "predicted_prob": max(p.home_win_prob or 0, p.draw_prob or 0, p.away_win_prob or 0),
                "bookmaker_odds": 0,
                "bookmaker_name": "",
                "implied_prob": 0,
                "edge_percentage": p.expected_value or 0,
                "expected_value": p.expected_value or 0,
                "confidence": p.confidence_score or 0,
            })
    return value_bets
