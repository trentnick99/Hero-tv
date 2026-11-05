from herotv import versions


def row(i, title, year, h, size, rt=6000, pos=0, done=0, series="", path=None):
    return {"id": i, "title": title, "year": year, "series": series, "height": h, "size": size, "runtime_s": rt,
            "position": pos, "completed": done, "favorite": 0, "path": path or f"/m/{title}{i}.mkv"}


def test_same_film_merges_best_picture_first():
    out = versions.merge([row(1, "The Hangover", 2009, 720, 1), row(2, "Other", 2001, 1080, 5),
                          row(3, "The  Hangover!", 2009, 1080, 4)])
    assert [d["id"] for d in out] == [3, 2]
    assert [v["id"] for v in out[0]["versions"]] == [3, 1]          # 1080p before 720p
    assert "versions" not in out[1] and "path" not in out[1]


def test_resumed_copy_stands_for_the_film():
    out = versions.merge([row(1, "Heat", 1995, 2160, 9), row(2, "Heat", 1995, 720, 1, pos=300)])
    assert out[0]["id"] == 2


def test_different_lengths_series_and_no_year_stay_apart():
    out = versions.merge([row(1, "Dune", 1984, 1080, 4, rt=7000), row(2, "Dune", 1984, 1080, 5, rt=14000),
                          row(3, "Show", 2020, 1080, 1, series="Show"), row(4, "Show", 2020, 1080, 1, series="Show"),
                          row(5, "Clip", None, 480, 1), row(6, "Clip", None, 480, 1)])
    assert len(out) == 6 and not any("versions" in d for d in out)


def test_watched_only_when_every_copy_is():
    out = versions.merge([row(1, "Up", 2009, 1080, 2, done=1), row(2, "Up", 2009, 720, 1)])
    assert out[0]["completed"] == 0
