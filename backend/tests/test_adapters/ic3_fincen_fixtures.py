"""Sanitized IC3 and FinCEN fixtures derived from the 2026-07-28 source audits.

Structure only — card layout, URL shapes, ``<time>`` placement and the wrapper
that used to swallow the FinCEN listing are preserved; all prose is short
synthetic text.
"""

# --- IC3 ------------------------------------------------------------------

IC3_ROOT = "https://www.ic3.gov/PSA"
IC3_LISTING_2026 = f"{IC3_ROOT}/2026"

PSA_TZ_URL = f"{IC3_ROOT}/2026/PSA260720"
PSA_VISIBLE_URL = f"{IC3_ROOT}/2026/PSA260626"
PSA_URL_DATE_URL = f"{IC3_ROOT}/2026/PSA260618"
PSA_SUFFIXED_URL = f"{IC3_ROOT}/2026/PSA260515-2"
PSA_BAD_SLUG_URL = f"{IC3_ROOT}/2026/PSA269932"
PSA_YEAR_MISMATCH_URL = f"{IC3_ROOT}/2026/PSA240301"
PSA_LEAP_URL = f"{IC3_ROOT}/2024/PSA240229"


def _card(href, title, date_markup=""):
    """One listing card: a heading link plus, usually, its own date element."""
    return (
        '<div class="psa-card">'
        f'<h3 class="psa-card__title"><a href="{href}">{title}</a></h3>'
        f"{date_markup}"
        '<p class="psa-card__teaser">Synthetic teaser text for the announcement.</p>'
        "</div>"
    )


def ic3_listing(*cards: str) -> str:
    """A year listing page: site chrome, a card grid, then footer navigation.

    No table, no <tr> — the structure that broke the old parser.
    """
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<title>Internet Crime Complaint Center (IC3) | Public Service Announcements</title>"
        "</head><body>"
        '<nav class="site-nav"><a href="/">Home</a>'
        '<a href="/PSA/Archive">Past PSAs</a>'
        '<a href="/PSA/RSS">RSS</a>'
        '<a href="/Media/Y2026">Media</a>'
        '<a href="https://www.fbi.gov/contact-us">Contact the FBI</a></nav>'
        '<main><div class="psa-grid">' + "".join(cards) + "</div>"
        '<nav class="pager"><a href="/PSA/2026?page=2">Next page</a>'
        '<a href="/PSA/2025">2025</a></nav></main>'
        '<footer><a href="/PSA/Archive">Archive</a>'
        '<a href="/Privacy">Privacy Policy</a></footer>'
        "</body></html>"
    )


# Card 1: timezone-aware <time datetime> — the primary path.
IC3_CARD_TZ = _card(
    "/PSA/2026/PSA260720",
    "Scammers Impersonate the IC3 to Contact Fraud Victims",
    '<time class="psa-card__date" datetime="2026-07-20T10:00:00-04:00">July 20, 2026</time>',
)
# Card 2: <time> with no datetime attribute — visible-text fallback.
IC3_CARD_VISIBLE = _card(
    "/PSA/2026/PSA260626",
    "Criminals Use Spoofed Numbers to Pose as Bank Investigators",
    '<time class="psa-card__date">June 26, 2026</time>',
)
# Card 3: no date element at all — URL-slug fallback.
IC3_CARD_NO_DATE = _card(
    "/PSA/2026/PSA260618",
    "Business Email Compromise Losses Continue to Rise",
)
# Card 4: absolute URL and a numeric suffix.
IC3_CARD_ABSOLUTE = _card(
    PSA_SUFFIXED_URL,
    "Second Announcement Issued the Same Day",
    '<time class="psa-card__date" datetime="2026-05-15T09:30:00-04:00">May 15, 2026</time>',
)
# Card 5: slug is not a real calendar date — no date, but the item survives.
IC3_CARD_BAD_SLUG = _card(
    "/PSA/2026/PSA269932",
    "Announcement With an Unparseable Identifier",
)
# Card 6: slug year disagrees with the path year — no date, item survives.
IC3_CARD_YEAR_MISMATCH = _card(
    "/PSA/2026/PSA240301",
    "Announcement Filed Under a Mismatched Year",
)
# Not an article: the PSA landing links the old parser accepted.
IC3_CARD_ARCHIVE = _card("/PSA/Archive", "Public Service Announcement Archive")
IC3_CARD_RSS = _card("/PSA/RSS", "Subscribe by RSS")

IC3_FULL_LISTING = ic3_listing(
    IC3_CARD_TZ,
    IC3_CARD_VISIBLE,
    IC3_CARD_NO_DATE,
    IC3_CARD_ABSOLUTE,
    IC3_CARD_ARCHIVE,
    IC3_CARD_RSS,
)
IC3_EDGE_LISTING = ic3_listing(IC3_CARD_BAD_SLUG, IC3_CARD_YEAR_MISMATCH)
IC3_EMPTY_LISTING = ic3_listing()

# Two cards whose dates sit adjacent in the DOM: a parser that widens too far
# would hand card 2's date to card 1.
IC3_ADJACENT_LISTING = ic3_listing(IC3_CARD_TZ, IC3_CARD_VISIBLE)

# A leap-day slug on its matching year page.
IC3_LEAP_LISTING = ic3_listing(
    _card("/PSA/2024/PSA240229", "Leap Day Announcement")
)

