"""Headers sent with every API response.

The API only returns JSON, calendar files and CSV, never a page, so the policy is to refuse
framing and sniffing and to keep patient data out of caches. Production adds HSTS.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

_COMMON_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
_HSTS = "max-age=31536000; includeSubDomains"

type Next = Callable[[Request], Awaitable[Response]]


def security_headers(*, hsts: bool) -> Callable[[Request, Next], Awaitable[Response]]:
    """Build the middleware. HSTS only makes sense where the API is served over HTTPS."""
    headers = {**_COMMON_HEADERS, **({"Strict-Transport-Security": _HSTS} if hsts else {})}

    async def middleware(request: Request, call_next: Next) -> Response:
        response = await call_next(request)
        for name, value in headers.items():
            response.headers.setdefault(name, value)
        return response

    return middleware
