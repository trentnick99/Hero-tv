"""Internet access for the few things that need it (weather, free movies).

Certificates are still fully checked. Only Python 3.13's extra-strict X.509 rule is relaxed, because it rejects
the certificates that many antivirus programs (and some routers/companies) put in the middle of secure connections
("Basic Constraints of CA cert not marked critical"), which made every secure website fail."""
import ssl
import urllib.request


def ssl_context():
    ctx = ssl.create_default_context()
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        ctx.verify_flags &= ~strict
    return ctx


def urlopen(req, timeout=30):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
