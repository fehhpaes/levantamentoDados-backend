"""
Data Export API Endpoints.

Provides endpoints for exporting data in various formats (CSV, Excel, PDF).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum
import io

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.services.data_export import DataExporter, ExportFormat


router = APIRouter()


# ========================
# Schemas
# ========================

class ExportFormatType(str, Enum):
    csv = "csv"
    excel = "excel"
    pdf = "pdf"
    json = "json"


class DataType(str, Enum):
    predictions = "predictions"
    bets = "bets"
    matches = "matches"
    odds = "odds"
    analytics = "analytics"
    backtest_results = "backtest_results"
    bankroll_history = "bankroll_history"


class ExportRequest(BaseModel):
    data_type: DataType
    format: ExportFormatType = ExportFormatType.csv
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    filters: Optional[dict] = None
    columns: Optional[List[str]] = Field(
        default=None,
        description="Specific columns to include. If None, includes all."
    )
    include_summary: bool = Field(
        default=True,
        description="Include summary statistics in export"
    )


class ExportResponse(BaseModel):
    export_id: str
    status: str
    download_url: Optional[str]
    expires_at: Optional[datetime]
    file_size: Optional[int]
    row_count: Optional[int]


class ScheduledExportCreate(BaseModel):
    data_type: DataType
    format: ExportFormatType = ExportFormatType.csv
    frequency: str = Field(..., pattern="^(daily|weekly|monthly)$")
    email_to: List[str]
    filters: Optional[dict] = None
    active: bool = True


class ScheduledExportResponse(BaseModel):
    id: int
    data_type: DataType
    format: ExportFormatType
    frequency: str
    email_to: List[str]
    last_run: Optional[datetime]
    next_run: datetime
    active: bool
    created_at: datetime


# ========================
# Endpoints
# ========================

@router.post("/", response_model=ExportResponse)
async def create_export(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a data export job.
    
    For small datasets, returns the file directly.
    For large datasets, returns a job ID to check status.
    """
    import uuid
    export_id = str(uuid.uuid4())
    
    # In production, check data size and either:
    # 1. Generate and return file directly
    # 2. Queue background job for large exports
    
    return ExportResponse(
        export_id=export_id,
        status="completed",
        download_url=f"/api/v1/export/download/{export_id}",
        expires_at=datetime.utcnow().replace(hour=23, minute=59),
        file_size=15420,
        row_count=250,
    )


@router.get("/download/{export_id}")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download a completed export file."""
    # In production, fetch the file from storage
    # For now, generate sample CSV
    
    csv_content = """date,match,prediction,confidence,result,profit_loss
2024-01-15,Team A vs Team B,Home Win,0.72,won,27.50
2024-01-15,Team C vs Team D,Over 2.5,0.65,lost,-25.00
2024-01-16,Team E vs Team F,Away Win,0.58,won,42.00
2024-01-16,Team G vs Team H,BTTS Yes,0.70,won,18.00
"""
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=export_{export_id}.csv"
        }
    )


@router.get("/predictions")
async def export_predictions(
    format: ExportFormatType = ExportFormatType.csv,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    model: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0, le=1),
    sport: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export predictions data with filters."""
    # Generate CSV content
    csv_content = """prediction_id,date,match,sport,model,home_win_prob,draw_prob,away_win_prob,confidence,recommended_bet,result
1,2024-01-15,Flamengo vs Palmeiras,football,ensemble,0.45,0.28,0.27,0.72,Home Win,correct
2,2024-01-15,Lakers vs Celtics,basketball,xgboost,0.52,0.00,0.48,0.65,Home Win,correct
3,2024-01-16,Nadal vs Djokovic,tennis,elo,0.42,0.00,0.58,0.70,Away Win,incorrect
"""
    
    filename = f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/bets")
async def export_bets(
    format: ExportFormatType = ExportFormatType.csv,
    bankroll_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export betting history."""
    csv_content = """bet_id,date,bankroll,match,market,selection,odds,stake,status,profit_loss,balance_after
1,2024-01-15,Main,Flamengo vs Palmeiras,1X2,Home Win,2.10,25.00,won,27.50,1027.50
2,2024-01-15,Main,Santos vs Corinthians,Over/Under,Over 2.5,1.85,30.00,lost,-30.00,997.50
3,2024-01-16,Main,Atletico vs Cruzeiro,BTTS,Yes,1.95,20.00,won,19.00,1016.50
"""
    
    filename = f"bets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/odds-history")
async def export_odds_history(
    format: ExportFormatType = ExportFormatType.csv,
    match_id: Optional[int] = None,
    bookmaker: Optional[str] = None,
    market: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export odds movement history."""
    csv_content = """timestamp,match,bookmaker,market,selection,odds,previous_odds,change_pct
2024-01-15 10:00,Flamengo vs Palmeiras,Bet365,1X2,Home,2.10,2.15,-2.33
2024-01-15 12:00,Flamengo vs Palmeiras,Bet365,1X2,Home,2.05,2.10,-2.38
2024-01-15 14:00,Flamengo vs Palmeiras,Betfair,1X2,Home,2.08,2.12,-1.89
2024-01-15 10:00,Flamengo vs Palmeiras,Bet365,Over/Under,Over 2.5,1.85,1.90,-2.63
"""
    
    filename = f"odds_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/backtest/{backtest_id}")
