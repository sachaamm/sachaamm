"""Fenetre d'activite et enrichissement des depots vivants."""
import base64, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from statslib import (months_before, repos_active_since, apply_naming,
                      repos_to_name, ANONYMOUS_STRIPS)
from collect import surface, fetch_readme, README_CHARS


class TestWindow(unittest.TestCase):
    def test_months_before_crosses_the_year(self):
        self.assertEqual(months_before("2026-08", 8), "2025-12")
        self.assertEqual(months_before("2026-01", 1), "2025-12")
        self.assertEqual(months_before("2026-01", 12), "2025-01")

    def test_months_before_january_stays_january(self):
        self.assertEqual(months_before("2026-03", 0), "2026-03")

    def test_active_uses_last_commit(self):
        repos = [{"id": "vivant", "last_commit": "2026-03"},
                 {"id": "dormant", "last_commit": "2025-06"}]
        self.assertEqual(repos_active_since(repos, "2025-12"), {"vivant"})

    def test_pushed_at_is_the_fallback(self):
        # Un depot dont aucun commit n'a ete date ne doit pas disparaitre.
        repos = [{"id": "sans-date", "pushed_at": "2026-02-01T00:00:00Z"}]
        self.assertEqual(repos_active_since(repos, "2025-12"), {"sans-date"})

    def test_a_repo_with_no_date_at_all_is_not_active(self):
        self.assertEqual(repos_active_since([{"id": "vide"}], "2025-12"), set())


class TestAnonymisationCoversEnrichment(unittest.TestCase):
    """Le point sensible : un README identifie un depot mieux qu'un nom."""

    def entries(self):
        return [
            {"id": "moi/actif", "private": True, "my_commits": 50,
             "description": "Bot de trading", "homepage": "https://x.example",
             "topics": ["trading"], "readme": {"excerpt": "# Binance bot"},
             "structure": {"top_dirs": [{"name": "src", "files": 12}]}},
            {"id": "moi/dormant", "private": True, "my_commits": 1,
             "description": "Vieux projet client", "homepage": "https://y.example",
             "topics": ["client"], "readme": {"excerpt": "# Projet Machin"},
             "structure": {"top_dirs": [{"name": "app", "files": 3}]}},
        ]

    def test_named_repo_keeps_everything(self):
        e = self.entries()
        apply_naming(e, named={"moi/actif"})
        self.assertEqual(e[0]["id"], "moi/actif")
        self.assertEqual(e[0]["readme"]["excerpt"], "# Binance bot")

    def test_anonymous_repo_keeps_nothing_identifying(self):
        e = self.entries()
        apply_naming(e, named={"moi/actif"})
        self.assertEqual(e[1]["id"], "private-001")
        for field in ANONYMOUS_STRIPS:
            self.assertNotIn(field, e[1], "%s a survecu a l'anonymisation" % field)

    def test_every_strip_is_declared(self):
        # Ajouter un champ identifiant sans l'inscrire ici le publierait.
        self.assertEqual(set(ANONYMOUS_STRIPS),
                         {"description", "homepage", "topics", "readme", "structure"})

    def test_public_repos_are_never_anonymised(self):
        e = [{"id": "moi/public", "private": False, "description": "ouvert"}]
        apply_naming(e, named=set())
        self.assertEqual(e[0]["id"], "moi/public")
        self.assertEqual(e[0]["description"], "ouvert")


class TestSurface(unittest.TestCase):
    def test_top_dirs_are_ranked_by_file_count(self):
        paths = ["src/a.ts", "src/b.ts", "src/c.ts", "docs/x.md", "README.md"]
        out = surface(paths)
        self.assertEqual(out["top_dirs"][0], {"name": "src", "files": 3})
        self.assertEqual(out["top_dirs"][1], {"name": "docs", "files": 1})

    def test_root_files_are_listed_separately(self):
        out = surface(["package.json", "README.md", "src/a.ts"])
        self.assertEqual(out["root_files"], ["README.md", "package.json"])
        self.assertNotIn("src/a.ts", out["root_files"])

    def test_empty_repo_does_not_explode(self):
        self.assertEqual(surface([]), {"top_dirs": [], "root_files": []})


class FakeGH:
    def __init__(self, payload):
        self.payload = payload

    def get(self, path, params=None, raw=False):
        return self.payload, {}


class TestFetchReadme(unittest.TestCase):
    def payload(self, text):
        return {"name": "README.md",
                "content": base64.b64encode(text.encode("utf-8")).decode()}

    def test_decodes_and_reports_the_real_length(self):
        out = fetch_readme(FakeGH(self.payload("# Titre\n\nDu texte.")), "moi/x")
        self.assertEqual(out["excerpt"], "# Titre\n\nDu texte.")
        self.assertEqual(out["chars"], len("# Titre\n\nDu texte."))

    def test_long_readme_is_cut_but_its_size_is_kept(self):
        long = "x" * (README_CHARS + 500)
        out = fetch_readme(FakeGH(self.payload(long)), "moi/x")
        self.assertEqual(len(out["excerpt"]), README_CHARS)
        self.assertEqual(out["chars"], README_CHARS + 500)

    def test_missing_readme_is_none_not_empty_string(self):
        self.assertIsNone(fetch_readme(FakeGH(None), "moi/x"))
        self.assertIsNone(fetch_readme(FakeGH({}), "moi/x"))

    def test_broken_base64_does_not_kill_the_run(self):
        self.assertIsNone(fetch_readme(FakeGH({"content": "!!!pas du base64!!!"}), "moi/x"))


class TestWhitelistUnion(unittest.TestCase):
    def test_active_repos_join_the_ranked_ones(self):
        repos = [{"id": "a", "my_commits": 100, "last_commit": "2024-01"},
                 {"id": "b", "my_commits": 1, "last_commit": "2026-05"},
                 {"id": "c", "my_commits": 2, "last_commit": "2024-02"}]
        named = repos_to_name(repos, top_n=1) | repos_active_since(repos, "2025-12")
        self.assertEqual(named, {"a", "b"})   # a par le classement, b par l'activite


if __name__ == "__main__":
    unittest.main()
