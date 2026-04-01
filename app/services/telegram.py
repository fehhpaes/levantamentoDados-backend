"""
Telegram Bot Service for Sports Alerts

Provides real-time notifications for:
- Value bet opportunities
- Match start alerts
- Odds movements
- Score updates
- Prediction results
"""

import httpx
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging
import html

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    LOW = 3
    MEDIUM = 2
    HIGH = 1
    URGENT = 0


class ParseMode(Enum):
    HTML = "HTML"
    MARKDOWN = "MarkdownV2"
    PLAIN = None


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    default_chat_id: Optional[str] = None
    rate_limit_per_second: float = 30  # Telegram API limit
    timeout: float = 30.0


@dataclass
class TelegramUser:
    """Telegram user subscription data."""
    user_id: int  # Our system user ID
    telegram_chat_id: str
    telegram_username: Optional[str] = None
    is_active: bool = True
    alert_types: List[str] = field(default_factory=list)
    min_edge: float = 0.05  # Minimum edge for value bet alerts
    favorite_teams: List[int] = field(default_factory=list)
    favorite_leagues: List[int] = field(default_factory=list)
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None
    language: str = "pt"  # pt, en, es


@dataclass
class TelegramMessage:
    """Message to be sent via Telegram."""
    chat_id: str
    text: str
    parse_mode: ParseMode = ParseMode.HTML
    disable_notification: bool = False
    reply_markup: Optional[Dict] = None
    priority: AlertPriority = AlertPriority.MEDIUM


class TelegramTemplates:
    """Message templates for different alert types."""
    
    # Value Bet Alert
    VALUE_BET_PT = """
<b>🎯 VALUE BET ENCONTRADO</b>

<b>Partida:</b> {home_team} vs {away_team}
<b>Liga:</b> {league}
<b>Horário:</b> {kickoff}

<b>📊 Mercado:</b> {market}
<b>💰 Odd:</b> {odds}
<b>📈 Probabilidade:</b> {probability}%
<b>✅ Edge:</b> {edge}%
<b>🎲 Stake Sugerido:</b> {stake}% da banca

<b>Confiança:</b> {"🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.5 else "🔴"} {confidence_pct}%
"""

    VALUE_BET_EN = """
<b>🎯 VALUE BET FOUND</b>

<b>Match:</b> {home_team} vs {away_team}
<b>League:</b> {league}
<b>Kickoff:</b> {kickoff}

<b>📊 Market:</b> {market}
<b>💰 Odds:</b> {odds}
<b>📈 Probability:</b> {probability}%
<b>✅ Edge:</b> {edge}%
<b>🎲 Suggested Stake:</b> {stake}% of bankroll

<b>Confidence:</b> {"🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.5 else "🔴"} {confidence_pct}%
"""

    # Match Start Alert
    MATCH_START_PT = """
<b>⚽ PARTIDA INICIANDO</b>

<b>{home_team}</b> vs <b>{away_team}</b>
<b>Liga:</b> {league}

<b>📊 Nossa Previsão:</b>
• Vitória Casa: {home_win}%
• Empate: {draw}%
• Vitória Fora: {away_win}%

<b>Melhor Odd:</b> {best_market} @ {best_odds}
"""

    MATCH_START_EN = """
<b>⚽ MATCH STARTING</b>

<b>{home_team}</b> vs <b>{away_team}</b>
<b>League:</b> {league}

<b>📊 Our Prediction:</b>
• Home Win: {home_win}%
• Draw: {draw}%
• Away Win: {away_win}%

<b>Best Odds:</b> {best_market} @ {best_odds}
"""

    # Live Score Update
    SCORE_UPDATE_PT = """
<b>⚽ GOL!</b>

<b>{home_team}</b> {home_score} - {away_score} <b>{away_team}</b>
<b>⏱️</b> {minute}'

<b>Marcador:</b> {scorer}
"""

    SCORE_UPDATE_EN = """
<b>⚽ GOAL!</b>

<b>{home_team}</b> {home_score} - {away_score} <b>{away_team}</b>
<b>⏱️</b> {minute}'

<b>Scorer:</b> {scorer}
"""

    # Odds Movement Alert
    ODDS_MOVEMENT_PT = """
<b>📉 MOVIMENTO DE ODDS</b>

<b>Partida:</b> {home_team} vs {away_team}
<b>Mercado:</b> {market}

<b>Odd Anterior:</b> {old_odds}
<b>Odd Atual:</b> {new_odds}
<b>Variação:</b> {direction} {change_pct}%

{analysis}
"""

    ODDS_MOVEMENT_EN = """
<b>📉 ODDS MOVEMENT</b>

<b>Match:</b> {home_team} vs {away_team}
<b>Market:</b> {market}

<b>Previous Odds:</b> {old_odds}
<b>Current Odds:</b> {new_odds}
<b>Change:</b> {direction} {change_pct}%

{analysis}
"""

    # Daily Summary
    DAILY_SUMMARY_PT = """
<b>📊 RESUMO DIÁRIO</b>
<b>{date}</b>

<b>Apostas do Dia:</b>
• Partidas: {matches_count}
• Value Bets: {value_bets_count}
• Previsões: {predictions_count}

<b>Performance:</b>
• Acertos: {wins}/{total} ({accuracy}%)
• ROI: {roi}%
• Lucro: R$ {profit}

<b>Top Pick:</b> {top_pick}
"""

    DAILY_SUMMARY_EN = """
<b>📊 DAILY SUMMARY</b>
<b>{date}</b>

<b>Today's Bets:</b>
• Matches: {matches_count}
• Value Bets: {value_bets_count}
• Predictions: {predictions_count}

<b>Performance:</b>
• Wins: {wins}/{total} ({accuracy}%)
• ROI: {roi}%
• Profit: ${profit}

<b>Top Pick:</b> {top_pick}
"""

    # Welcome Message
    WELCOME_PT = """
<b>🎉 Bem-vindo ao Sports Analytics Bot!</b>

Você está agora inscrito para receber:
✅ Alertas de Value Bets
✅ Previsões de Partidas
✅ Movimentos de Odds
✅ Atualizações de Placar (ao vivo)
✅ Resumos Diários

<b>Comandos disponíveis:</b>
/settings - Configurar alertas
/valuebets - Ver value bets atuais
/predictions - Ver previsões do dia
/stop - Pausar notificações
/help - Ajuda

Boa sorte! 🍀
"""

    WELCOME_EN = """
<b>🎉 Welcome to Sports Analytics Bot!</b>

You are now subscribed to receive:
✅ Value Bet Alerts
✅ Match Predictions
✅ Odds Movements
✅ Live Score Updates
✅ Daily Summaries

<b>Available commands:</b>
/settings - Configure alerts
/valuebets - View current value bets
/predictions - View today's predictions
/stop - Pause notifications
/help - Help

Good luck! 🍀
"""


