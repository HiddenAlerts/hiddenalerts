from app.sources.rss_adapter import RSSAdapter


class BleepingAdapter(RSSAdapter):
    """BleepingComputer RSS feed."""

    @property
    def rss_url(self) -> str:
        return (
            self.source.rss_url  # type: ignore[attr-defined]
            or "https://www.bleepingcomputer.com/feed/"
        )
