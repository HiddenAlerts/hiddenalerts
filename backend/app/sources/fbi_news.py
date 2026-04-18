from app.sources.rss_adapter import RSSAdapter


class FBINewsAdapter(RSSAdapter):
    """FBI in the News RSS feed."""

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/fbi-in-the-news/rss.xml"
        )
