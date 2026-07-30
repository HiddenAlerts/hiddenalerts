"""Sanitized FTC, SEC and Krebs fixtures derived from the 2026-07-28 audits.

Structure only — nested listing containers, URL shapes, summary length bands and
feed layout are preserved; all prose is short synthetic text.
"""

# --- FTC ------------------------------------------------------------------

FTC_LISTING_URL = "https://www.ftc.gov/news-events/news/press-releases"
FTC_HOST = "https://www.ftc.gov"

PR_TZ_URL = f"{FTC_HOST}/news-events/news/press-releases/2026/07/ftc-returns-money-scam-victims"
PR_VISIBLE_URL = f"{FTC_HOST}/news-events/news/press-releases/2026/07/ftc-sues-subscription-service"
PR_NO_DATE_URL = f"{FTC_HOST}/news-events/news/press-releases/2026/06/ftc-finalizes-order-data-broker"
PR_ABSOLUTE_URL = f"{FTC_HOST}/news-events/news/press-releases/2026/06/ftc-staff-report-dark-patterns"


def _ftc_row(href, title, date_markup="", *, repeat_anchor=False):
    """One listing item, wrapped the way the FTC page nests its containers.

    ``div.view-content > div.views-row > article`` — all three matched the old
    selector, which is why one anchor was captured three times over.
    ``repeat_anchor`` adds the second link to the same release that the real page
    carries (a thumbnail link alongside the heading link).
    """
    thumb = f'<a class="card__image" href="{href}"><img alt="" src="/i.png"/>Read</a>' \
        if repeat_anchor else ""
    return (
        '<div class="views-row"><article class="card">'
        f"{thumb}"
        f'<h3 class="card__title"><a href="{href}">{title}</a></h3>'
        f"{date_markup}"
        '<p class="card__teaser">Synthetic teaser text for the press release.</p>'
        "</article></div>"
    )


