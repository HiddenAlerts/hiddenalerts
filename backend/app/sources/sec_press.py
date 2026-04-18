from app.sources.rss_adapter import RSSAdapter


class SECPressAdapter(RSSAdapter):
    """SEC Press Releases — RSS feed at sec.gov."""

    @property
    def rss_url(self) -> str:
        return self.source.rss_url or "https://www.sec.gov/news/pressreleases.rss"  # type: ignore[attr-defined]
