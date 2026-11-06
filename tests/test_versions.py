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


def test_different_lengths_and_series_stay_apart():
    out = versions.merge([row(1, "Dune", 1984, 1080, 4, rt=7000), row(2, "Dune", 1984, 1080, 5, rt=14000),
                          row(3, "Show", 2020, 1080, 1, series="Show"), row(4, "Show", 2020, 1080, 1, series="Show")])
    assert len(out) == 4 and not any("versions" in d for d in out)


def test_copy_without_a_year_joins_the_one_with_a_year():
    out = versions.merge([row(1, "Spider-Man Homecoming", 2017, 1080, 4), row(2, "Spider-man Homecoming", None, 1080, 3)])
    assert len(out) == 1 and len(out[0]["versions"]) == 2


def test_no_year_copy_never_picks_between_two_films():
    out = versions.merge([row(1, "Halloween", 1978, 1080, 4), row(2, "Halloween", 2007, 1080, 4), row(3, "Halloween", None, 1080, 4)])
    assert len(out) == 3


def test_watched_only_when_every_copy_is():
    out = versions.merge([row(1, "Up", 2009, 1080, 2, done=1), row(2, "Up", 2009, 720, 1)])
    assert out[0]["completed"] == 0