def ftc_listing(*rows: str) -> str:
    """The listing page: chrome, a nested view container, then navigation."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<title>Press Releases | Federal Trade Commission</title></head><body>"
        '<nav class="site-nav">'
        '<a href="/">Home</a>'
        '<a href="/news-events/news/press-releases">Press Releases</a>'
        '<a href="/news-events/news/press-releases/">Press Releases (trailing)</a>'
        '<a href="/news-events/topics/protecting-consumers">Protecting Consumers</a>'
        '<a href="/enforcement/competition-matters/2026/02/some-blog-post">'
        "Competition Matters</a>"
        '<a href="/news-events/events/2026/07/veterans-small-business-webinar">'
        "Veterans Webinar</a>"
        '<a href="/microeconomics">Microeconomics</a>'
        '<a href="https://www.consumer.gov/">Consumer.gov</a>'
        "</nav>"
        '<div class="view-content">' + "".join(rows) + "</div>"
        '<nav class="pager">'
        '<a href="/news-events/news/press-releases?page=1">Next</a>'
        '<a href="/news-events/news/press-releases?items_per_page=50">Show 50</a>'
        "</nav>"
        '<footer><a href="/policy/advocacy-research">Advocacy</a>'
        '<a href="/about-ftc/contact">Contact</a></footer>'
        "</body></html>"
    )


FTC_ROW_TZ = _ftc_row(
    "/news-events/news/press-releases/2026/07/ftc-returns-money-scam-victims",
    "FTC Returns Money to Consumers Harmed by a Tech Support Scam",
    '<time class="card__date" datetime="2026-07-22T13:00:00-04:00">July 22, 2026</time>',
    repeat_anchor=True,
)
FTC_ROW_VISIBLE = _ftc_row(
    "/news-events/news/press-releases/2026/07/ftc-sues-subscription-service",
    "FTC Sues a Subscription Service Over Hard-to-Cancel Enrollments",
    '<span class="card__date field--date">July 8, 2026</span>',
)
FTC_ROW_NO_DATE = _ftc_row(
    "/news-events/news/press-releases/2026/06/ftc-finalizes-order-data-broker",
    "FTC Finalizes Order Against a Data Broker",
)
FTC_ROW_ABSOLUTE = _ftc_row(
    PR_ABSOLUTE_URL,
    "FTC Staff Report Examines Dark Patterns in Online Sign-Up Flows",
    '<time class="card__date" datetime="2026-06-30T09:15:00-04:00">June 30, 2026</time>',
)

FTC_FULL_LISTING = ftc_listing(
    FTC_ROW_TZ, FTC_ROW_VISIBLE, FTC_ROW_NO_DATE, FTC_ROW_ABSOLUTE
)
FTC_EMPTY_LISTING = ftc_listing()

# Hrefs that break url parsing, alongside one healthy row.
FTC_MALFORMED_LISTING = ftc_listing(
    _ftc_row("http://[::1/news-events/news/press-releases/2026/01/a", "Unclosed bracket"),
    _ftc_row("http://[not-an-ip]/news-events/news/press-releases/2026/01/b", "Bad host"),
    _ftc_row("//[::1/news-events/news/press-releases/2026/01/c", "Bad protocol-relative"),
    FTC_ROW_TZ,
)

FTC_ARTICLE_PAGE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    "<title>FTC Returns Money to Consumers | Federal Trade Commission</title>"
    '</head><body><time datetime="2026-07-22T13:00:00-04:00">July 22, 2026</time>'
    "<article><p>The Federal Trade Commission is sending payments to consumers who "
    "lost money to a technology support scheme. "
    + ("Recipients should deposit the payment within ninety days. " * 40)
    + "</p></article></body></html>"
)


# --- SEC ------------------------------------------------------------------

SEC_FEED_URL = "https://www.sec.gov/news/pressreleases.rss"

# Cleaned length ~245 chars — the audit measured min 212 / median 249 / max 255.
SEC_GOOD_SUMMARY = (
    "The Securities and Exchange Commission today announced settled charges against "
    "an investment adviser for misrepresenting how client assets were custodied. The "
    "order finds the firm violated the antifraud provisions and imposes a civil "
    "penalty payable to harmed investors."
)
# ~160 chars: shorter than the audited floor but complete and factual.
SEC_SHORT_VALID_SUMMARY = (
    "The Commission charged two individuals today with running an offering fraud "
    "that raised nine million dollars from retail investors across four states."
)
SEC_WEAK_SUMMARY = "The Commission announced charges."
SEC_BOILERPLATE_SUMMARY = "For immediate release. Read the full press release."
SEC_LINK_ONLY_SUMMARY = (
    '<p><a href="https://www.sec.gov/news/press-release/2026-140">'
    "https://www.sec.gov/news/press-release/2026-140</a></p>"
)
SEC_TITLE_ECHO_TITLE = (
    "SEC Charges Investment Adviser With Misrepresenting Custody of Client Assets"
)
SEC_TITLE_ECHO_SUMMARY = (
    "SEC charges investment adviser with misrepresenting custody of client assets."
)
SEC_HTML_SUMMARY = (
    "<div><script>ga('send');</script><nav>Skip to main content</nav>"
    "<p>The Securities and Exchange Commission today obtained a final judgment "
    "against a former executive who concealed related-party transactions from "
    "auditors over a three-year period, according to the complaint filed in "
    "federal district court.</p></div>"
)

SEC_PR_1 = "https://www.sec.gov/newsroom/press-releases/2026-140"
SEC_PR_2 = "https://www.sec.gov/newsroom/press-releases/2026-141"
SEC_PR_3 = "https://www.sec.gov/newsroom/press-releases/2026-142"
SEC_PR_4 = "https://www.sec.gov/newsroom/press-releases/2026-143"
SEC_PR_5 = "https://www.sec.gov/newsroom/press-releases/2026-144"

SEC_PUB_DATE = "Wed, 22 Jul 2026 14:00:00 -0400"
SEC_PUB_DATE_2 = "Tue, 21 Jul 2026 09:30:00 +0000"


def _sec_item(title, link, pub_date, description=None):
    parts = [f"<title>{title}</title>", f"<link>{link}</link>",
             f"<pubDate>{pub_date}</pubDate>"]
    if description is not None:
        parts.append(f"<description><![CDATA[{description}]]></description>")
    parts.append(f"<guid isPermaLink='true'>{link}</guid>")
    return "<item>" + "".join(parts) + "</item>"


def sec_feed(*items: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        "<title>SEC Press Releases</title>"
        "<link>https://www.sec.gov/news/pressreleases</link>"
        "<description>Press releases from the U.S. Securities and Exchange "
        "Commission</description>"
        + "".join(items)
        + "</channel></rss>"
    )


SEC_ITEM_GOOD = _sec_item(
    "SEC Charges Investment Adviser Over Custody Misstatements",
    SEC_PR_1, SEC_PUB_DATE, SEC_GOOD_SUMMARY,
)
SEC_ITEM_SHORT = _sec_item(
    "SEC Charges Two in Offering Fraud",
    SEC_PR_2, SEC_PUB_DATE_2, SEC_SHORT_VALID_SUMMARY,
)
SEC_ITEM_EMPTY = _sec_item(
    "SEC Announces Committee Meeting", SEC_PR_3, SEC_PUB_DATE, "",
)
SEC_ITEM_WEAK = _sec_item(
    "SEC Announces Enforcement Action", SEC_PR_4, SEC_PUB_DATE, SEC_WEAK_SUMMARY,
)
SEC_ITEM_HTML = _sec_item(
    "SEC Obtains Final Judgment Against Former Executive",
    SEC_PR_5, SEC_PUB_DATE, SEC_HTML_SUMMARY,
)

SEC_FULL_FEED = sec_feed(
    SEC_ITEM_GOOD, SEC_ITEM_SHORT, SEC_ITEM_EMPTY, SEC_ITEM_WEAK, SEC_ITEM_HTML
)
SEC_EMPTY_FEED = sec_feed()


# --- Krebs ----------------------------------------------------------------

KREBS_FEED_URL = "https://krebsonsecurity.com/feed/"
KREBS_BASE = "https://krebsonsecurity.com"

KREBS_POST_1 = f"{KREBS_BASE}/2026/07/inside-a-phishing-as-a-service-operation/"
KREBS_POST_2 = f"{KREBS_BASE}/2026/07/who-is-behind-the-latest-sim-swap-wave/"
KREBS_POST_3 = f"{KREBS_BASE}/2026/06/a-closer-look-at-invoice-fraud/"

KREBS_SUMMARY_1 = (
    "A phishing-as-a-service operation sold ready-made login pages to hundreds of "
    "customers, complete with a support channel and a subscription tier that "
    "promised to bypass one-time codes."
)
KREBS_SUMMARY_2 = (
    "A wave of SIM-swap attacks against cryptocurrency holders traces back to a "
    "small group that recruited insiders at retail mobile stores."
)


def _krebs_item(title, link, pub_date, description, *, omit_link=False, omit_title=False):
    parts = []
    if not omit_title:
        parts.append(f"<title>{title}</title>")
    if not omit_link:
        parts.append(f"<link>{link}</link>")
    parts.append(f"<pubDate>{pub_date}</pubDate>")
    parts.append(f"<description><![CDATA[{description}]]></description>")
    return "<item>" + "".join(parts) + "</item>"


def krebs_feed(*items: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        "<title>Krebs on Security</title>"
        f"<link>{KREBS_BASE}</link>"
        "<description>In-depth security news and investigation</description>"
        + "".join(items)
        + "</channel></rss>"
    )


KREBS_ITEM_1 = _krebs_item(
    "Inside a Phishing-as-a-Service Operation", KREBS_POST_1,
    "Tue, 21 Jul 2026 18:05:00 +0000", KREBS_SUMMARY_1,
)
# Relative link — resolved against the feed URL.
KREBS_ITEM_2 = _krebs_item(
    "Who Is Behind the Latest SIM-Swap Wave?",
    "/2026/07/who-is-behind-the-latest-sim-swap-wave/",
    "Mon, 13 Jul 2026 12:30:00 -0400", KREBS_SUMMARY_2,
)
KREBS_ITEM_NO_LINK = _krebs_item(
    "Entry Missing A Link", "", "Sun, 12 Jul 2026 08:00:00 +0000",
    KREBS_SUMMARY_1, omit_link=True,
)
KREBS_ITEM_NO_TITLE = _krebs_item(
    "", KREBS_POST_3, "Sat, 11 Jul 2026 08:00:00 +0000",
    KREBS_SUMMARY_1, omit_title=True,
)

KREBS_FULL_FEED = krebs_feed(KREBS_ITEM_1, KREBS_ITEM_2)
KREBS_FEED_WITH_MALFORMED = krebs_feed(
    KREBS_ITEM_1, KREBS_ITEM_NO_LINK, KREBS_ITEM_NO_TITLE
)
KREBS_EMPTY_FEED = krebs_feed()

KREBS_ARTICLE_PAGE = (
    "<!DOCTYPE html><html><head><title>Inside a Phishing-as-a-Service Operation"
    "</title></head><body><article>"
    "<p>The operation advertised itself openly on a handful of forums. "
    + ("Subscribers received templates, hosting and a support channel. " * 60)
    + "</p></article></body></html>"
)

# The Krebs HTML listing the old fallback used to scrape. Present only to prove
# the repaired adapter never requests or parses it.
KREBS_HTML_LISTING = (
    "<!DOCTYPE html><html><head><title>Krebs on Security</title></head><body>"
    f'<article class="post"><h2 class="entry-title"><a href="{KREBS_POST_1}">'
    "Inside a Phishing-as-a-Service Operation</a></h2></article>"
    f'<article class="post"><h2 class="entry-title"><a href="{KREBS_POST_2}">'
    "Who Is Behind the Latest SIM-Swap Wave?</a></h2></article>"
    "</body></html>"
)
