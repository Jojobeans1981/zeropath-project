"""
Security middleware: rate limiting + security headers.
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter. Per-IP, sliding window."""

    def __init__(self, app, requests_per_minute: int = 60, scan_requests_per_minute: int = 5):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.scan_requests_per_minute = scan_requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, ip: str, limit: int) -> bool:
        now = time.time()
        window = now - 60
        self.requests[ip] = [t for t in self.requests[ip] if t > window]
        if len(self.requests[ip]) >= limit:
            return True
        self.requests[ip].append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        ip = self._get_client_ip(request)

        # Stricter limit for scan creation
        if request.url.path == "/api/scans/" and request.method == "POST":
            if self._is_rate_limited(f"{ip}:scan", self.scan_requests_per_minute):
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "RATE_LIMITED", "message": "Too many scan requests. Please wait a minute."}},
                )

        # General rate limit
        if self._is_rate_limited(ip, self.requests_per_minute):
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down."}},
            )

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
