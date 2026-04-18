import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser


# Query parameters that are tracking noise — strip them from URLs
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "ref", "source", "via", "fbclid", "gclid", "mc_cid", "mc_eid",
})


def normalize_url(url: str) -> str:
    """Strip tracking params, fragment, normalize scheme to lowercase."""
    url = url.strip()
    parsed = urlparse(url)
    clean_params = [
        (k, v) for k, v in parse_qsl(parsed.query)
        if k.lower() not in _TRACKING_PARAMS
    ]
    clean_query = urlencode(clean_params)
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        clean_query,
        "",  # drop fragment
    ))
    return normalized


def compute_url_hash(url: str) -> str:
    """SHA-256 of normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_content_hash(text: str) -> str:
    """SHA-256 of whitespace-normalized lowercase text."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_text_from_html(html: str) -> str:
    """Strip tags, scripts, styles. Return clean readable text."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return " ".join(text.split())


def parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a naive UTC datetime. Returns None on failure."""
    if not date_str:
        return None
    try:
        import calendar
        dt = dateutil_parser.parse(date_str, fuzzy=True)
        # Store as naive UTC — columns are TIMESTAMP WITHOUT TIME ZONE
        if dt.tzinfo is not None:
            dt = datetime.utcfromtimestamp(calendar.timegm(dt.utctimetuple()))
        return dt
    except Exception:
        return None
