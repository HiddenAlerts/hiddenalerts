from app.sources.rss_adapter import RSSAdapter


class FBINationalAdapter(RSSAdapter):
    """FBI National Press Releases RSS feed."""

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/national-press-releases/rss.xml"
        )
