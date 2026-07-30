"""Sanitized DOJ fixtures derived from the 2026-07-28 source audit.

Structure only — feed shape, URL patterns, interstitial markers and summary
length bands are preserved; all prose is short synthetic text.
"""

# Cleaned length ~250 chars: a typical DOJ summary (audit median was 213).
GOOD_SUMMARY = (
    "A federal jury convicted a Massachusetts man of conspiring to export "
    "controlled electronic components in violation of federal sanctions. The "
    "defendant faces a statutory maximum of twenty years in prison at sentencing "
    "later this year, according to court documents filed in the district."
)

# ~135 chars: short, but a complete factual sentence — the audit's minimum
# observed summary was 68 chars, so this sits just above the production floor.
SHORT_VALID_SUMMARY = (
    "A Gretna man was indicted on federal firearm offenses following a "
    "multi-agency investigation into straw purchases in the district."
)

# Below the floor: one clause, no substance to classify on.
WEAK_SUMMARY = "Two men were charged."

BOILERPLATE_SUMMARY = "Read the full press release for more information."

LINK_ONLY_SUMMARY = (
    '<p><a href="https://www.justice.gov/opa/pr/example">'
    "https://www.justice.gov/opa/pr/example</a></p>"
)

TITLE_ECHO_TITLE = "Ukrainian-Israeli Citizen Sentenced for Fake Brokerage Scheme"
TITLE_ECHO_SUMMARY = "Ukrainian-Israeli citizen sentenced for fake brokerage scheme."

HTML_SUMMARY = (
    "<div><script>track();</script><nav>Skip to content</nav>"
    "<p>A federal grand jury returned an indictment charging three defendants "
    "with wire fraud and money laundering in connection with a scheme that "
    "solicited investors through fraudulent brokerage websites over two years.</p>"
    "</div>"
)


def _item(title, link, pub_date, description=None, *, omit_link=False, omit_title=False):
    parts = []
    if not omit_title:
        parts.append(f"<title>{title}</title>")
    if not omit_link:
        parts.append(f"<link>{link}</link>")
    parts.append(f"<pubDate>{pub_date}</pubDate>")
    if description is not None:
        parts.append(f"<description><![CDATA[{description}]]></description>")
    parts.append(f"<guid isPermaLink='true'>{link}</guid>")
    return "<item>" + "".join(parts) + "</item>"


def feed(*items: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        "<title>Justice News</title><link>https://www.justice.gov/news</link>"
        "<description>Department of Justice press releases</description>"
        + "".join(items)
        + "</channel></rss>"
    )


OPA_URL = "https://www.justice.gov/opa/pr/massachusetts-man-convicted-sanctions"
OPA_URL_2 = "https://www.justice.gov/opa/pr/investor-fraud"
USAO_URL = "https://www.justice.gov/usao-md/pr/gretna-man-indicted-firearm-offenses"
USAO_URL_2 = "https://www.justice.gov/usao-edny/pr/two-men-charged-conspiracy"
USAO_URL_3 = "https://www.justice.gov/usao-sdny/pr/defendant-sentenced-fraud"

PUB_DATE = "Tue, 28 Jul 2026 12:00:00 +0000"
PUB_DATE_EARLIER = "Mon, 27 Jul 2026 16:30:00 -0400"

ITEM_OPA = _item("Massachusetts Man Convicted of Violating Sanctions", OPA_URL,
                 PUB_DATE, GOOD_SUMMARY)
ITEM_USAO_GOOD = _item("Gretna Man Indicted on Federal Firearm Offenses", USAO_URL,
                       PUB_DATE_EARLIER, SHORT_VALID_SUMMARY)
ITEM_USAO_EMPTY = _item("Two Men Charged in Conspiracy", USAO_URL_2, PUB_DATE, "")
ITEM_USAO_WEAK = _item("Defendant Sentenced for Fraud", USAO_URL_3, PUB_DATE,
                       WEAK_SUMMARY)
ITEM_NO_DESCRIPTION = _item("Item Without Description",
                            "https://www.justice.gov/opa/pr/no-description", PUB_DATE)
ITEM_TITLE_ECHO = _item(TITLE_ECHO_TITLE,
                        "https://www.justice.gov/opa/pr/title-echo", PUB_DATE,
                        TITLE_ECHO_SUMMARY)
ITEM_HTML_SUMMARY = _item("Three Charged in Investor Fraud Scheme", OPA_URL_2, PUB_DATE,
                          HTML_SUMMARY)
ITEM_NO_LINK = _item("Entry Missing A Link", "", PUB_DATE, GOOD_SUMMARY,
                     omit_link=True)
ITEM_NO_TITLE = _item("", "https://www.justice.gov/opa/pr/no-title", PUB_DATE,
                      GOOD_SUMMARY, omit_title=True)

FULL_FEED = feed(ITEM_OPA, ITEM_USAO_GOOD, ITEM_USAO_EMPTY, ITEM_USAO_WEAK,
                 ITEM_HTML_SUMMARY)
FEED_WITH_MALFORMED = feed(ITEM_OPA, ITEM_NO_LINK, ITEM_NO_TITLE)
EMPTY_FEED = feed()

# A DOJ /opa/ article page: server-rendered, real text.
OPA_ARTICLE_HTML = (
    "<!DOCTYPE html><html><head><title>Office of Public Affairs | "
    "Massachusetts Man Convicted</title></head><body><article>"
    '<time datetime="2026-07-28T12:00:00Z">July 28, 2026</time>'
    "<p>A federal jury convicted the defendant following a fourteen-day trial. "
    + ("The indictment describes the export scheme in further detail. " * 40)
    + "</p></article></body></html>"
)

# A second /opa/ article — distinct text, so content-hash dedup does not merge it
# with OPA_ARTICLE_HTML during a collection run.
OPA_ARTICLE_HTML_2 = (
    "<!DOCTYPE html><html><head><title>Office of Public Affairs | "
    "Three Charged in Investor Fraud</title></head><body><article>"
    '<time datetime="2026-07-28T12:00:00Z">July 28, 2026</time>'
    "<p>Three defendants were charged in a superseding indictment unsealed today. "
    + ("Investors were solicited through fraudulent brokerage websites. " * 40)
    + "</p></article></body></html>"
)

# The Akamai interstitial served for /usao-* pages: HTTP 200, ~2.4 KB, no text.
USAO_INTERSTITIAL_HTML = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="5; URL=\'/news?bm-verify=AAQAAAAN'
    + ("x" * 700)
    + '\'" /><title>&nbsp;</title></head><body>'
    '<iframe src="https://www.justice.gov/apology_objects/interstitial/'
    'doj-interstitial.html"></iframe>'
    '<script>function go(){var x=new XMLHttpRequest();'
    'x.open("POST","/_sec/verify?provider=interstitial",false);'
    'x.send(JSON.stringify({"bm-verify":"AAQ'
    + ("y" * 700)
    + '"}));} try{document.getElementById("akam-logo").onload=go;}catch(e){go();}</script>'
    "</body></html>"
)

# The feed URL itself returning the interstitial instead of RSS.
FEED_CHALLENGE_HTML = USAO_INTERSTITIAL_HTML
