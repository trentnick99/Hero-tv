"""Titles TMDB writes differently from the file: a longer official name, a franchise word in front, numbers as words."""
from herotv import art


def R(t, y):
    return {"title": t, "original_title": t, "release_date": f"{y}-05-01", "id": 1}


def pick(t, y, *res):
    return (art._pick(list(res), t, y, "movie") or {}).get("title")


def test_longer_or_shorter_official_names():
    assert pick("Shang-Chi", 2021, R("Shang-Chi and the Legend of the Ten Rings", 2021)) == "Shang-Chi and the Legend of the Ten Rings"
    assert pick("X-Men Dark Phoenix", 2019, R("Dark Phoenix", 2019)) == "Dark Phoenix"
    assert pick("The Fantastic Four First Steps", 2025, R("The Fantastic 4: First Steps", 2025)) == "The Fantastic 4: First Steps"


def test_sequels_and_other_years_are_not_taken():
    assert pick("Iron Man", 2010, R("Iron Man 2", 2010)) is None
    assert pick("Deadpool", 2018, R("Deadpool 2", 2018)) is None
    assert pick("Halloween", 2009, R("Halloween II", 2009)) is None
    assert pick("Thor", 2011, R("Thor: The Dark World", 2013)) is None


def test_file_name_quirks():
    assert art.clean_movie("36. Thunderbolts", 2025) == ("Thunderbolts", 2025)
    assert art.clean_movie("Thunderboltsx", 2025)[0] == "Thunderbolts"
    assert art.clean_movie("1917", 2019) == ("1917", 2019)
    assert art.key_for({"title": "X-Men 2", "year": 2003, "series": "", "franchise": "X-Men", "season": 0, "episode": 0})[2] == "X2"


def test_spider_man_1994_not_the_2003_series():
    row = {"series": "Spider-Man The Animated Series", "title": "Doctor Strange", "season": 3, "episode": 1, "franchise": "MCU", "year": None}
    k, kind, name, year = art.key_for(row)
    assert (k, kind, year) == ("s:spider man the animated series", "tv", 1994)
    res = [{"name": "Spider-Man: The New Animated Series", "original_name": "Spider-Man: The New Animated Series", "first_air_date": "2003-07-11", "id": 2},
           {"name": "Spider-Man", "original_name": "Spider-Man", "first_air_date": "1994-11-19", "id": 1}]
    assert art._pick(res, name, year, "tv")["id"] == 1


def test_known_wrong_matches_are_looked_up_again(tmp_path):
    from herotv.db import connect
    c = connect(str(tmp_path / "t.sqlite3"))
    c.execute("INSERT INTO art(key,kind,title,fetched,miss) VALUES('s:spider man the animated series','tv','Spider-Man: The New Animated Series',1,0)")
    c.execute("INSERT INTO prefs(key,value) VALUES('art_match','4')")
    c.commit()
    art.pending(c)
    assert c.execute("SELECT COUNT(*) FROM art WHERE key='s:spider man the animated series'").fetchone()[0] == 0
