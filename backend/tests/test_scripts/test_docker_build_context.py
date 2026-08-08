"""Docker build-context safety.

A credentials file named ``e2e.env`` was once copied into a production image
layer. The cause was subtle: ``.dockerignore`` excluded ``.env`` and ``.env.*``,
and neither pattern matches ``e2e.env`` — ``.env.*`` only covers names that
*start* with ``.env.``. Nothing failed loudly; the file simply shipped.

These tests evaluate ``.dockerignore`` as behaviour rather than asserting that
certain lines are present, so the protection cannot be defeated by reordering,
by a later negation, or by someone rewriting the rules in a different style.
They also assert the converse — that the ignore file does not swallow files the
image genuinely needs — because an over-broad fix would break the build instead.

The matcher below implements the subset of Docker's ``.dockerignore`` semantics
this file actually uses: comments, ``!`` negation, ``**``, ``*``, ``?``,
directory prefixes, and last-match-wins.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = BACKEND_ROOT / ".dockerignore"


def _parse(text: str) -> list[tuple[str, bool]]:
    """Return [(pattern, is_negation)] in file order, skipping blanks/comments."""
    rules: list[tuple[str, bool]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        # Docker cleans patterns; a trailing slash is not significant.
        line = line.rstrip("/")
        if line:
            rules.append((line, negated))
    return rules


def _to_regex(pattern: str) -> re.Pattern[str]:
    """Translate one dockerignore pattern to an anchored regex.

    ``**`` spans path separators, ``*`` and ``?`` do not.
    """
    out = ["^"]
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            # zero or more leading path segments
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def is_excluded(path: str, rules: list[tuple[str, bool]]) -> bool:
    """True if ``path`` would be withheld from the Docker build context.

    A path is excluded when it matches an exclusion rule directly, or when any
    ancestor directory does. A later negation re-includes it.
    """
    segments = path.split("/")
    candidates = ["/".join(segments[: n + 1]) for n in range(len(segments))]
    excluded = False
    for pattern, negated in rules:
        rx = _to_regex(pattern)
        if any(rx.match(c) for c in candidates):
            excluded = not negated
    return excluded


@pytest.fixture(scope="module")
def rules() -> list[tuple[str, bool]]:
    assert DOCKERIGNORE.is_file(), f"missing {DOCKERIGNORE}"
    return _parse(DOCKERIGNORE.read_text())


# --- the regression this file exists for --------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "e2e.env",
        "scripts/e2e.env",
        "scripts/e2e/e2e.env",
        "hiddenalerts-e2e.env",
        "config/prod-e2e.env",
        "deeply/nested/dir/e2e.env",
    ],
)
def test_e2e_credential_files_never_enter_the_build_context(path, rules):
    assert is_excluded(path, rules), (
        f"{path!r} would be copied into the image. An E2E credentials file was "
        "baked into a build layer this way once already."
    )


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        ".env.local",
        "server.pem",
        "tls/private.key",
        "credentials.json",
        "credentials-prod.json",
        "service-account.json",
    ],
)
def test_other_secret_material_is_excluded(path, rules):
    assert is_excluded(path, rules), f"{path!r} should not be in the build context"


# --- the converse: the fix must not starve the image --------------------------

@pytest.mark.parametrize(
    "path",
    [
        "Dockerfile",
        "requirements.txt",
        "alembic.ini",
        "pytest.ini",
        "app/main.py",
        "app/config.py",
        "app/scheduler/jobs.py",
        "app/pipeline/alert_pipeline.py",
        "alembic/env.py",
        "alembic/versions/0013_source_url_decisions.py",
        "scripts/e2e/common.py",
        "scripts/e2e/.env.e2e.example",
        ".env.example",
        ".env.production.example",
    ],
)
def test_required_build_files_are_still_included(path, rules):
    assert not is_excluded(path, rules), (
        f"{path!r} is needed to build or run the image but would be excluded"
    )


def test_no_actual_e2e_env_file_is_sitting_in_the_repository():
    """The harness env file belongs outside the repo; ignores are only a backstop."""
    offenders = [
        p.relative_to(BACKEND_ROOT).as_posix()
        for p in BACKEND_ROOT.rglob("*e2e.env")
        if ".git" not in p.parts
    ]
    assert offenders == [], f"E2E credential file(s) inside the repo: {offenders}"
