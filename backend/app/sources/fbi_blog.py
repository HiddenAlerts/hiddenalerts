from app.sources.fbi_policy import FBIHostedContentMixin
from app.sources.rss_adapter import RSSAdapter


class FBIBlogAdapter(FBIHostedContentMixin, RSSAdapter):
    """FBI News Blog RSS feed — FBI-hosted articles only.

    The feed is currently valid but empty. That is a healthy state, not a
    failure: the source stays enabled so a future post is collected the day it
    appears.
    """

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.fbi.gov/feeds/news-blog/rss.xml"
        )
