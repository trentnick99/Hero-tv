"""/health and /metrics for a homelab: Uptime Kuma, Grafana, Prometheus, Home Assistant. Counts only, never titles or addresses."""
import shutil
import time

from . import __version__

STARTED = time.time()


def health():
    return {"ok": True, "version": __version__, "uptime_s": int(time.time() - STARTED)}


def _count(c, sql):
    try:
        return c.execute(sql).fetchone()[0] or 0
    except Exception:
        return 0


def metrics(c, media_dir=None):
    """Prometheus text format."""
    rows = [
        ("herotv_up", "1 while HERO TV answers", 1),
        ("herotv_uptime_seconds", "Seconds since HERO TV started", int(time.time() - STARTED)),
        ("herotv_videos", "Videos in the library", _count(c, "SELECT COUNT(*) FROM media WHERE available=1")),
        ("herotv_videos_playable", "Videos that play", _count(c, "SELECT COUNT(*) FROM media WHERE available=1 AND verified=1 AND playable=1")),
        ("herotv_videos_problem", "Videos that need attention", _count(c, "SELECT COUNT(*) FROM media WHERE available=1 AND (playable=0 OR verified=0)")),
        ("herotv_copies_ready", "Ready copies made", _count(c, "SELECT COUNT(*) FROM prepared WHERE status='ready'")),
        ("herotv_copies_failed", "Ready copies that failed", _count(c, "SELECT COUNT(*) FROM prepared WHERE status='failed'")),
        ("herotv_copies_waiting", "Repairs waiting in line", _count(c, "SELECT COUNT(*) FROM prepared WHERE status='fix'")),
        ("herotv_paired_devices", "Paired phones, tablets and TVs", _count(c, "SELECT COUNT(*) FROM devices")),
    ]
    if media_dir:
        try:
            rows.append(("herotv_media_free_bytes", "Free space on the media drive", shutil.disk_usage(media_dir).free))
        except OSError:
            pass
    out = ["# HELP herotv_info HERO TV version", "# TYPE herotv_info gauge", f'herotv_info{{version="{__version__}"}} 1']
    for name, help_, v in rows:
        out += [f"# HELP {name} {help_}", f"# TYPE {name} gauge", f"{name} {v}"]
    return "\n".join(out) + "\n"