class TelegramService:
    """
    Telegram Bot Service for sending sports alerts.
    
    Features:
    - Value bet notifications
    - Match alerts
    - Live score updates
    - Odds movement alerts
    - Daily/weekly summaries
    - User preference management
    - Rate limiting
    - Quiet hours support
    """
    
    TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram service.
        
        Args:
            config: Telegram bot configuration
        """
        self.config = config
        self.users: Dict[int, TelegramUser] = {}  # user_id -> TelegramUser
        self.chat_id_map: Dict[str, int] = {}  # telegram_chat_id -> user_id
        self._last_request_time: float = 0
        self._request_interval = 1.0 / config.rate_limit_per_second
        
    async def _make_request(
        self,
        method: str,
        data: Dict[str, Any]
    ) -> Dict:
        """
        Make request to Telegram API with rate limiting.
        
        Args:
            method: API method name
            data: Request data
            
        Returns:
            API response
        """
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._request_interval:
            await asyncio.sleep(self._request_interval - time_since_last)
        
        url = self.TELEGRAM_API_URL.format(
            token=self.config.bot_token,
            method=method
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, json=data)
                self._last_request_time = asyncio.get_event_loop().time()
                
                result = response.json()
                
                if not result.get("ok"):
                    logger.error(f"Telegram API error: {result.get('description')}")
                    return {"ok": False, "error": result.get("description")}
                
                return result
                
        except httpx.TimeoutException:
            logger.error(f"Telegram API timeout for {method}")
            return {"ok": False, "error": "Request timeout"}
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return {"ok": False, "error": str(e)}
    
    async def send_message(self, message: TelegramMessage) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            message: Message to send
            
        Returns:
            True if successful
        """
        data = {
            "chat_id": message.chat_id,
            "text": message.text,
            "disable_notification": message.disable_notification,
        }
        
        if message.parse_mode != ParseMode.PLAIN:
            data["parse_mode"] = message.parse_mode.value
        
        if message.reply_markup:
            data["reply_markup"] = message.reply_markup
        
        result = await self._make_request("sendMessage", data)
        return result.get("ok", False)
    
    async def send_messages_batch(
        self,
        messages: List[TelegramMessage]
    ) -> Dict[str, bool]:
        """
        Send multiple messages with rate limiting.
        
        Args:
            messages: List of messages to send
            
        Returns:
            Dict of chat_id -> success status
        """
        results = {}
        
        # Sort by priority
        sorted_messages = sorted(messages, key=lambda m: m.priority.value)
        
        for message in sorted_messages:
            results[message.chat_id] = await self.send_message(message)
        
        return results
    
    def register_user(self, user: TelegramUser) -> None:
        """Register a user for notifications."""
        self.users[user.user_id] = user
        self.chat_id_map[user.telegram_chat_id] = user.user_id
        logger.info(f"Registered user {user.user_id} for Telegram alerts")
    
    def unregister_user(self, user_id: int) -> None:
        """Unregister a user from notifications."""
        if user_id in self.users:
            user = self.users[user_id]
            del self.chat_id_map[user.telegram_chat_id]
            del self.users[user_id]
            logger.info(f"Unregistered user {user_id} from Telegram alerts")
    
    def _is_quiet_hours(self, user: TelegramUser) -> bool:
        """Check if current time is within user's quiet hours."""
        if user.quiet_hours_start is None or user.quiet_hours_end is None:
            return False
        
        current_hour = datetime.now().hour
        start = user.quiet_hours_start
        end = user.quiet_hours_end
        
        if start <= end:
            return start <= current_hour < end
        else:  # Crosses midnight
            return current_hour >= start or current_hour < end
    
    def _get_template(
        self,
        template_name: str,
        language: str = "pt"
    ) -> str:
        """Get template by name and language."""
        attr_name = f"{template_name}_{language.upper()}"
        return getattr(TelegramTemplates, attr_name, getattr(TelegramTemplates, f"{template_name}_EN"))
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return html.escape(text)
    
    async def send_value_bet_alert(
        self,
        user_ids: Optional[List[int]] = None,
        home_team: str = "",
        away_team: str = "",
        league: str = "",
        kickoff: str = "",
        market: str = "",
        odds: float = 0.0,
        probability: float = 0.0,
        edge: float = 0.0,
        stake: float = 0.0,
        confidence: float = 0.0
    ) -> Dict[int, bool]:
        """
        Send value bet alert to users.
        
        Args:
            user_ids: Specific user IDs (None = all subscribed)
            ... bet details
            
        Returns:
            Dict of user_id -> success status
        """
        results = {}
        target_users = user_ids or list(self.users.keys())
        
        for user_id in target_users:
            if user_id not in self.users:
                continue
                
            user = self.users[user_id]
            
            # Check if user wants value bet alerts
            if "value_bet" not in user.alert_types and user.alert_types:
                continue
            
            # Check minimum edge preference
            if edge < user.min_edge:
                continue
            
            # Check quiet hours
            if self._is_quiet_hours(user):
                continue
            
            # Format message
            template = self._get_template("VALUE_BET", user.language)
            
            # Format confidence emoji
            confidence_emoji = "🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.5 else "🔴"
            
            text = template.format(
                home_team=self._escape_html(home_team),
                away_team=self._escape_html(away_team),
                league=self._escape_html(league),
                kickoff=kickoff,
                market=self._escape_html(market),
                odds=f"{odds:.2f}",
                probability=f"{probability*100:.1f}",
                edge=f"{edge*100:.1f}",
                stake=f"{stake*100:.1f}",
                confidence=confidence,
                confidence_pct=f"{confidence*100:.0f}"
            )
            
            # Replace conditional emoji (simple approach)
            text = text.replace(
                '{"🟢" if confidence >= 0.7 else "🟡" if confidence >= 0.5 else "🔴"}',
                confidence_emoji
            )
            
            message = TelegramMessage(
                chat_id=user.telegram_chat_id,
                text=text,
                priority=AlertPriority.HIGH if edge > 0.10 else AlertPriority.MEDIUM
            )
            
            results[user_id] = await self.send_message(message)
        
        return results
    
    async def send_match_start_alert(
        self,
        user_ids: Optional[List[int]] = None,
        home_team: str = "",
        away_team: str = "",
        league: str = "",
        home_win: float = 0.0,
        draw: float = 0.0,
        away_win: float = 0.0,
        best_market: str = "",
        best_odds: float = 0.0,
        home_team_id: Optional[int] = None,
        away_team_id: Optional[int] = None,
        league_id: Optional[int] = None
    ) -> Dict[int, bool]:
        """Send match start alert to users."""
        results = {}
        target_users = user_ids or list(self.users.keys())
        
        for user_id in target_users:
            if user_id not in self.users:
                continue
                
            user = self.users[user_id]
            
            # Check if user wants match alerts
            if "match_start" not in user.alert_types and user.alert_types:
                continue
            
            # Check if user follows this team/league
            if user.favorite_teams or user.favorite_leagues:
                team_match = (
                    home_team_id in user.favorite_teams or
                    away_team_id in user.favorite_teams
                )
                league_match = league_id in user.favorite_leagues
                
                if not (team_match or league_match):
                    continue
            
            # Check quiet hours
            if self._is_quiet_hours(user):
                continue
            
            template = self._get_template("MATCH_START", user.language)
            
            text = template.format(
                home_team=self._escape_html(home_team),
                away_team=self._escape_html(away_team),
                league=self._escape_html(league),
                home_win=f"{home_win*100:.0f}",
                draw=f"{draw*100:.0f}",
                away_win=f"{away_win*100:.0f}",
                best_market=self._escape_html(best_market),
                best_odds=f"{best_odds:.2f}"
            )
            
            message = TelegramMessage(
                chat_id=user.telegram_chat_id,
                text=text,
                priority=AlertPriority.MEDIUM
            )
            
            results[user_id] = await self.send_message(message)
        
        return results
    
    async def send_score_update(
        self,
        user_ids: Optional[List[int]] = None,
        home_team: str = "",
        away_team: str = "",
        home_score: int = 0,
        away_score: int = 0,
        minute: int = 0,
        scorer: str = "",
        home_team_id: Optional[int] = None,
        away_team_id: Optional[int] = None
    ) -> Dict[int, bool]:
        """Send live score update to users."""
        results = {}
        target_users = user_ids or list(self.users.keys())
        
        for user_id in target_users:
            if user_id not in self.users:
                continue
                
            user = self.users[user_id]
            
            # Check if user wants live updates
            if "live_score" not in user.alert_types and user.alert_types:
                continue
            
            # Check if user follows these teams
            if user.favorite_teams:
                if home_team_id not in user.favorite_teams and away_team_id not in user.favorite_teams:
                    continue
            
            template = self._get_template("SCORE_UPDATE", user.language)
            
            text = template.format(
                home_team=self._escape_html(home_team),
                away_team=self._escape_html(away_team),
                home_score=home_score,
                away_score=away_score,
                minute=minute,
                scorer=self._escape_html(scorer) if scorer else "N/A"
            )
            
            message = TelegramMessage(
                chat_id=user.telegram_chat_id,
                text=text,
                priority=AlertPriority.LOW,
                disable_notification=True  # Silent for live updates
            )
            
            results[user_id] = await self.send_message(message)
        
        return results
    
    async def send_odds_movement_alert(
        self,
        user_ids: Optional[List[int]] = None,
        home_team: str = "",
        away_team: str = "",
        market: str = "",
        old_odds: float = 0.0,
        new_odds: float = 0.0,
        analysis: str = ""
    ) -> Dict[int, bool]:
        """Send odds movement alert to users."""
        results = {}
        target_users = user_ids or list(self.users.keys())
        
        change_pct = abs(new_odds - old_odds) / old_odds * 100
        direction = "📈" if new_odds > old_odds else "📉"
        
        for user_id in target_users:
            if user_id not in self.users:
                continue
                
            user = self.users[user_id]
            
            # Check if user wants odds movement alerts
            if "odds_movement" not in user.alert_types and user.alert_types:
                continue
            
            # Only alert for significant movements (>5%)
            if change_pct < 5:
                continue
            
            if self._is_quiet_hours(user):
                continue
            
            template = self._get_template("ODDS_MOVEMENT", user.language)
            
            text = template.format(
                home_team=self._escape_html(home_team),
                away_team=self._escape_html(away_team),
                market=self._escape_html(market),
                old_odds=f"{old_odds:.2f}",
                new_odds=f"{new_odds:.2f}",
                direction=direction,
                change_pct=f"{change_pct:.1f}",
                analysis=self._escape_html(analysis) if analysis else ""
            )
            
            message = TelegramMessage(
                chat_id=user.telegram_chat_id,
                text=text,
                priority=AlertPriority.MEDIUM if change_pct > 10 else AlertPriority.LOW
            )
            
            results[user_id] = await self.send_message(message)
        
        return results
    
    async def send_daily_summary(
        self,
        user_ids: Optional[List[int]] = None,
        date: str = "",
        matches_count: int = 0,
        value_bets_count: int = 0,
        predictions_count: int = 0,
        wins: int = 0,
        total: int = 0,
        accuracy: float = 0.0,
        roi: float = 0.0,
        profit: float = 0.0,
        top_pick: str = ""
    ) -> Dict[int, bool]:
        """Send daily summary to users."""
        results = {}
        target_users = user_ids or list(self.users.keys())
        
        for user_id in target_users:
            if user_id not in self.users:
                continue
                
            user = self.users[user_id]
            
            # Check if user wants daily summaries
            if "daily_summary" not in user.alert_types and user.alert_types:
                continue
            
            template = self._get_template("DAILY_SUMMARY", user.language)
            
            text = template.format(
                date=date or datetime.now().strftime("%d/%m/%Y"),
                matches_count=matches_count,
                value_bets_count=value_bets_count,
                predictions_count=predictions_count,
                wins=wins,
                total=total,
                accuracy=f"{accuracy*100:.1f}" if accuracy else "N/A",
                roi=f"{roi*100:.1f}" if roi else "N/A",
                profit=f"{profit:.2f}",
                top_pick=self._escape_html(top_pick) if top_pick else "N/A"
            )
            
            message = TelegramMessage(
                chat_id=user.telegram_chat_id,
                text=text,
                priority=AlertPriority.LOW
            )
            
            results[user_id] = await self.send_message(message)
        
        return results
    
    async def send_welcome_message(self, user_id: int) -> bool:
        """Send welcome message to new user."""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        template = self._get_template("WELCOME", user.language)
        
        message = TelegramMessage(
            chat_id=user.telegram_chat_id,
            text=template,
            priority=AlertPriority.HIGH
        )
        
        return await self.send_message(message)
    
    async def get_bot_info(self) -> Optional[Dict]:
        """Get bot information."""
        result = await self._make_request("getMe", {})
        if result.get("ok"):
            return result.get("result")
        return None
    
    async def set_webhook(self, url: str) -> bool:
        """Set webhook URL for receiving updates."""
        result = await self._make_request("setWebhook", {"url": url})
        return result.get("ok", False)
    
    async def delete_webhook(self) -> bool:
        """Delete webhook."""
        result = await self._make_request("deleteWebhook", {})
        return result.get("ok", False)
    
    def get_user_by_chat_id(self, chat_id: str) -> Optional[TelegramUser]:
        """Get user by Telegram chat ID."""
        user_id = self.chat_id_map.get(chat_id)
        if user_id:
            return self.users.get(user_id)
        return None
    
    def update_user_preferences(
        self,
        user_id: int,
        **kwargs
    ) -> bool:
        """Update user notification preferences."""
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        return True
    
    def get_active_users_count(self) -> int:
        """Get count of active users."""
        return sum(1 for u in self.users.values() if u.is_active)
    
    def get_users_for_alert_type(self, alert_type: str) -> List[int]:
        """Get user IDs subscribed to a specific alert type."""
        return [
            user_id for user_id, user in self.users.items()
            if user.is_active and (not user.alert_types or alert_type in user.alert_types)
        ]
