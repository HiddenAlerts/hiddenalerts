"""Deterministic response fixtures for the shared source HTTP boundary.

Shapes mirror what the source audits observed. No network is ever used.
"""

# Observed DOJ/FBI interstitial: HTTP 200, ~2.3–2.6 KB, bm-verify token, meta
# refresh, iframe to the interstitial document, XHR to /_sec/verify.
DOJ_INTERSTITIAL = (
    '<!DOCTYPE html><html><head> <meta charset="utf-8"> '
    '<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no"> '
    '<meta http-equiv="refresh" content="5; URL=\'/news?bm-verify=AAQAAAAN_____'
    + ("x" * 700)
    + '\'" /><title>&nbsp;</title><script> var i = 1785087938; </script> </head>'
    '<noscript><iframe style="border: none;" src=""></iframe></noscript><body> '
    '<iframe style="border: none; width: 100vw;" '
    'src="https://www.justice.gov/apology_objects/interstitial/doj-interstitial.html"> </iframe> '
    '<script> function triggerInterstitialChallenge() {var xhr = new XMLHttpRequest(); '
    'xhr.open("POST", "/_sec/verify?provider=interstitial", false); '
    'xhr.send(JSON.stringify({"bm-verify": "AAQAAAAN'
    + ("y" * 700)
    + '", "pow": j}));} '
    'try {if (document.getElementById("akam-logo")) {'
    'document.getElementById("akam-logo").onload = triggerInterstitialChallenge;} '
    'else {triggerInterstitialChallenge()}} catch(e) {triggerInterstitialChallenge();}</script>'
    "</body></html>"
)

# IC3 article: real content, plus an inert recaptcha preconnect hint in a CSP-ish
# script prefix list. Must classify as usable.
IC3_ARTICLE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    "<title>Internet Crime Complaint Center (IC3) | FBI Warns of Scammers Impersonating the IC3</title>"
    '<link rel="preconnect" href="https://www.gstatic.com/recaptcha/releases/">'
    "<script>var trustedScriptPrefix = ['https://www.gstatic.com/recaptcha/releases/', "
    "'https://www.googletagmanager.com/'];</script>"
    '</head><body><time datetime="2026-07-20T10:00:00.000-04:00">July 20, 2026</time>'
    "<article><p>This Public Service Announcement warns the public that scammers are "
    "impersonating the FBI Internet Crime Complaint Center. "
    + ("Victims are urged to report fraudulent contacts to law enforcement immediately. " * 120)
    + "</p></article></body></html>"
)

# Ordinary small page with a meta refresh for a legitimate reason (a moved page).
# One corroborating signal only — must NOT be treated as a challenge.
BENIGN_META_REFRESH = (
    '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="3; url=/news/2026/new-home">'
    "<title>Page moved</title></head><body><p>This press release has moved to a new address. "
    "Please update your bookmarks.</p></body></html>"
)

ARTICLE_HTML = (
    "<!DOCTYPE html><html><head><title>Man Sentenced for Wire Fraud</title></head>"
    "<body><article><p>A federal jury convicted the defendant of wire fraud following "
    "a three-week trial. " + ("Additional detail about the scheme follows. " * 40)
    + "</p></article></body></html>"
)

RSS_FEED = (
    '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    "<title>Test Press Releases</title><link>https://example.test/</link>"
    "<item><title>First Item</title><link>https://example.test/a</link>"
    "<description>A factual summary of the first item.</description>"
    "<pubDate>Mon, 20 Jul 2026 12:00:00 +0000</pubDate></item>"
    "<item><title>Second Item</title><link>https://example.test/b</link>"
    "<description>A factual summary of the second item.</description>"
    "<pubDate>Sun, 19 Jul 2026 12:00:00 +0000</pubDate></item>"
    "</channel></rss>"
)

ORDINARY_HTML_LISTING = (
    "<!DOCTYPE html><html><head><title>Press Releases</title></head><body>"
    '<div class="views-row"><a href="/news/one">Item One</a></div>'
    '<div class="views-row"><a href="/news/two">Item Two</a></div>'
    "</body></html>"
)

# Minimal but valid PDF bytes, for the mislabelled-content-type case.
PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

# Healthy article that embeds a reCAPTCHA widget in its footer contact form.
# A widget alone must never mark a real page as blocked.
ARTICLE_WITH_FOOTER_RECAPTCHA = (
    "<!DOCTYPE html><html><head><title>Grant Fraud Indictment</title></head><body>"
    "<article><p>A federal grand jury returned an indictment charging the defendant "
    "with grant fraud. " + ("Further procedural detail follows in the release. " * 60)
    + "</p></article>"
    '<footer><form action="/contact"><div class="g-recaptcha" '
    'data-sitekey="6LcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"></div>'
    "<button>Send</button></form></footer></body></html>"
)

