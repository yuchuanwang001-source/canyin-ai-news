import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "spm",
    "from",
}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in TRACKING_PARAMETERS
        )
    )
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            query,
            "",
        )
    )


def article_fingerprint(title: str, source: str) -> str:
    normalized = re.sub(r"[\W_]+", "", title, flags=re.UNICODE).lower()
    payload = f"{source.strip().lower()}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def event_fingerprint(title: str) -> str:
    normalized = re.sub(r"[\W_]+", "", title, flags=re.UNICODE).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
