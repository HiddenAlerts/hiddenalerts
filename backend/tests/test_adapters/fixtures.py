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
