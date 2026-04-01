"""
Email Digest Service for Sports Alerts

Sends daily/weekly email digests with:
- Value bet opportunities
- Match predictions
- Performance summaries
- Upcoming matches of interest
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio
from jinja2 import Template
import json

logger = logging.getLogger(__name__)


class DigestFrequency(Enum):
    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"


class AlertType(Enum):
    VALUE_BET = "value_bet"
    MATCH_START = "match_start"
    ODDS_MOVEMENT = "odds_movement"
    PREDICTION_UPDATE = "prediction_update"
    PERFORMANCE_REPORT = "performance_report"


@dataclass
class EmailConfig:
    """Email server configuration."""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    from_email: str
    from_name: str = "Sports Analytics"
    use_tls: bool = True


@dataclass
class UserPreferences:
    """User notification preferences."""
    user_id: int
    email: str
    name: str
    frequency: DigestFrequency = DigestFrequency.DAILY
    alert_types: List[AlertType] = field(default_factory=lambda: list(AlertType))
    min_edge: float = 0.05  # Minimum edge for value bet alerts
    min_confidence: float = 0.6  # Minimum confidence for predictions
    favorite_teams: List[int] = field(default_factory=list)
    favorite_leagues: List[int] = field(default_factory=list)
    timezone: str = "UTC"


@dataclass
class Alert:
    """Individual alert item."""
    alert_type: AlertType
    title: str
    message: str
    data: Dict[str, Any]
    priority: int = 1  # 1=high, 2=medium, 3=low
    created_at: datetime = field(default_factory=datetime.now)


class EmailTemplate:
    """Email templates for different digest types."""
    
    DIGEST_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #1a365d; color: white; padding: 20px; text-align: center; }
            .section { margin: 20px 0; padding: 15px; background: #f7fafc; border-radius: 8px; }
            .section-title { color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 5px; }
            .value-bet { background: #c6f6d5; padding: 10px; margin: 10px 0; border-radius: 4px; }
            .match-card { border: 1px solid #e2e8f0; padding: 15px; margin: 10px 0; border-radius: 4px; }
            .probability { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
            .high { background: #48bb78; color: white; }
            .medium { background: #ecc94b; color: #333; }
            .low { background: #fc8181; color: white; }
            .stats-table { width: 100%; border-collapse: collapse; }
            .stats-table td { padding: 8px; border-bottom: 1px solid #e2e8f0; }
            .footer { text-align: center; padding: 20px; color: #718096; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ title }}</h1>
                <p>{{ subtitle }}</p>
            </div>
            
            {% if value_bets %}
            <div class="section">
                <h2 class="section-title">Value Bets</h2>
                {% for bet in value_bets %}
                <div class="value-bet">
                    <strong>{{ bet.match }}</strong><br>
                    Market: {{ bet.market }} @ {{ bet.odds }}<br>
                    Edge: <strong>{{ bet.edge }}%</strong> | 
                    Expected Value: {{ bet.ev }}%<br>
                    Recommended Stake: {{ bet.stake }}% of bankroll
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            {% if predictions %}
            <div class="section">
                <h2 class="section-title">Top Predictions</h2>
                {% for pred in predictions %}
                <div class="match-card">
                    <strong>{{ pred.home_team }} vs {{ pred.away_team }}</strong><br>
                    <span class="probability {{ pred.confidence_class }}">
                        {{ pred.predicted_outcome }} ({{ pred.confidence }}%)
                    </span><br>
                    Kickoff: {{ pred.kickoff }}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            {% if performance %}
            <div class="section">
                <h2 class="section-title">Performance Summary</h2>
                <table class="stats-table">
                    <tr><td>Predictions Made</td><td><strong>{{ performance.total }}</strong></td></tr>
                    <tr><td>Correct Predictions</td><td><strong>{{ performance.correct }}</strong></td></tr>
                    <tr><td>Accuracy</td><td><strong>{{ performance.accuracy }}%</strong></td></tr>
                    <tr><td>ROI (Value Bets)</td><td><strong>{{ performance.roi }}%</strong></td></tr>
                </table>
            </div>
            {% endif %}
            
            {% if upcoming_matches %}
            <div class="section">
                <h2 class="section-title">Upcoming Matches</h2>
                {% for match in upcoming_matches %}
                <div class="match-card">
                    {{ match.home_team }} vs {{ match.away_team }}<br>
                    {{ match.league }} | {{ match.kickoff }}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="footer">
                <p>Sports Analytics - Data-Driven Predictions</p>
                <p>
                    <a href="{{ unsubscribe_url }}">Unsubscribe</a> | 
                    <a href="{{ preferences_url }}">Manage Preferences</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    INSTANT_ALERT_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            .alert { padding: 20px; border-radius: 8px; }
            .value-bet { background: #c6f6d5; border-left: 4px solid #38a169; }
            .odds-movement { background: #feebc8; border-left: 4px solid #dd6b20; }
        </style>
    </head>
    <body>
        <div class="alert {{ alert_class }}">
            <h2>{{ title }}</h2>
            <p>{{ message }}</p>
            {% if details %}
            <hr>
            <p>{{ details }}</p>
            {% endif %}
        </div>
    </body>
    </html>
    """


