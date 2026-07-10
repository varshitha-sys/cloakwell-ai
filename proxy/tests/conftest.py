"""
Keep the default test run hermetic.

engine.py auto-loads the repo-root .env (so the proxy/API get Gemma creds without a
manual `source`). The side effect: importing engine during tests would feed REAL
Fireworks credentials into the suite, and any un-stubbed Tier 2 call would hit the
network. This fixture strips those creds for the whole session so the default
`pytest` stays offline, deterministic, and fast. Opt in to live tests with
FIREWORKS_LIVE=1 (see the live smoke test in test_tier2.py), which leaves the creds
in place.
"""
import os

import pytest

_LIVE = ("FIREWORKS_API_KEY", "FIREWORKS_MODEL", "FIREWORKS_BASE_URL")


@pytest.fixture(autouse=True, scope="session")
def hermetic_fireworks_env():
    if os.getenv("FIREWORKS_LIVE"):
        yield  # opt-in: keep real creds so live tests can reach Gemma
        return
    saved = {k: os.environ.pop(k, None) for k in _LIVE}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