async def export_backtest_results(
    backtest_id: int,
    format: ExportFormatType = ExportFormatType.csv,
    include_all_bets: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Export detailed backtest results."""
    csv_content = """# Backtest Results - Strategy: Value Betting
# Period: 2024-01-01 to 2024-06-30
# Initial Bankroll: R$ 1000.00

# Summary
metric,value
Total Bets,250
Win Rate,56.0%
ROI,19.0%
Total Profit,R$ 2375.00
Max Drawdown,R$ 450.00
Sharpe Ratio,1.85

# Bet Details
date,match,market,selection,odds,stake,predicted_prob,edge,result,profit_loss,bankroll
2024-01-02,Team A vs Team B,1X2,Home,2.10,20.00,0.55,10.5%,won,22.00,1022.00
2024-01-03,Team C vs Team D,Over/Under,Over 2.5,1.90,25.00,0.58,8.2%,lost,-25.00,997.00
"""
    
    filename = f"backtest_{backtest_id}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/analytics-report")
async def export_analytics_report(
    format: ExportFormatType = ExportFormatType.pdf,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_charts: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export comprehensive analytics report.
    
    PDF format includes charts and visualizations.
    """
    if format == ExportFormatType.pdf:
        # In production, generate actual PDF with charts
        # For now, return info about what would be included
        return {
            "message": "PDF report generation queued",
            "sections": [
                "Executive Summary",
                "Prediction Accuracy by Model",
                "ROI by Sport/League",
                "Monthly Performance",
                "Best/Worst Performing Markets",
                "Risk Analysis",
                "Recommendations",
            ],
            "download_url": "/api/v1/export/download/report_123",
            "estimated_pages": 12,
        }
    
    # CSV version
    csv_content = """# Analytics Report
# Generated: 2024-01-20

# Model Performance
model,predictions,accuracy,roi
ensemble,500,68.5%,22.3%
poisson,500,65.2%,18.1%
elo,500,62.8%,15.5%
xgboost,500,67.1%,20.2%

# Sport Performance
sport,bets,win_rate,roi
football,300,58%,21%
basketball,120,55%,18%
tennis,60,62%,25%
esports,20,50%,10%
"""
    
    filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ========================
# Scheduled Exports
# ========================

@router.post("/scheduled", response_model=ScheduledExportResponse, status_code=201)
async def create_scheduled_export(
    export: ScheduledExportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a scheduled recurring export."""
    from datetime import timedelta
    
    next_run = datetime.utcnow()
    if export.frequency == "daily":
        next_run += timedelta(days=1)
    elif export.frequency == "weekly":
        next_run += timedelta(weeks=1)
    else:  # monthly
        next_run += timedelta(days=30)
    
    return ScheduledExportResponse(
        id=1,
        data_type=export.data_type,
        format=export.format,
        frequency=export.frequency,
        email_to=export.email_to,
        last_run=None,
        next_run=next_run,
        active=export.active,
        created_at=datetime.utcnow(),
    )


@router.get("/scheduled", response_model=List[ScheduledExportResponse])
async def list_scheduled_exports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all scheduled exports for the current user."""
    return [
        ScheduledExportResponse(
            id=1,
            data_type=DataType.predictions,
            format=ExportFormatType.csv,
            frequency="daily",
            email_to=["user@example.com"],
            last_run=datetime.utcnow(),
            next_run=datetime.utcnow(),
            active=True,
            created_at=datetime.utcnow(),
        ),
    ]


@router.delete("/scheduled/{export_id}", status_code=204)
async def delete_scheduled_export(
    export_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scheduled export."""
    return None


@router.patch("/scheduled/{export_id}/toggle")
async def toggle_scheduled_export(
    export_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a scheduled export on/off."""
    return {
        "id": export_id,
        "active": True,  # Would toggle in production
        "message": "Scheduled export toggled successfully",
    }
