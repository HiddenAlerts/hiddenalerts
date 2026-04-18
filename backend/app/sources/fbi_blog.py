from app.sources.rss_adapter import RSSAdapter


class FBIBlogAdapter(RSSAdapter):
    """FBI News Blog RSS feed."""

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/news-blog/rss.xml"
        )
