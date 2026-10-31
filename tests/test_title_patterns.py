"""File-name cleanup: release tags, editions, streaming and site labels are dropped; title, year, season and episode stay."""
import os
import unittest

from herotv import library as L


def guess(folder, name):
    return L._guess([folder, name], os.path.splitext(name)[0])


class Patterns(unittest.TestCase):
    def movie(self, name, title, year):
        d = guess("Movies", name)
        self.assertEqual((d["title"], d["year"], d["series"], d["episode"]), (title, year, "", 0), name)

    def test_movies_lose_everything_but_title_and_year(self):
        for name, title, year in (
                ("Oppenheimer.2023.IMAX.1080p.WEB-DL.DDP5.1.Atmos.H.264-FLUX.mkv", "Oppenheimer", 2023),
                ("Se7en 1995 REMASTERED 1080p BluRay DTS x264.mkv", "Se7en", 1995),
                ("Blade.Runner.2049.2017.German.DL.1080p.BluRay.x264-DETAiLS.mkv", "Blade Runner 2049", 2017),
                ("www.Torrenting.com - Joker 2019 720p HDRip.mp4", "Joker", 2019),
                ("Movie Title 2020 NF WEB-DL 1080p.mkv", "Movie Title", 2020),
                ("Léon.The.Professional.1994.Directors.Cut.1080p.mkv", "Léon The Professional", 1994),
                ("The Matrix (1999) [1080p] [YTS.MX].mp4", "The Matrix", 1999),
                ("1917.2019.1080p.BluRay.x264.mp4", "1917", 2019),
                ("300 (2006) 1080p BrRip x264 - YIFY.mp4", "300", 2006)):
            self.movie(name, title, year)

    def test_real_title_words_are_kept(self):
        for name, title, year in (("Johnny.English.2003.1080p.BluRay.mkv", "Johnny English", 2003),
                                  ("The Extended Family 2010 720p.mkv", "The Extended Family", 2010),
                                  ("Limited Partners (2012).mp4", "Limited Partners", 2012)):
            self.movie(name, title, year)

    def test_episodes_keep_show_season_episode_and_title(self):
        d = guess("Invincible", "Invincible - S02E03 - Title Here [WEBDL-1080p][EAC3 5.1][h264]-GROUP.mkv")
        self.assertEqual((d["series"], d["season"], d["episode"], d["title"]), ("Invincible", 2, 3, "Title Here"))
        d = guess("Show", "Better Call Saul Season 2 Episode 4 - Gloves Off.mkv")
        self.assertEqual((d["series"], d["season"], d["episode"], d["title"]), ("Better Call Saul", 2, 4, "Gloves Off"))
        d = guess("Show", "Naruto Shippuden Episode 123 English Dubbed HD.mp4")
        self.assertEqual((d["series"], d["episode"], d["title"]), ("Naruto Shippuden", 123, "Episode 123"))

    def test_videos_already_in_the_library_are_cleaned_but_user_names_are_kept(self):
        import json
        import shutil
        import tempfile
        from helpers import make_db, tmpdb
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        c = make_db(tmpdb())
        self.addCleanup(c.close)
        os.makedirs(os.path.join(root, "Movies"))
        paths = []
        for i, name in enumerate(("Oppenheimer.2023.IMAX.1080p.WEB-DL.mkv", "Se7en 1995 REMASTERED 1080p.mkv")):
            p = os.path.join(root, "Movies", name)
            paths.append(p)
            c.execute("INSERT INTO media(path,title,year,franchise,series,season,episode,verified,playable,available,ord,size) "
                      "VALUES(?,?,?,?,?,?,?,1,1,1,?,5)", (p, name[:-4].replace(".", " ")[:20], None, "Movies", "", 0, 0, i))
        with open(L.sidecar_path(paths[1]), "w", encoding="utf-8") as fh:
            json.dump({"title": "My Own Name"}, fh)                      # the user named this one
        c.execute("UPDATE media SET title='My Own Name' WHERE path=?", (paths[1],))
        self.assertEqual(L.refresh_names(c, root), 2)
        rows = {os.path.basename(r["path"]): (r["title"], r["year"]) for r in c.execute("SELECT path,title,year FROM media")}
        self.assertEqual(rows["Oppenheimer.2023.IMAX.1080p.WEB-DL.mkv"], ("Oppenheimer", 2023))
        self.assertEqual(rows["Se7en 1995 REMASTERED 1080p.mkv"], ("My Own Name", 1995))     # year filled, name kept
        self.assertEqual(L.refresh_names(c, root), 0)                                       # nothing left to change


if __name__ == "__main__":
    unittest.main()
