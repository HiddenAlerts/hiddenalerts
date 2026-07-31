"""Canonical-source policy for the FBI feeds.

Ken's approved decision: **DOJ is canonical for anything ultimately hosted on
justice.gov**, and the FBI sources must exclude any item whose final destination
is DOJ or any other external site.

The 2026-07-28 audit showed why. FBI feed entries routinely redirect to
justice.gov — ``/opa/`` pages fetch normally while ``/usao-*`` pages sit behind an
interstitial — so following those redirects would collect the same press release
twice, once as DOJ and once as FBI, under two different URLs that URL-hash
deduplication cannot reconcile.

The same audit measured the FBI feed summaries: FBI National's were suitable for
discovery but not for reliable AI analysis, and FBI in the News scored roughly
0.3% AI-suitable. So a failed article fetch has nothing worth substituting, and
these sources store full FBI-hosted article text or nothing at all.
"""
from app.sources.base import RawItemStub

#: FBI content lives here. Matching covers the domain and its subdomains, so
#: ``www.fbi.gov`` and a future ``newsroom.fbi.gov`` are both in scope while
#: ``evilfbi.gov`` and ``fbi.gov.example.com`` are not.
FBI_DOMAINS: tuple[str, ...] = ("fbi.gov",)


class FBIHostedContentMixin:
    """Collect only FBI-hosted articles, and never substitute a feed summary.

    Mixed into every FBI adapter ahead of ``RSSAdapter`` so both rules are stated
    once. Discovery is untouched: the feed is still read normally, and a stub
    pointing somewhere external is still emitted — it is the *article* request
    that refuses to leave fbi.gov, before any packet is sent to the destination.
    """

    allowed_article_domains = FBI_DOMAINS

    def summary_fallback(self, stub: RawItemStub, error: Exception | None) -> str | None:
        """Never. Either the FBI-hosted article was retrieved, or there is no item.

        An excluded destination belongs to another source, and the audited feed
        summaries are too thin to analyse — in both cases the item is left
        unstored and its URL stays retriable.
        """
        return None
