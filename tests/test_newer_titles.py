"""Films that came out after a customised keyword list was written still reach the right channels."""
import json
import os
import shutil
import tempfile
from pathlib import Path

from herotv import config, sortrules
from herotv.config import Config


def test_brand_new_day_goes_on_marvel_movies_and_spider_verse_with_an_old_list():
    d = tempfile.mkdtemp()
    for f in ("channels.json",):
        shutil.copy(Path(config.ROOT) / "config" / f, Path(d) / f)
    old = json.load(open(Path(config.ROOT) / "config" / "auto-sort.json", encoding="utf-8"))
    for r in old["rules"]:                                    # the list as it was before these films came out
        r["keywords"] = [k for k in r["keywords"] if k not in sortrules.NEWER.get("mcu", [])]
    (Path(d) / "auto-sort.json").write_text(json.dumps(old), encoding="utf-8")
    cfg = Config(media_dir=Path(d), db_path=os.path.join(d, "t.sqlite3"), channels_file=str(Path(d) / "channels.json"))
    rules, channels = sortrules.load(cfg)
    ids = [c["id"] for c in sortrules.targets("Spider-Man.Brand.New.Day.2026.1080p.WEB-DL.x264", rules, channels)]
    assert "mcu" in ids and "spider-verse" in ids
    assert "brand new day" not in (Path(d) / "auto-sort.json").read_text(encoding="utf-8")   # your file is left as it was


def test_marvel_studios_before_2008_is_not_mcu():
    import json
    from pathlib import Path
    from herotv import sortrules
    rules = json.loads((Path(__file__).parent.parent / "config" / "smart-sort.json").read_text(encoding="utf-8"))["rules"]
    ghost = {"type": "movie", "year": 2007, "genres": ["Thriller", "Action", "Fantasy"],
             "companies": ["Crystal Sky Pictures", "Columbia Pictures", "Marvel Studios"], "keywords": ["superhero"]}
    iron = {"type": "movie", "year": 2008, "genres": ["Action"], "companies": ["Marvel Studios"], "keywords": ["superhero"]}
    assert "mcu" not in sortrules.smart_channels(ghost, rules)
    assert "mcu" in sortrules.smart_channels(iron, rules)
