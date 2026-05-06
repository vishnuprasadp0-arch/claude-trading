import os
import ssl

# ── Root cause ────────────────────────────────────────────────────────────────
# OpenSSL 3.6 + Python 3.14 on macOS has two problems for YouTube:
#   1. VERIFY_X509_STRICT rejects intermediate CAs with non-critical Basic
#      Constraints (YouTube's chain fails this).
#   2. certifi's bundle is missing the specific intermediate CA used by
#      YouTube's API endpoint; the Homebrew OpenSSL store (197 certs) has it.
#
# Fix: patch all SSL layers — ssl module, urllib3, yt-dlp, and requests
# (used by youtube-transcript-api) — to use system certs + skip STRICT flag.
# ─────────────────────────────────────────────────────────────────────────────

# 0. Point requests (and any other library that respects these env vars) to the
#    Homebrew OpenSSL CA bundle which contains YouTube's intermediate CA.
_SYSTEM_CA = "/opt/homebrew/etc/openssl@3/cert.pem"
if os.path.exists(_SYSTEM_CA):
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _SYSTEM_CA)
    os.environ.setdefault("CURL_CA_BUNDLE", _SYSTEM_CA)
    os.environ.setdefault("SSL_CERT_FILE", _SYSTEM_CA)

_STRICT = getattr(ssl, "VERIFY_X509_STRICT", 0)


def _clear_strict(ctx: ssl.SSLContext) -> ssl.SSLContext:
    if _STRICT:
        ctx.verify_flags &= ~_STRICT
    return ctx


# 1. Patch ssl.create_default_context (used by urllib.request, some libraries)
_orig_cdc = ssl.create_default_context

def _patched_cdc(*args, **kwargs):
    return _clear_strict(_orig_cdc(*args, **kwargs))

ssl.create_default_context = _patched_cdc


# 2. Zero out urllib3's VERIFY_X509_STRICT constant so it ORs in 0
try:
    import urllib3.util.ssl_ as _u3ssl
    _u3ssl.VERIFY_X509_STRICT = 0
except Exception:
    pass


# 3. Patch yt-dlp's ssl_load_certs to use system certs and clear the flag
try:
    import yt_dlp.networking._helper as _ydl_helper

    def _patched_ssl_load_certs(context: ssl.SSLContext, use_certifi: bool = True) -> None:
        context.load_default_certs()
        _clear_strict(context)

    _ydl_helper.ssl_load_certs = _patched_ssl_load_certs
except Exception:
    pass
