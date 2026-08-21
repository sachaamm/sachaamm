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
         "last_commit": "2024-07-01T00:00:00Z",
         "languages": {"C#": 11262791, "ShaderLab": 402424},
         "loc": {"written": {"C#": 1732258}, "vendored": {}}, "markers": [],
         "dependencies": [], "file_count": 20000},
        {"id": "private-007", "private": True, "primary_language": "TypeScript",
         "my_commits": 261, "created_at": "2023-01-01T00:00:00Z",
         "pushed_at": "2026-08-01T00:00:00Z", "languages": {"TypeScript": 900000},
         "loc": {"written": {"TypeScript": 537931}, "vendored": {}}, "markers": [],
         "dependencies": [], "file_count": 900},
    ],
}


def load_module():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(FIXTURE, f)
    os.environ["PROFILE_DATA"] = path
    for m in ("render_cards",):
        sys.modules.pop(m, None)
    import render_cards
    os.unlink(path)
    return render_cards


def render():
    m = load_module()
    return m.card_repos(m.THEMES["light"])[2]


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

    def test_legend_does_not_announce_a_colour_no_row_uses(self):
        # les deux repos de la fixture sont prives : annoncer "public" est faux
        self.assertNotIn("public", self.svg)
        self.assertIn("private", self.svg)

    def test_no_text_escapes_the_card_frame(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(self.svg if self.svg.startswith("<svg")
                             else f'<svg xmlns="http://www.w3.org/2000/svg" width="840">{self.svg}</svg>')
        for el in root.iter("{http://www.w3.org/2000/svg}text"):
            x, size = float(el.get("x")), float(el.get("font-size"))
            w = len(el.text or "") * size * 0.55
            anchor = el.get("text-anchor", "start")
            x0 = x - w if anchor == "end" else x
            self.assertGreaterEqual(x0, 4, f"deborde a gauche : {el.text!r}")
            self.assertLessEqual(x0 + w, 836, f"deborde a droite : {el.text!r}")

    def test_states_that_counts_include_asset_imports(self):
        self.assertIn("imports included", self.svg)


class TestOverviewCard(unittest.TestCase):
    """La carte overview doit compter comme le reste : lignes ecrites, pas octets bruts."""

    @classmethod
    def setUpClass(cls):
        m = load_module()
        cls.svg = m.card_overview(m.THEMES["light"])[2]

    def test_domain_split_uses_written_lines_not_raw_bytes(self):
        # fixture : C# vaut 77.5 % des octets mais 76.3 % des lignes ecrites.
        # Le code tiers ne doit pas gonfler la repartition par domaine.
        self.assertIn("76.3%", self.svg)
        self.assertNotIn("77.5%", self.svg)

    def test_states_both_the_public_and_the_private_count(self):
        # 171 private sans 58 public obligeait le lecteur a faire la soustraction
        self.assertIn("1 public", self.svg)
        self.assertIn("1 private", self.svg)

    def test_unity_csharp_is_credited_to_graphics_not_to_backend(self):
        # la fixture : tout le C# vit dans un depot a shaders
        import xml.etree.ElementTree as ET
        root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{self.svg}</svg>')
        legend = [el.text for el in root.iter("{http://www.w3.org/2000/svg}text")
                  if el.get("y") == "240"]
        pairs = dict(zip(legend[::2], legend[1::2]))
        self.assertEqual(pairs["Graphics / Unity"], "76.3%")
        self.assertEqual(pairs[".NET Backend"], "0.0%")

    def test_headline_loc_matches_the_written_total(self):
        self.assertIn("3.8M", self.svg)   # totals.loc_written = 3 760 000


if __name__ == "__main__":
    unittest.main(verbosity=2)
