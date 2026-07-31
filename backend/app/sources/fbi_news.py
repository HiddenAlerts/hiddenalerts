from app.sources.fbi_policy import FBIHostedContentMixin
from app.sources.rss_adapter import RSSAdapter


class FBINewsAdapter(FBIHostedContentMixin, RSSAdapter):
    """FBI in the News RSS feed — FBI-hosted articles only.

    Most entries point at externally hosted coverage; those are excluded at the
    article boundary rather than collected under an FBI identity.
    """

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/fbi-in-the-news/rss.xml"
        )
