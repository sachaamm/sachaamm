"""Rendu de la carte Top repositories, sur données maîtrisées."""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

FIXTURE = {
    "schema": "github-profile/1.2",
    "account": {"login": "sachaamm", "years_on_github": 11.6},
    "totals": {"repos": 2, "private": 1, "public": 1, "my_commits": 748,
               "files_indexed": 40000, "loc_written": 3760000, "loc_vendored": 1710000,
               "churn_additions": 91938973, "churn_deletions": 41275746},
    "language_bytes": {"C#": 53700000, "TypeScript": 15600000},
    "loc_by_language": {"C#": 1732258, "TypeScript": 537931},
    "loc_vendored_by_language": {"ShaderLab": 1660000},
    "stack_markers": {"Angular": 5, "Docker": 9},
    "top_dependencies": {"@nestjs/core": 6},
    "commits_by_month": {"2021-01": 40, "2024-06": 30},
    "file_extensions": {}, "ci_workflows": {},
    "named_repos": ["sachaamm/generativeroads"],
    "repos": [
        {"id": "sachaamm/generativeroads", "private": True, "primary_language": "C#",
         "my_commits": 487, "churn_additions": 54074266, "churn_deletions": 37184798,
         "churn": 91259064, "created_at": "2021-03-01T00:00:00Z",
         "pushed_at": "2024-07-07T00:00:00Z", "first_commit": "2021-04-01T00:00:00Z",
         "last_commit": "2024-07-01T00:00:00Z", "languages": {"C#": 11262791},
         "loc": {"written": {"C#": 363316}, "vendored": {}}, "markers": [],
         "dependencies": [], "file_count": 20000},
        {"id": "private-007", "private": True, "primary_language": "TypeScript",
         "my_commits": 261, "created_at": "2023-01-01T00:00:00Z",
         "pushed_at": "2026-08-01T00:00:00Z", "languages": {"TypeScript": 900000},
         "loc": {"written": {"TypeScript": 31034}, "vendored": {}}, "markers": [],
         "dependencies": [], "file_count": 900},
    ],
}


def render():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(FIXTURE, f)
    os.environ["PROFILE_DATA"] = path
    for m in ("render_cards",):
        sys.modules.pop(m, None)
    import render_cards
    w, h, svg = render_cards.card_repos(render_cards.THEMES["light"])
    os.unlink(path)
    return svg


class TestReposCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svg = render()

    def test_columns_are_labelled_so_nothing_needs_decoding(self):
        for col in ("REPOSITORY", "COMMITS", "LINES ADDED", "LINES DELETED", "PERIOD"):
            self.assertIn(col, self.svg, f"colonne manquante : {col}")

    def test_shows_the_real_name_of_a_whitelisted_repo(self):
        self.assertIn("generativeroads", self.svg)

    def test_keeps_anonymised_repos_anonymous(self):
        self.assertIn("private-007", self.svg)

    def test_formats_added_and_deleted_lines_readably(self):
        self.assertIn("+54.1M", self.svg)
        self.assertIn("−37.2M", self.svg)   # vrai signe moins

    def test_shows_the_activity_period(self):
        self.assertIn("2021", self.svg)
        self.assertIn("2024", self.svg)

    def test_missing_churn_is_shown_as_a_dash_not_a_zero(self):
        # private-007 n'a pas de churn : afficher 0 serait un mensonge
        self.assertNotIn("+0", self.svg)
        self.assertIn("—", self.svg)

    def test_states_that_counts_include_asset_imports(self):
        self.assertIn("imports included", self.svg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
