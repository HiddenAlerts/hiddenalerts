from app.sources.fbi_policy import FBIHostedContentMixin
from app.sources.rss_adapter import RSSAdapter


class FBINationalAdapter(FBIHostedContentMixin, RSSAdapter):
    """FBI National Press Releases RSS feed — FBI-hosted articles only."""

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/national-press-releases/rss.xml"
        )