class EmailDigestService:
    """
    Service for sending email digests and alerts.
    
    Features:
    - Daily/weekly digest compilation
    - Instant value bet alerts
    - Odds movement notifications
    - Performance reports
    - Template-based emails
    """
    
    def __init__(self, config: EmailConfig):
        """
        Initialize email service.
        
        Args:
            config: Email server configuration
        """
        self.config = config
        self.pending_alerts: Dict[int, List[Alert]] = {}  # user_id -> alerts
        self.user_preferences: Dict[int, UserPreferences] = {}
    
    def register_user(self, preferences: UserPreferences) -> None:
        """Register user preferences for alerts."""
        self.user_preferences[preferences.user_id] = preferences
        self.pending_alerts[preferences.user_id] = []
        logger.info(f"Registered user {preferences.user_id} for alerts")
    
    def add_alert(
        self,
        user_id: int,
        alert: Alert
    ) -> None:
        """
        Add alert to user's pending alerts.
        
        If user prefers instant alerts for this type, send immediately.
        """
        if user_id not in self.user_preferences:
            logger.warning(f"User {user_id} not registered for alerts")
            return
        
        prefs = self.user_preferences[user_id]
        
        # Check if user wants this alert type
        if alert.alert_type not in prefs.alert_types:
            return
        
        # Check if instant delivery
        if prefs.frequency == DigestFrequency.INSTANT:
            self._send_instant_alert(prefs, alert)
        else:
            # Queue for digest
            if user_id not in self.pending_alerts:
                self.pending_alerts[user_id] = []
            self.pending_alerts[user_id].append(alert)
    
    def create_value_bet_alert(
        self,
        match: str,
        market: str,
        odds: float,
        probability: float,
        edge: float,
        recommended_stake: float
    ) -> Alert:
        """Create a value bet alert."""
        return Alert(
            alert_type=AlertType.VALUE_BET,
            title=f"Value Bet Found: {match}",
            message=f"{market} @ {odds:.2f} with {edge*100:.1f}% edge",
            data={
                "match": match,
                "market": market,
                "odds": odds,
                "probability": probability,
                "edge": edge,
                "stake": recommended_stake
            },
            priority=1 if edge > 0.10 else 2
        )
    
    def create_odds_movement_alert(
        self,
        match: str,
        market: str,
        old_odds: float,
        new_odds: float,
        direction: str
    ) -> Alert:
        """Create an odds movement alert."""
        change_pct = abs(new_odds - old_odds) / old_odds * 100
        
        return Alert(
            alert_type=AlertType.ODDS_MOVEMENT,
            title=f"Odds Movement: {match}",
            message=f"{market}: {old_odds:.2f} → {new_odds:.2f} ({direction} {change_pct:.1f}%)",
            data={
                "match": match,
                "market": market,
                "old_odds": old_odds,
                "new_odds": new_odds,
                "change_percent": change_pct,
                "direction": direction
            },
            priority=2
        )
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body (optional)
            
        Returns:
            True if successful
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = to_email
            
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.username, self.config.password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def _send_instant_alert(
        self,
        user: UserPreferences,
        alert: Alert
    ) -> bool:
        """Send instant alert email."""
        template = Template(EmailTemplate.INSTANT_ALERT_HTML)
        
        alert_class = {
            AlertType.VALUE_BET: "value-bet",
            AlertType.ODDS_MOVEMENT: "odds-movement"
        }.get(alert.alert_type, "")
        
        details = None
        if alert.alert_type == AlertType.VALUE_BET:
            data = alert.data
            details = (
                f"Odds: {data['odds']:.2f} | "
                f"Probability: {data['probability']*100:.1f}% | "
                f"Recommended Stake: {data['stake']*100:.1f}%"
            )
        
        html = template.render(
            title=alert.title,
            message=alert.message,
            alert_class=alert_class,
            details=details
        )
        
        return self._send_email(
            user.email,
            f"[Alert] {alert.title}",
            html
        )
    
    def compile_digest(
        self,
        user_id: int,
        value_bets: Optional[List[Dict]] = None,
        predictions: Optional[List[Dict]] = None,
        performance: Optional[Dict] = None,
        upcoming_matches: Optional[List[Dict]] = None
    ) -> str:
        """
        Compile digest HTML from components.
        
        Args:
            user_id: User ID
            value_bets: Value bet opportunities
            predictions: Match predictions
            performance: Performance summary
            upcoming_matches: Upcoming matches
            
        Returns:
            Compiled HTML
        """
        if user_id not in self.user_preferences:
            raise ValueError(f"User {user_id} not registered")
        
        user = self.user_preferences[user_id]
        template = Template(EmailTemplate.DIGEST_HTML)
        
        # Format data
        formatted_bets = []
        if value_bets:
            for bet in value_bets:
                formatted_bets.append({
                    "match": bet["match"],
                    "market": bet["market"],
                    "odds": f"{bet['odds']:.2f}",
                    "edge": f"{bet['edge']*100:.1f}",
                    "ev": f"{bet.get('expected_value', 0)*100:.1f}",
                    "stake": f"{bet.get('recommended_stake', 0.02)*100:.1f}"
                })
        
        formatted_predictions = []
        if predictions:
            for pred in predictions:
                confidence = pred.get("confidence", 0.5) * 100
                confidence_class = "high" if confidence >= 70 else "medium" if confidence >= 50 else "low"
                
                formatted_predictions.append({
                    "home_team": pred["home_team"],
                    "away_team": pred["away_team"],
                    "predicted_outcome": pred["predicted_outcome"],
                    "confidence": f"{confidence:.0f}",
                    "confidence_class": confidence_class,
                    "kickoff": pred.get("kickoff", "TBD")
                })
        
        formatted_performance = None
        if performance:
            formatted_performance = {
                "total": performance.get("total_predictions", 0),
                "correct": performance.get("correct_predictions", 0),
                "accuracy": f"{performance.get('accuracy', 0)*100:.1f}",
                "roi": f"{performance.get('roi', 0)*100:.1f}"
            }
        
        # Determine title based on frequency
        now = datetime.now()
        if user.frequency == DigestFrequency.DAILY:
            title = "Daily Sports Digest"
            subtitle = now.strftime("%A, %B %d, %Y")
        else:
            title = "Weekly Sports Digest"
            week_start = now - timedelta(days=now.weekday())
            subtitle = f"Week of {week_start.strftime('%B %d, %Y')}"
        
        return template.render(
            title=title,
            subtitle=subtitle,
            value_bets=formatted_bets,
            predictions=formatted_predictions,
            performance=formatted_performance,
            upcoming_matches=upcoming_matches,
            unsubscribe_url="#",
            preferences_url="#"
        )
    
    def send_digest(
        self,
        user_id: int,
        **kwargs
    ) -> bool:
        """
        Send digest email to user.
        
        Args:
            user_id: User ID
            **kwargs: Data for digest compilation
            
        Returns:
            True if successful
        """
        if user_id not in self.user_preferences:
            logger.warning(f"User {user_id} not registered")
            return False
        
        user = self.user_preferences[user_id]
        
        try:
            html = self.compile_digest(user_id, **kwargs)
            
            subject = (
                "Your Daily Sports Digest" 
                if user.frequency == DigestFrequency.DAILY 
                else "Your Weekly Sports Digest"
            )
            
            success = self._send_email(user.email, subject, html)
            
            if success:
                # Clear pending alerts
                self.pending_alerts[user_id] = []
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send digest to user {user_id}: {e}")
            return False
    
    async def send_digest_batch(
        self,
        user_ids: List[int],
        **kwargs
    ) -> Dict[int, bool]:
        """
        Send digests to multiple users asynchronously.
        
        Args:
            user_ids: List of user IDs
            **kwargs: Data for digest compilation
            
        Returns:
            Dict of user_id -> success status
        """
        results = {}
        
        for user_id in user_ids:
            results[user_id] = self.send_digest(user_id, **kwargs)
            await asyncio.sleep(0.1)  # Rate limiting
        
        return results
    
    def get_pending_alerts(self, user_id: int) -> List[Alert]:
        """Get pending alerts for a user."""
        return self.pending_alerts.get(user_id, [])
    
    def clear_pending_alerts(self, user_id: int) -> None:
        """Clear pending alerts for a user."""
        self.pending_alerts[user_id] = []
    
    def get_users_for_digest(
        self,
        frequency: DigestFrequency
    ) -> List[int]:
        """Get users who should receive digest with given frequency."""
        return [
            user_id for user_id, prefs in self.user_preferences.items()
            if prefs.frequency == frequency
        ]
