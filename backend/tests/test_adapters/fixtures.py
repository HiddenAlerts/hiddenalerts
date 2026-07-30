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


def small_article_mentioning(marker: str) -> str:
    """A short but legitimate press release quoting a CDN/challenge token.

    Sized in the range the audit observed for real FinCEN detail pages
    (~0.9–3 KB of extracted text), so short length alone must not be read as
    evidence of a verification shell.
    """
    return (
        "<!DOCTYPE html><html><head><title>FinCEN Alert</title></head><body>"
        f"<p>FinCEN issued an alert after analysts observed {marker} referenced "
        "in the reporting. "
        + ("The advisory describes the typology in brief. " * 40)
        + "</p></body></html>"
    )


def large_article_quoting_mechanism(token: str) -> str:
    """A long security article quoting a challenge endpoint in prose and a code block.

    The token appears only as text, never as a form action, script call or
    element id, so it must not read as a live mechanism.
    """
    return (
        "<!DOCTYPE html><html><head><title>CDN Challenge Analysis</title></head><body>"
        f"<article><p>The vendor documentation refers to {token} when describing "
        "the interstitial flow. Analysts reproduced the behaviour in a lab.</p>"
        f"<pre><code>GET {token} HTTP/1.1</code></pre>"
        + ("<p>Further analysis of the observed traffic continues here. </p>" * 300)
        + "</article></body></html>"
    )


def _prose(n: int = 30) -> str:
    return "Analysts documented the observed behaviour in detail. " * n


def article_documenting(snippet: str) -> str:
    """A security article whose body quotes challenge markup as documentation."""
    return (
        "<!DOCTYPE html><html><head><title>CDN Interstitial Analysis</title></head>"
        f"<body><article><p>{_prose()}</p>{snippet}"
        f"<p>{_prose()}</p></article></body></html>"
    )


def article_with_marker_and_wording(marker: str, wording: str) -> str:
    """A short but real security article that uses a vendor token and denial wording."""
    return (
        "<!DOCTYPE html><html><head><title>Threat Note</title></head><body><article>"
        f"<p>The report references {marker} and describes {wording} controls. "
        + ("The note continues with the observed detection detail. " * 20)
        + "</p></article></body></html>"
    )


# Article about access denial with an unrelated footer contact-form reCAPTCHA.
ARTICLE_ACCESS_DENIED_WITH_FOOTER_CAPTCHA = (
    "<!DOCTYPE html><html><head><title>Insider Access Case</title></head><body>"
    "<main><article><p>The complaint states the defendant received an access denied "
    "message before escalating privileges. "
    + ("The filing details the subsequent unauthorized activity. " * 30)
    + "</p></article></main>"
    '<footer><form action="/contact"><div class="g-recaptcha" '
    'data-sitekey="6LcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"></div></form></footer>'
    "</body></html>"
)

# Real mechanisms, for the positive side of each documentation case.
REAL_SEC_VERIFY_SCRIPT = (
    '<html><body><script>var x=new XMLHttpRequest();'
    'x.open("POST","/_sec/verify?provider=interstitial",false);x.send();</script></body></html>'
)
REAL_DOJ_IFRAME = (
    '<html><body><iframe src="https://www.justice.gov/apology_objects/interstitial/'
    'doj-interstitial.html"></iframe></body></html>'
)
REAL_CF_RESOURCE = (
    '<html><body><script src="/cdn-cgi/challenge-platform/h/b/orchestrate/jsch/v1">'
    "</script></body></html>"
)
REAL_CF_FORM = (
    '<html><body><form id="challenge-form" action="/cdn-cgi/challenge-platform/verify">'
    "<button>Continue</button></form></body></html>"
)

MALFORMED_LOCATIONS = [
    "http://[::1",
    "http://[:::1]/",
    "http://[bad]:x/",
    "http://[]/",
    "//[::1",
    "http://x.test:99999/",
]


def article_with_data_script(script_type: str, payload: str) -> str:
    """A real article carrying a challenge call inside a non-executable script."""
    return (
        "<!DOCTYPE html><html><head><title>Interstitial Research</title>"
        f'<script type="{script_type}">{payload}</script></head>'
        "<body><article><p>"
        + ("The write-up walks through the observed verification flow. " * 30)
        + "</p></article></body></html>"
    )


def article_with_executable_script(payload: str) -> str:
    """The same call in a script the browser would actually run."""
    return (
        "<!DOCTYPE html><html><head><title>Page</title></head><body><article><p>"
        + ("Body prose. " * 30)
        + f"</p></article><script>{payload}</script></body></html>"
    )


def article_with_generic_asset(marker: str, asset: str) -> str:
    """A long article that names a vendor token and loads an unrelated asset."""
    return (
        "<!DOCTYPE html><html><head><title>Threat Analysis</title>"
        f'<script src="{asset}"></script></head><body><article><p>'
        f"The report discusses {marker} at length. "
        + ("Further analysis of the campaign continues here. " * 120)
        + "</p></article></body></html>"
    )


JSONLD_WITH_CALLS = (
    '{"@context":"https://schema.org","@type":"NewsArticle",'
    '"articleBody":"The demo used fetch(\'/_sec/verify\') and '
    'xhr.open(\'POST\', \'/_sec/verify\') to reproduce the flow.",'
    '"description":"Also fetch(\'/cdn-cgi/challenge-platform/example\')."}'
)

# Legitimate form whose name merely contains the word challenge.
LEGITIMATE_CHALLENGE_ENTRY_FORM = (
    "<!DOCTYPE html><html><body><main><article><p>"
    + ("Entries for the challenge are open until Friday. " * 30)
    + '</p></article></main><form id="challenge-entry-form" action="/submit">'
    "<button>Enter</button></form></body></html>"
)

# XHTML served with an XML declaration, carrying a real challenge form.
XHTML_CHALLENGE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">'
    '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Verify</title></head>'
    '<body><form id="challenge-form" action="/cdn-cgi/challenge-platform/verify">'
    "<button>Continue</button></form></body></html>"
)

XHTML_ARTICLE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Press Release</title></head>'
    "<body><article><p>"
    + ("A federal jury returned an indictment today. " * 30)
    + "</p></article></body></html>"
)

RSS_WITH_DECLARATION = (
    '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    "<title>Feed</title><item><title>One</title>"
    "<link>https://example.test/a</link></item></channel></rss>"
)

ATOM_WITH_DECLARATION = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom"><title>Feed</title>'
    "<entry><title>One</title><link href=\"https://example.test/a\"/></entry></feed>"
)


# JSON documents whose *values* contain markup. The document is still JSON.
JSON_WITH_HTML_STRING = '{"body":"<html><body>text</body></html>"}'
JSON_WITH_P_STRING = '{"description":"<p>summary</p>"}'
JSON_ARRAY_WITH_DIV_STRING = '["<div>rendered preview</div>"]'

# Generic XML whose children merely share names with HTML elements.
XML_RESPONSE_WITH_BODY = (
    '<?xml version="1.0"?><response><body>ok</body></response>'
)
XML_ROOT_WITH_P = "<root><p>value</p></root>"
XML_DOCUMENT_WITH_DIV = "<document><div>value</div></document>"

# Names that merely contain a known token — not mechanisms.
FORM_ACTION_CHALLENGE_ENTRY = '<form action="/events/challenge-form-entry"></form>'
DIV_CF_CHALLENGE_ANALYSIS = '<div class="cf-challenge-analysis">notes</div>'
DIV_AKAM_LOGO_ANALYSIS = '<div id="akam-logo-analysis">notes</div>'
