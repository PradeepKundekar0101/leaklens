"""slowapi rate limiter: applied to login and to every LLM-backed endpoint."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().app_env != "test")

LOGIN_LIMIT = "10/minute"
LLM_LIMIT = "30/minute"