IC3_ARTICLE_PAGE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    "<title>Internet Crime Complaint Center (IC3) | Scammers Impersonate the IC3</title>"
    '</head><body><time datetime="2026-07-20T10:00:00-04:00">July 20, 2026</time>'
    "<article><p>This Public Service Announcement warns the public that criminals are "
    "contacting prior fraud victims while posing as IC3 staff. "
    + ("Recipients are urged to report the contact rather than respond. " * 40)
    + "</p></article></body></html>"
)


# --- FinCEN ---------------------------------------------------------------

FINCEN_LISTING_URL = "https://www.fincen.gov/news/press-releases"

FINCEN_TZ_URL = (
    "https://www.fincen.gov/news/news-releases/"
    "fincen-proposes-rule-pay-whistleblowers"
)
FINCEN_VISIBLE_URL = (
    "https://www.fincen.gov/news/news-releases/"
    "fincen-issues-notice-threat-human-trafficking"
)
FINCEN_NO_DATE_URL = (
    "https://www.fincen.gov/news/news-releases/"
    "readout-financial-intelligence-units-commit-counter-crime"
)
FINCEN_ABSOLUTE_URL = (
    "https://www.fincen.gov/news/news-releases/"
    "treasury-proposes-rule-sever-swiss-bank-access"
)


def _row(href, title, date_markup="", lead_link=True):
    """One listing row. ``lead_link`` mimics the tag link that precedes the
    real press-release link in FinCEN's markup — the anchor the old
    first-link-under-the-wrapper selector kept picking up."""
    lead = '<a class="row__tag" href="/news-room/topic/enforcement">Enforcement</a>' if lead_link else ""
    return (
        '<div class="views-row">'
        f"{lead}"
        f'<h2 class="row__title"><a href="{href}">{title}</a></h2>'
        f"{date_markup}"
        '<div class="row__teaser">Synthetic teaser text for the press release.</div>'
        "</div>"
    )


def fincen_listing(*rows: str) -> str:
    """The listing page inside the single broad wrapper the audit observed."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<title>Press Releases | FinCEN.gov</title></head><body>"
        '<article class="page page--press-releases">'
        '<nav class="breadcrumb"><a href="/">Home</a><a href="/news">News</a>'
        '<a href="/news/press-releases">Press Releases</a></nav>'
        '<div class="view-content">' + "".join(rows) + "</div>"
        '<nav class="pager"><a href="/news/press-releases?page=1">Next</a></nav>'
        "</article>"
        '<footer><a href="https://www.treasury.gov/">Treasury</a>'
        '<a href="/contact">Contact</a></footer>'
        "</body></html>"
    )


FINCEN_ROW_TZ = _row(
    "/news/news-releases/fincen-proposes-rule-pay-whistleblowers",
    "FinCEN Proposes Rule to Pay Whistleblowers",
    '<time class="row__date" datetime="2026-07-15T14:00:00-04:00">July 15, 2026</time>',
)
FINCEN_ROW_VISIBLE = _row(
    "/news/news-releases/fincen-issues-notice-threat-human-trafficking",
    "FinCEN Issues Notice on Human Trafficking Threats During the 2026 World Cup",
    '<span class="date-display-single">July 9, 2026</span>',
)
FINCEN_ROW_NO_DATE = _row(
    "/news/news-releases/readout-financial-intelligence-units-commit-counter-crime",
    "Readout: Financial Intelligence Units Commit to Counter Transnational Crime",
)
FINCEN_ROW_ABSOLUTE = _row(
    FINCEN_ABSOLUTE_URL,
    "Treasury Proposes Rule to Sever a Swiss Bank's Access",
    '<time class="row__date" datetime="2026-06-30T09:00:00-04:00">June 30, 2026</time>',
)
# Not a press release: an advisory link and an off-site link in row shape.
FINCEN_ROW_UNRELATED = _row(
    "/resources/advisories/fincen-advisory-fin-2026-a003",
    "Advisory on Fuel Smuggling Schemes",
    '<time class="row__date" datetime="2026-06-01T09:00:00-04:00">June 1, 2026</time>',
)
FINCEN_ROW_OFFSITE = _row(
    "https://www.treasury.gov/news/press-releases/tr-2026-07",
    "Treasury Announcement Hosted Elsewhere",
    '<time class="row__date" datetime="2026-06-02T09:00:00-04:00">June 2, 2026</time>',
)

FINCEN_FULL_LISTING = fincen_listing(
    FINCEN_ROW_TZ,
    FINCEN_ROW_VISIBLE,
    FINCEN_ROW_NO_DATE,
    FINCEN_ROW_ABSOLUTE,
    FINCEN_ROW_UNRELATED,
    FINCEN_ROW_OFFSITE,
)
FINCEN_EMPTY_LISTING = fincen_listing()

# Two dated rows side by side — a wrapper-wide date search would cross them.
FINCEN_ADJACENT_LISTING = fincen_listing(FINCEN_ROW_TZ, FINCEN_ROW_ABSOLUTE)

FINCEN_ARTICLE_PAGE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    "<title>FinCEN Proposes Rule to Pay Whistleblowers | FinCEN.gov</title>"
    '</head><body><time datetime="2026-07-15T14:00:00-04:00">July 15, 2026</time>'
    "<article><p>FinCEN today proposed a rule establishing how awards would be paid "
    "to whistleblowers who report violations. "
    + ("The proposal describes the award determination process. " * 40)
    + "</p></article></body></html>"
)
