from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.settings import settings

# In-memory storage deliberately, not Redis: slowapi/limits does not
# degrade gracefully when its storage backend is unreachable (a Redis
# outage makes every request raise, not just fail open), which would turn
# a cache/queue hiccup into a total app outage. The trade-off is that
# limits are per-process rather than shared across replicas - acceptable
# for abuse protection, revisit only with a storage backend that fails
# open.
#
# default_limits applies to every route automatically; routes needing a
# stricter limit (expensive AI calls, auth brute-force protection) add
# their own @limiter.limit(...) decorator, which overrides the default for
# that route.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