# A genuine captcha interstitial: small, widget plus verification wording.
CAPTCHA_CHALLENGE = (
    "<!DOCTYPE html><html><head><title>Security check</title></head><body>"
    "<h1>Please verify you are human</h1>"
    '<div class="g-recaptcha" data-sitekey="6LcXXXX"></div>'
    "</body></html>"
)

# Cloudflare-style challenge returned with HTTP 403.
CLOUDFLARE_CHALLENGE = (
    "<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
    '<div class="cf-browser-verification cf-im-under-attack">'
    "<noscript>Please enable JavaScript and cookies to continue.</noscript>"
    "</div><p>Checking if the site connection is secure</p></body></html>"
)

# Valid RSS with zero entries — an empty feed is NOT an empty response.
EMPTY_RSS_FEED = (
    '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    "<title>News Blog</title><link>https://example.test/</link>"
    "<description>No items at present.</description></channel></rss>"
)

# HTML whose extracted text is empty once scripts/styles/chrome are stripped.
ARTICLE_WITH_NO_TEXT = (
    "<!DOCTYPE html><html><head><title></title>"
    "<style>body{color:red}</style></head>"
    '<body><nav>Home About Contact</nav><div id="root"></div>'
    '<script>window.__DATA__={};renderApp();</script>'
    "<footer>All rights reserved</footer></body></html>"
)

# Short HTTP 403 refusal page: one strong denial marker, no other evidence.
ACCESS_DENIED_403 = (
    "<!DOCTYPE html><html><head><title>Access Denied</title></head><body>"
    "<h1>Access Denied</h1><p>You don't have permission to access this resource "
    "on this server.</p></body></html>"
)

# A genuine article that merely discusses access denial. Must stay usable.
ARTICLE_ABOUT_ACCESS_DENIAL = (
    "<!DOCTYPE html><html><head><title>Insider Denied Access Charged</title></head>"
    "<body><article><p>The indictment alleges the defendant saw an access denied "
    "message and then escalated privileges. "
    + ("The complaint describes further unauthorized access attempts. " * 160)
    + "</p></article></body></html>"
)

# Plain 403 with no challenge or denial evidence at all.
PLAIN_FORBIDDEN_403 = "<!DOCTYPE html><html><body><h1>Forbidden</h1></body></html>"

# HTML fragments with no document wrapper.
HTML_ARTICLE_FRAGMENT = (
    "<article><h2>Man Sentenced for Fraud</h2><p>A federal judge imposed a "
    "48-month sentence following a guilty plea.</p></article>"
)
HTML_DIV_FRAGMENT = '<div class="content"><p>Press release body text here.</p></div>'

# Ordinary non-feed XML — must stay XML, not be mistaken for HTML.
GENERIC_XML = (
    '<?xml version="1.0"?><catalog><book id="1"><title>A</title></book></catalog>'
)
GENERIC_XML_NO_PROLOGUE = '<catalog><book id="1"><title>A</title></book></catalog>'


def large_article_mentioning(marker: str) -> str:
    """A genuine security article that merely quotes a CDN/challenge token.

    Comfortably above the small-shell threshold, so a technical marker appearing
    as prose must not classify it as blocked.
    """
    return (
        "<!DOCTYPE html><html><head><title>Threat Report</title></head><body><article>"
        f"<p>Researchers observed {marker} referenced in the intrusion set. "
        + ("A further sentence of genuine reporting continues the analysis here. " * 400)
        + "</p></article></body></html>"
    )


# 429 body that mentions automated access but carries no challenge mechanism.
RATE_LIMITED_BODY = (
    "<!DOCTYPE html><html><body><h1>Too Many Requests</h1>"
    "<p>Automated access is limited. Please retry later.</p></body></html>"
)

# 429 that really is a challenge: a challenge form is present.
RATE_LIMITED_WITH_CHALLENGE = (
    "<!DOCTYPE html><html><body><h1>Too Many Requests</h1>"
    '<form class="challenge-form" action="/cdn-cgi/challenge-platform/verify">'
    "<button>Verify</button></form></body></html>"
)

# Browser navigation returning a PDF.
BROWSER_PDF_HTML = "<html><body>%PDF-1.4 binary payload</body></html>"
