"""Carte GitHub at a glance : repartition des lignes privees / publiques."""
import json, os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

BASE = {
    "schema": "github-profile/1.2",
    "account": {"login": "sachaamm", "years_on_github": 11.4},
    "totals": {"repos": 2, "private": 1, "public": 1, "my_commits": 100,
               "files_indexed": 1000, "loc_written": 1000, "loc_vendored": 0,
               "churn_additions": 0, "churn_deletions": 0},
    "language_bytes": {"C#": 1000, "TypeScript": 1000},
    "loc_by_language": {"C#": 800, "TypeScript": 200},
    "loc_vendored_by_language": {}, "stack_markers": {}, "top_dependencies": {},
    "commits_by_month": {"2026-01": 100}, "file_extensions": {}, "ci_workflows": {},
    "named_repos": [],
}


def repo(rid, private, written):
    return {"id": rid, "private": private, "primary_language": "C#",
            "my_commits": 10, "created_at": "2026-01-01T00:00:00Z",
            "pushed_at": "2026-01-02T00:00:00Z", "languages": {"C#": written},
            "loc": {"written": {"C#": written}, "vendored": {}},
            "markers": [], "dependencies": [], "file_count": 10}


def render(repos):
    fd, path = tempfile.mkstemp(suffix=".json")
    payload = dict(BASE, repos=repos)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.environ["PROFILE_DATA"] = path
    os.environ["CLAUDE_DATA"] = os.path.join(tempfile.gettempdir(), "absent-xyz.json")
    sys.modules.pop("render_cards", None)
    import render_cards
    os.unlink(path)
    return render_cards.card_overview(render_cards.THEMES["light"])


class TestVisibilitySplit(unittest.TestCase):
    def test_private_share_is_stated(self):
        _, _, svg = render([repo("moi/prive", True, 800), repo("moi/public", False, 200)])
        self.assertIn("LINES WRITTEN, BY REPOSITORY VISIBILITY", svg)
        self.assertIn("private 800 · 80%", svg)

    def test_public_segment_is_labelled_when_it_fits(self):
        _, _, svg = render([repo("moi/prive", True, 600), repo("moi/public", False, 400)])
        self.assertIn("public 400", svg)

    def test_a_narrow_segment_is_not_labelled_over_its_neighbour(self):
        # 2 % de large : y ecrire un libelle deborderait sur le segment voisin.
        _, _, svg = render([repo("moi/prive", True, 9800), repo("moi/public", False, 200)])
        self.assertNotIn("public 200", svg)
        self.assertIn("private", svg)

    def test_the_percentage_is_dropped_when_the_segment_is_only_medium(self):
        # Assez large pour le nom, trop etroit pour le nom ET le pourcentage.
        _, _, svg = render([repo("moi/prive", True, 780), repo("moi/public", False, 220)])
        self.assertIn("public 220", svg)
        self.assertNotIn("public 220 ·", svg)

    def test_segments_fill_the_card_width_exactly(self):
        w, _, svg = render([repo("moi/prive", True, 700), repo("moi/public", False, 300)])
        widths = [float(x) for x in
                  re.findall(r'<rect x="[\d.]+" y="282" width="([\d.]+)"', svg)]
        self.assertEqual(len(widths), 2)
        # -2 px de gouttiere sur chaque segment, comme la barre par domaine
        self.assertAlmostEqual(sum(widths) + 4, w - 48, delta=0.5)

    def test_everything_stays_inside_the_taller_frame(self):
        w, h, svg = render([repo("moi/prive", True, 700), repo("moi/public", False, 300)])
        self.assertEqual(h, 330)
        for x, y in re.findall(r'<(?:rect|text) x="([\d.]+)" y="([\d.]+)"', svg):
            self.assertLessEqual(float(x), w - 24)
            self.assertLessEqual(float(y), h)

    def test_all_private_does_not_divide_by_zero(self):
        _, _, svg = render([repo("moi/prive", True, 500)])
        self.assertIn("private 500 · 100%", svg)


if __name__ == "__main__":
    unittest.main()
