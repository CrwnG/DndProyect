"""
Rate limiting and cost tracking for AI DM API calls.

Implements request rate limiting (RPM, RPH) and estimated cost tracking
to prevent runaway API usage and costs.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Track API usage statistics."""
    requests_total: int = 0
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_today: int = 0
    tokens_used_total: int = 0
    tokens_used_this_hour: int = 0
    tokens_used_today: int = 0
    last_request_time: Optional[datetime] = None
    minute_reset_time: datetime = field(default_factory=datetime.utcnow)
    hour_reset_time: datetime = field(default_factory=datetime.utcnow)
    day_reset_time: datetime = field(default_factory=datetime.utcnow)
    estimated_cost_today: float = 0.0
    estimated_cost_total: float = 0.0

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "requests_total": self.requests_total,
            "requests_this_minute": self.requests_this_minute,
            "requests_this_hour": self.requests_this_hour,
            "requests_today": self.requests_today,
            "tokens_used_total": self.tokens_used_total,
            "tokens_used_this_hour": self.tokens_used_this_hour,
            "tokens_used_today": self.tokens_used_today,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "estimated_cost_today": round(self.estimated_cost_today, 4),
            "estimated_cost_total": round(self.estimated_cost_total, 4),
        }


class AIDMRateLimiter:
    """
    Rate limiter for AI DM API calls with cost tracking.

    Implements multiple rate limiting windows:
    - Per minute (soft limit, returns warning)
    - Per hour (hard limit, blocks requests)
    - Daily cost cap (hard limit, blocks requests)

    Also tracks estimated API costs based on token usage.
    """

    # Claude Sonnet pricing (approximate, as of 2024)
    # Input: $3 per million tokens
    # Output: $15 per million tokens
    COST_PER_1K_INPUT_TOKENS = 0.003
    COST_PER_1K_OUTPUT_TOKENS = 0.015

    def __init__(
        self,
        requests_per_minute: int = 20,
        requests_per_hour: int = 200,
        daily_cost_cap_usd: float = 5.0,
    ):
        """
        Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute (soft limit)
            requests_per_hour: Maximum requests per hour (hard limit)
            daily_cost_cap_usd: Maximum daily cost in USD
        """
        self._rpm_limit = requests_per_minute
        self._rph_limit = requests_per_hour
        self._daily_cap = daily_cost_cap_usd
        self._stats = UsageStats()
        self._lock = threading.Lock()

        logger.info(
            f"AI DM Rate Limiter initialized: "
            f"rpm={requests_per_minute}, rph={requests_per_hour}, "
            f"daily_cap=${daily_cost_cap_usd}"
        )

    def can_make_request(self) -> Tuple[bool, str, bool]:
        """
        Check if a request is allowed.

        Returns:
            Tuple of (allowed, reason, is_soft_limit):
            - allowed: Whether the request should proceed
            - reason: Human-readable reason if blocked
            - is_soft_limit: True if this is a warning (still allowed)
        """
        with self._lock:
            self._reset_counters_if_needed()

            # Check daily cost cap (hard limit)
            if self._stats.estimated_cost_today >= self._daily_cap:
                logger.warning(f"Daily cost cap reached: ${self._stats.estimated_cost_today:.2f}")
                return False, f"Daily cost cap of ${self._daily_cap:.2f} reached", False

            # Check hourly limit (hard limit)
            if self._stats.requests_this_hour >= self._rph_limit:
                logger.warning(f"Hourly rate limit reached: {self._stats.requests_this_hour}/{self._rph_limit}")
                return False, f"Hourly limit of {self._rph_limit} requests reached", False

            # Check minute limit (soft limit - warning only)
            if self._stats.requests_this_minute >= self._rpm_limit:
                logger.debug(f"Minute rate limit reached: {self._stats.requests_this_minute}/{self._rpm_limit}")
                return True, f"Approaching rate limit ({self._stats.requests_this_minute}/{self._rpm_limit} RPM)", True

            return True, "OK", False

    def record_request(
        self,
        input_tokens: int = 500,
        output_tokens: int = 150,
        success: bool = True,
    ) -> Dict:
        """
        Record a completed API request.

        Args:
            input_tokens: Approximate input tokens used
            output_tokens: Approximate output tokens used
            success: Whether the request succeeded

        Returns:
            Dictionary with updated stats summary
        """
        with self._lock:
            self._reset_counters_if_needed()

            self._stats.requests_total += 1
            self._stats.requests_this_minute += 1
            self._stats.requests_this_hour += 1
            self._stats.requests_today += 1
            self._stats.last_request_time = datetime.utcnow()

            if success:
                total_tokens = input_tokens + output_tokens
                self._stats.tokens_used_total += total_tokens
                self._stats.tokens_used_this_hour += total_tokens
                self._stats.tokens_used_today += total_tokens

                # Calculate cost
                cost = (
                    (input_tokens / 1000) * self.COST_PER_1K_INPUT_TOKENS +
                    (output_tokens / 1000) * self.COST_PER_1K_OUTPUT_TOKENS
                )
                self._stats.estimated_cost_today += cost
                self._stats.estimated_cost_total += cost

                logger.debug(
                    f"AI DM request recorded: {total_tokens} tokens, "
                    f"cost ${cost:.4f}, today total ${self._stats.estimated_cost_today:.2f}"
                )

            return {
                "requests_this_minute": self._stats.requests_this_minute,
                "requests_this_hour": self._stats.requests_this_hour,
                "cost_today": round(self._stats.estimated_cost_today, 4),
            }

    def _reset_counters_if_needed(self) -> None:
        """Reset counters based on time windows."""
        now = datetime.utcnow()

        # Reset minute counter
        if now - self._stats.minute_reset_time > timedelta(minutes=1):
            self._stats.requests_this_minute = 0
            self._stats.minute_reset_time = now

        # Reset hour counter
        if now - self._stats.hour_reset_time > timedelta(hours=1):
            self._stats.requests_this_hour = 0
            self._stats.tokens_used_this_hour = 0
            self._stats.hour_reset_time = now

        # Reset day counter
        if now - self._stats.day_reset_time > timedelta(hours=24):
            self._stats.requests_today = 0
            self._stats.tokens_used_today = 0
            self._stats.estimated_cost_today = 0.0
            self._stats.day_reset_time = now
            logger.info("Daily usage counters reset")

    def get_stats(self) -> Dict:
        """
        Get current usage statistics.

        Returns:
            Dictionary with all usage stats
        """
        with self._lock:
            self._reset_counters_if_needed()

            return {
                **self._stats.to_dict(),
                "limits": {
                    "requests_per_minute": self._rpm_limit,
                    "requests_per_hour": self._rph_limit,
                    "daily_cost_cap_usd": self._daily_cap,
                },
                "remaining": {
                    "requests_this_minute": max(0, self._rpm_limit - self._stats.requests_this_minute),
                    "requests_this_hour": max(0, self._rph_limit - self._stats.requests_this_hour),
                    "daily_budget_usd": round(max(0, self._daily_cap - self._stats.estimated_cost_today), 4),
                },
                "time_until_reset": {
                    "minute_seconds": max(0, 60 - (datetime.utcnow() - self._stats.minute_reset_time).seconds),
                    "hour_minutes": max(0, 60 - int((datetime.utcnow() - self._stats.hour_reset_time).seconds / 60)),
                },
            }

    def set_limits(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        daily_cost_cap_usd: Optional[float] = None,
    ) -> Dict:
        """
        Update rate limits.

        Args:
            requests_per_minute: New RPM limit (optional)
            requests_per_hour: New RPH limit (optional)
            daily_cost_cap_usd: New daily cost cap (optional)

        Returns:
            Dictionary with updated limits
        """
        with self._lock:
            if requests_per_minute is not None:
                self._rpm_limit = requests_per_minute
            if requests_per_hour is not None:
                self._rph_limit = requests_per_hour
            if daily_cost_cap_usd is not None:
                self._daily_cap = daily_cost_cap_usd

            logger.info(
                f"Rate limits updated: rpm={self._rpm_limit}, "
                f"rph={self._rph_limit}, daily_cap=${self._daily_cap}"
            )

            return {
                "requests_per_minute": self._rpm_limit,
                "requests_per_hour": self._rph_limit,
                "daily_cost_cap_usd": self._daily_cap,
            }

    def reset_daily_counters(self) -> None:
        """Manually reset daily counters (for admin use)."""
        with self._lock:
            self._stats.requests_today = 0
            self._stats.tokens_used_today = 0
            self._stats.estimated_cost_today = 0.0
            self._stats.day_reset_time = datetime.utcnow()
            logger.info("Daily counters manually reset")

    def estimate_cost(self, input_text: str, max_output_tokens: int = 500) -> float:
        """
        Estimate cost for a potential request.

        Args:
            input_text: The input prompt text
            max_output_tokens: Expected maximum output tokens

        Returns:
            Estimated cost in USD
        """
        # Rough estimate: ~4 characters per token
        estimated_input_tokens = len(input_text) // 4
        return (
            (estimated_input_tokens / 1000) * self.COST_PER_1K_INPUT_TOKENS +
            (max_output_tokens / 1000) * self.COST_PER_1K_OUTPUT_TOKENS
        )
