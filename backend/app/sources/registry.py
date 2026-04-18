from app.sources.base import BaseSourceAdapter
from app.sources.bleeping import BleepingAdapter
from app.sources.doj_press import DOJPressAdapter
from app.sources.fbi_blog import FBIBlogAdapter
from app.sources.fbi_national import FBINationalAdapter
from app.sources.fbi_news import FBINewsAdapter
from app.sources.fincen_press import FinCENPressAdapter
from app.sources.ftc_feeds import FTCFeedsAdapter
from app.sources.ic3_alerts import IC3AlertsAdapter
from app.sources.krebs import KrebsAdapter
from app.sources.sec_press import SECPressAdapter

ADAPTER_REGISTRY: dict[str, type[BaseSourceAdapter]] = {
    "sec_press.SECPressAdapter": SECPressAdapter,
    "ftc_feeds.FTCFeedsAdapter": FTCFeedsAdapter,
    "fincen_press.FinCENPressAdapter": FinCENPressAdapter,
    "ic3_alerts.IC3AlertsAdapter": IC3AlertsAdapter,
    "fbi_national.FBINationalAdapter": FBINationalAdapter,
    "fbi_blog.FBIBlogAdapter": FBIBlogAdapter,
    "fbi_news.FBINewsAdapter": FBINewsAdapter,
    "doj_press.DOJPressAdapter": DOJPressAdapter,
    "krebs.KrebsAdapter": KrebsAdapter,
    "bleeping.BleepingAdapter": BleepingAdapter,
}


def get_adapter(source: object) -> BaseSourceAdapter:
    """Instantiate the correct adapter for a given Source ORM object."""
    adapter_class_key = source.adapter_class  # type: ignore[attr-defined]
    cls = ADAPTER_REGISTRY.get(adapter_class_key)
    if cls is None:
        raise ValueError(
            f"Unknown adapter class '{adapter_class_key}'. "
            f"Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    return cls(source)
