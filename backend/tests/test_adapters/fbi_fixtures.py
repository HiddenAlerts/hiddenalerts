"""Sanitized FBI fixtures for the canonical-source destination policy.

Structure only — feed shape, the fbi.gov → justice.gov redirect chain the audit
observed, and the deceptive-host shapes the domain rule must reject. All prose is
short synthetic text.
"""

# --- Hosts and URLs -------------------------------------------------------

FBI_NATIONAL_FEED = "https://www.fbi.gov/feeds/national-press-releases/rss.xml"
FBI_NEWS_FEED = "https://www.fbi.gov/feeds/fbi-in-the-news/rss.xml"
FBI_BLOG_FEED = "https://www.fbi.gov/feeds/news-blog/rss.xml"

# Stays on fbi.gov — collectible.
FBI_DIRECT_URL = "https://www.fbi.gov/news/press-releases/man-sentenced-wire-fraud"
FBI_DIRECT_URL_2 = "https://www.fbi.gov/news/press-releases/two-charged-romance-scam"
# Same-domain redirect (trailing-slash canonicalization).
FBI_SAME_HOST_REDIRECT = "https://www.fbi.gov/news/press-releases/moved-release"
FBI_SAME_HOST_TARGET = "https://www.fbi.gov/news/press-releases/moved-release/"
# Redirect to a genuine fbi.gov subdomain — still collectible.
FBI_SUBDOMAIN_REDIRECT = "https://www.fbi.gov/news/press-releases/newsroom-item"
FBI_SUBDOMAIN_TARGET = "https://newsroom.fbi.gov/releases/newsroom-item"

# Redirects that must be refused before the destination is contacted.
FBI_TO_DOJ_URL = "https://www.fbi.gov/news/press-releases/joint-doj-announcement"
DOJ_TARGET = "https://www.justice.gov/news/press-release-joint-announcement"
FBI_TO_DOJ_OPA_URL = "https://www.fbi.gov/news/press-releases/opa-announcement"
DOJ_OPA_TARGET = "https://www.justice.gov/opa/pr/national-security-indictment"
FBI_TO_DOJ_USAO_URL = "https://www.fbi.gov/news/press-releases/district-announcement"
DOJ_USAO_TARGET = "https://www.justice.gov/usao-edny/pr/two-men-charged-conspiracy"
FBI_TO_IC3_URL = "https://www.fbi.gov/news/press-releases/ic3-annual-report"
IC3_TARGET = "https://www.ic3.gov/AnnualReport/Reports/2026_IC3Report.pdf"
FBI_TO_TREASURY_URL = "https://www.fbi.gov/news/press-releases/joint-treasury-action"
TREASURY_TARGET = "https://home.treasury.gov/news/press-releases/tr2026-0721"

# Multi-hop: fbi.gov → fbi.gov → justice.gov. The chain must stop at hop 2,
# before justice.gov is requested.
FBI_MULTIHOP_URL = "https://www.fbi.gov/news/press-releases/multi-hop-release"
FBI_MULTIHOP_MIDDLE = "https://www.fbi.gov/news/press-releases/multi-hop-release-v2"

# Deceptive hosts: none of these is fbi.gov or a subdomain of it.
DECEPTIVE_SUFFIX_URL = "https://fbi.gov.example.com/news/press-releases/fake"
DECEPTIVE_PREFIX_URL = "https://evilfbi.gov/news/press-releases/fake"
DECEPTIVE_DASH_URL = "https://fbi-gov.example/news/press-releases/fake"
FBI_TO_DECEPTIVE_URL = "https://www.fbi.gov/news/press-releases/lookalike-redirect"

# A feed entry that links straight to an external site, no redirect involved.
EXTERNAL_FEED_LINK = "https://www.reuters.com/legal/fbi-operation-coverage-2026"

# Carries a query string that must never reach a log line or an exception.
FBI_SECRET_QUERY_URL = (
    "https://www.fbi.gov/news/press-releases/tracked-release?token=SUPERSECRET123"
)


# --- Feed building --------------------------------------------------------

PUB_DATE = "Tue, 21 Jul 2026 13:00:00 -0400"

# Audited as discovery-grade only: usable to find an item, too thin to analyse.
WEAK_FBI_SUMMARY = (
    "A federal jury returned a verdict today in the District of Example."
)


