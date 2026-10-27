"""Internet access for the few things that need it (weather, free movies, update checks).

Certificates are always fully checked. Two things make that work on more PCs:
- Python 3.13's extra-strict X.509 rule is relaxed, because it rejects the certificates that many antivirus programs
  (and some routers/companies) put in the middle of secure connections ("Basic Constraints of CA cert not marked
  critical"), which made every secure website fail.
- When a certificate is refused, it is tried again: first after asking Windows itself to check the site once
  (Windows then downloads a root certificate it did not have yet - Python only sees the roots Windows already
  has), then with the up-to-date list of trusted roots that comes with HERO TV (certifi), if present."""
import os
import ssl
import subprocess
import urllib.error
import urllib.request


def ssl_context(cafile=None):
    ctx = ssl.create_default_context(cafile=cafile)
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        ctx.verify_flags &= ~strict
    return ctx


def is_cert_error(e):
    r = getattr(e, "reason", e)
    return isinstance(r, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(r)


def _windows_check(url, timeout=20):
    """Let Windows look at the site once (its own secure connection fetches missing root certificates)."""
    if os.name != "nt":
        return False
    from . import tools
    ps = "try { Invoke-WebRequest -UseBasicParsing -Method Head -TimeoutSec 15 -Uri $env:HT_URL | Out-Null } catch { }"
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       timeout=timeout, env=dict(os.environ, HT_URL=url), **tools.HIDE)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _bundled_roots():
    try:
        import certifi
        p = certifi.where()
        return p if os.path.isfile(p) else None
    except Exception:
        return None


def urlopen(req, timeout=30, _win=_windows_check, _roots=_bundled_roots):
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
    except urllib.error.URLError as e:
        if not is_cert_error(e):
            raise
        first = e
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    if _win(url):
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
        except urllib.error.URLError as e:
            if not is_cert_error(e):
                raise
    roots = _roots()
    if roots:
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=ssl_context(roots))
        except urllib.error.URLError as e:
            if not is_cert_error(e):
                raise
    raise first