def _item(title, link, pub_date=PUB_DATE, description=WEAK_FBI_SUMMARY):
    return (
        "<item>"
        f"<title>{title}</title><link>{link}</link>"
        f"<pubDate>{pub_date}</pubDate>"
        f"<description><![CDATA[{description}]]></description>"
        f"<guid isPermaLink='true'>{link}</guid>"
        "</item>"
    )


def feed(*items: str, title="FBI Press Releases") -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>{title}</title><link>https://www.fbi.gov/news</link>"
        "<description>Synthetic FBI feed</description>"
        + "".join(items)
        + "</channel></rss>"
    )


ITEM_DIRECT = _item("Man Sentenced for Wire Fraud", FBI_DIRECT_URL)
ITEM_DIRECT_2 = _item("Two Charged in a Romance Scam", FBI_DIRECT_URL_2)
ITEM_TO_DOJ = _item("Joint Announcement With the Department", FBI_TO_DOJ_URL)
ITEM_TO_DOJ_OPA = _item("National Security Indictment Unsealed", FBI_TO_DOJ_OPA_URL)
ITEM_TO_DOJ_USAO = _item("District Charges Two in Conspiracy", FBI_TO_DOJ_USAO_URL)
ITEM_TO_IC3 = _item("IC3 Releases Its Annual Report", FBI_TO_IC3_URL)
ITEM_TO_TREASURY = _item("Joint Action With Treasury", FBI_TO_TREASURY_URL)
ITEM_EXTERNAL_LINK = _item("Coverage of a Recent Operation", EXTERNAL_FEED_LINK)
ITEM_SUBDOMAIN = _item("Item Moved to the Newsroom", FBI_SUBDOMAIN_REDIRECT)
ITEM_SAME_HOST = _item("Release With a Canonical Slash", FBI_SAME_HOST_REDIRECT)

# FBI National: one collectible item, three DOJ redirects, one direct external.
FBI_NATIONAL_FEED_BODY = feed(
    ITEM_DIRECT, ITEM_TO_DOJ, ITEM_TO_DOJ_OPA, ITEM_TO_DOJ_USAO, ITEM_EXTERNAL_LINK
)
# FBI in the News: mostly externally hosted coverage, one FBI-hosted release.
FBI_NEWS_FEED_BODY = feed(
    ITEM_DIRECT_2, ITEM_TO_DOJ_USAO, ITEM_TO_IC3, ITEM_EXTERNAL_LINK,
    title="FBI in the News",
)
# Valid, structurally complete, and empty — the current FBI News Blog state.
FBI_BLOG_EMPTY_FEED = feed(title="FBI News Blog")
# The same blog once it has a post, and once it has an externally hosted one.
FBI_BLOG_FUTURE_FEED = feed(ITEM_DIRECT, title="FBI News Blog")
FBI_BLOG_FUTURE_EXTERNAL_FEED = feed(ITEM_TO_TREASURY, title="FBI News Blog")

FBI_REDIRECT_FEED_BODY = feed(
    ITEM_SAME_HOST, ITEM_SUBDOMAIN, ITEM_TO_TREASURY
)


# --- Article pages --------------------------------------------------------

def _article(headline, body_sentence):
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{headline} — FBI</title></head><body><article>"
        f"<time datetime='2026-07-21T13:00:00-04:00'>July 21, 2026</time>"
        f"<p>{body_sentence} "
        + ("Further detail about the investigation follows in the release. " * 40)
        + "</p></article></body></html>"
    )


FBI_ARTICLE = _article(
    "Man Sentenced for Wire Fraud",
    "A federal judge sentenced the defendant to sixty months in prison.",
)
FBI_ARTICLE_2 = _article(
    "Two Charged in a Romance Scam",
    "Two defendants were charged with defrauding victims through dating platforms.",
)
FBI_ARTICLE_SUBDOMAIN = _article(
    "Item Moved to the Newsroom",
    "The bureau published the release through its newsroom service.",
)
FBI_ARTICLE_MOVED = _article(
    "Release With a Canonical Slash",
    "The release is served from the canonical trailing-slash address.",
)

# Content that must never be reached through an FBI adapter. Serving it proves
# the request was refused rather than merely unhelpful.
DOJ_ARTICLE = _article(
    "Joint Announcement",
    "THIS IS DOJ CONTENT AND MUST NOT BE COLLECTED UNDER AN FBI SOURCE.",
)
