"""Instantane Claude Code : collecte anonymisee, puis rendu de la carte."""
import contextlib, io, json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Le profil GitHub est charge au moment de l'import de render_cards : la carte
# Claude Code n'en tire rien, mais le module refuse de s'importer sans lui.
PROFILE = {
    "schema": "github-profile/1.2",
    "account": {"login": "sachaamm", "years_on_github": 11.6},
    "totals": {"repos": 1, "private": 0, "public": 1, "my_commits": 10,
               "files_indexed": 10, "loc_written": 100, "loc_vendored": 0,
               "churn_additions": 100, "churn_deletions": 10},
    "language_bytes": {"TypeScript": 1000}, "loc_by_language": {"TypeScript": 100},
    "loc_vendored_by_language": {}, "stack_markers": {}, "top_dependencies": {},
    "commits_by_month": {"2026-01": 10}, "file_extensions": {}, "ci_workflows": {},
    "named_repos": [],
    "repos": [{"id": "sachaamm/x", "private": False, "primary_language": "TypeScript",
               "my_commits": 10, "created_at": "2026-01-01T00:00:00Z",
               "pushed_at": "2026-01-02T00:00:00Z", "languages": {"TypeScript": 1000},
               "loc": {"written": {"TypeScript": 100}, "vendored": {}},
               "markers": [], "dependencies": [], "file_count": 10}],
}

SNAPSHOT = {
    "schema": "claude-code-usage/1.0",
    "generated_at": "2026-08-22T09:00:00Z",
    "machine": "MacBook Air",
    "anonymized": True,
    "period": {"first": "2026-01-06", "last": "2026-08-22"},
    "totals": {"sessions": 245, "transcripts_on_disk": 158, "agents": 529,
               "prompts": 1239, "projects": 29},
    "prompts_by_month": {"2026-06": 216, "2026-07": 422, "2026-08": 512},
    "agents_by_model": {"sonnet": 370, "opus": 92, "haiku": 59},
    "agents_by_type": {"general-purpose": 529}, "agents_nested": 3,
    "projects": [{"key": "project-01", "sessions": 108, "transcripts": 123,
                  "agents": 243, "prompts": 576}],
}


def write_json(payload):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def load_module(snapshot=SNAPSHOT):
    profile = write_json(PROFILE)
    os.environ["PROFILE_DATA"] = profile
    if snapshot is None:
        os.environ["CLAUDE_DATA"] = os.path.join(tempfile.gettempdir(), "absent-xyz.json")
        claude = None
    else:
        claude = write_json(snapshot)
        os.environ["CLAUDE_DATA"] = claude
    sys.modules.pop("render_cards", None)
    import render_cards
    os.unlink(profile)
    if claude:
        os.unlink(claude)
    return render_cards


class TestClaudeCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()
        cls.w, cls.h, cls.svg = cls.m.card_claude(cls.m.THEMES["light"])

    def test_kpis_are_printed(self):
        for n in ("245", "529", "1 239", "29"):
            self.assertIn(">%s<" % n, self.svg)

    def test_scope_is_stated_not_implied(self):
        # Le lecteur doit savoir que le chiffre couvre un seul poste et une
        # seule date : sans cela il le lit comme un total.
        self.assertIn("MacBook Air only", self.svg)
        self.assertIn("not auto-refreshed", self.svg)
        self.assertIn("2026-01-06", self.svg)

    def test_both_session_figures_are_published(self):
        # 245 sessions vues dans l'historique, 158 transcripts restants :
        # n'afficher que le premier laisserait croire a 245 transcripts.
        self.assertIn("158 transcripts still on disk", self.svg)

    def test_month_bars_use_short_labels(self):
        for label in ("Jul", "Aug"):
            self.assertIn(">%s<" % label, self.svg)

    def test_first_bar_carries_the_year(self):
        # Sur une periode a cheval sur deux annees, "Jan" seul est ambigu.
        self.assertIn(">Jun 26<", self.svg)

    def test_model_bar_spans_the_full_width_exactly(self):
        import re
        widths = [float(w) for x, y, w in
                  re.findall(r'<rect x="([\d.]+)" y="(266)" width="([\d.]+)"', self.svg)]
        self.assertEqual(len(widths), 3)
        self.assertAlmostEqual(sum(widths), self.w - 48, delta=0.5)

    def test_content_stays_inside_the_frame(self):
        import re
        for x, y in re.findall(r'<(?:rect|text) x="([\d.]+)" y="([\d.]+)"', self.svg):
            self.assertLessEqual(float(x), self.w - 24)
            self.assertLessEqual(float(y), self.h)


class TestMachineSectionOnCard(unittest.TestCase):
    """La carte doit nommer les postes, pas seulement leur somme."""

    @classmethod
    def setUpClass(cls):
        snap = dict(SNAPSHOT)
        snap["machines"] = [
            {"name": "Tour", "source": "collector",
             "totals": {"sessions": 1546, "agents": 19, "prompts": 6249}},
            {"name": "MacBook Air", "source": "collector",
             "totals": {"sessions": 245, "agents": 529, "prompts": 1249}},
        ]
        m = load_module(snapshot=snap)
        cls.w, cls.h, cls.svg = m.card_claude(m.THEMES["light"])

    def test_each_machine_is_named_with_its_own_figures(self):
        self.assertIn(">Tour<", self.svg)
        self.assertIn(">MacBook Air<", self.svg)
        self.assertIn(">1\u2009546<", self.svg)   # espace fine, comme nfmt
        self.assertIn(">245<", self.svg)

    def test_subtitle_names_both_instead_of_claiming_one(self):
        self.assertIn("Tour + MacBook Air", self.svg)
        self.assertNotIn("only \u00b7", self.svg)

    def test_card_grew_to_fit_the_section(self):
        self.assertGreater(self.h, 308)

    def test_nothing_spills_out_of_the_taller_frame(self):
        import re
        for x, y in re.findall(r'<(?:rect|text) x="([\d.-]+)" y="([\d.-]+)"', self.svg):
            self.assertLessEqual(float(x), self.w - 24)
            self.assertLessEqual(float(y), self.h)


class TestMultipleMachines(unittest.TestCase):
    """Fusion de deux postes dans un seul instantane."""

    def setUp(self):
        import collect_claude
        self.mod = collect_claude
        self.mac = {
            "name": "MacBook Air", "source": "collector",
            "period": {"first": "2026-01-06", "last": "2026-08-22"},
            "totals": {"sessions": 245, "transcripts_on_disk": 158,
                       "agents": 529, "prompts": 1249, "projects": 29},
            "prompts_by_month": {"2026-07": 422, "2026-08": 512},
            "agents_by_model": {"sonnet": 370}, "agents_by_type": {}, "agents_nested": 3,
        }
        self.tour = {
            "name": "Tour", "source": "collector",
            "period": {"first": "2025-10-03", "last": "2026-08-19"},
            "totals": {"sessions": 1546, "transcripts_on_disk": 151,
                       "agents": 19, "prompts": 6249, "projects": 101},
            "prompts_by_month": {"2025-10": 30, "2026-08": 187},
            "agents_by_model": {"unknown": 19}, "agents_by_type": {}, "agents_nested": 0,
        }

    def test_totals_are_the_sum(self):
        a = self.mod.aggregate([self.tour, self.mac])
        self.assertEqual(a["totals"]["sessions"], 1791)
        self.assertEqual(a["totals"]["agents"], 548)
        self.assertEqual(a["totals"]["prompts"], 7498)

    def test_period_spans_both(self):
        a = self.mod.aggregate([self.tour, self.mac])
        self.assertEqual(a["period"], {"first": "2025-10-03", "last": "2026-08-22"})

    def test_months_are_added_not_replaced(self):
        a = self.mod.aggregate([self.tour, self.mac])
        self.assertEqual(a["prompts_by_month"]["2026-08"], 512 + 187)
        self.assertEqual(a["prompts_by_month"]["2025-10"], 30)

    def test_recollecting_a_machine_replaces_it(self):
        # Relancer la collecte sur un poste ne doit pas le compter deux fois.
        again = dict(self.mac, totals=dict(self.mac["totals"], sessions=250))
        merged = self.mod.upsert([self.tour, self.mac], again)
        self.assertEqual(len(merged), 2)
        self.assertEqual(self.mod.aggregate(merged)["totals"]["sessions"], 1546 + 250)

    def test_a_machine_without_model_detail_does_not_fake_a_zero(self):
        # La commande courte ne donne pas la repartition par modele : le poste
        # est exclu de cette somme, et la carte peut le dire.
        reported = {k: v for k, v in self.tour.items() if k != "agents_by_model"}
        a = self.mod.aggregate([reported, self.mac])
        self.assertEqual(a["agents_by_model"], {"sonnet": 370})
        self.assertEqual(a["model_split_machines"], 1)

    def test_months_parser_rejects_junk(self):
        self.assertEqual(self.mod.parse_months("2026-03:10,2026-04:50"),
                         {"2026-03": 10, "2026-04": 50})
        with self.assertRaises(SystemExit):
            self.mod.parse_months("mars:10")


class TestCardIsOptional(unittest.TestCase):
    def test_missing_snapshot_drops_the_card(self):
        # Un checkout qui n'a jamais lance collect_claude.py doit rendre les
        # cinq autres cartes, pas une carte Claude Code remplie de zeros.
        m = load_module(snapshot=None)
        self.assertNotIn("claude", m.CARDS)
        self.assertIn("overview", m.CARDS)


class TestCollector(unittest.TestCase):
    """Collecte sur une arborescence ~/.claude fabriquee de toutes pieces."""

    def setUp(self):
        import collect_claude
        self.mod = collect_claude
        self.tmp = tempfile.mkdtemp()
        proj = "-Users-alex-Documents-GitHub-client-secret-app"
        sess = os.path.join(self.tmp, "projects", proj, "s-1", "subagents")
        os.makedirs(sess)
        open(os.path.join(self.tmp, "projects", proj, "s-1.jsonl"), "w").close()
        for i, model in enumerate(("sonnet", "opus")):
            with open(os.path.join(sess, "agent-%d.meta.json" % i), "w") as f:
                json.dump({"agentType": "general-purpose", "model": model,
                           "spawnDepth": 1}, f)
        with open(os.path.join(self.tmp, "history.jsonl"), "w", encoding="utf-8") as f:
            for sid in ("a", "a", "b"):
                f.write(json.dumps({
                    "display": "secret de fabrication du client",
                    "project": "/Users/alex/Documents/GitHub/client_secret_app",
                    "sessionId": sid, "timestamp": 1770000000000}) + "\n")
            f.write("{ ligne tronquee\n")

    def run_collect(self, extra=()):
        out = os.path.join(self.tmp, "out.json")
        argv = sys.argv
        sys.argv = ["collect_claude.py", "--claude-home", self.tmp,
                    "--machine", "Tour", "--out", out] + list(extra)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.mod.main()
        finally:
            sys.argv = argv
        with open(out, encoding="utf-8") as f:
            raw = f.read()
        return raw, json.loads(raw)

    def test_counts(self):
        _, d = self.run_collect()
        self.assertEqual(d["totals"]["sessions"], 2)          # a et b
        self.assertEqual(d["totals"]["prompts"], 3)           # la ligne cassee est ignoree
        self.assertEqual(d["totals"]["transcripts_on_disk"], 1)
        self.assertEqual(d["totals"]["agents"], 2)
        self.assertEqual(d["totals"]["projects"], 1)
        self.assertEqual(d["agents_by_model"], {"sonnet": 1, "opus": 1})

    def test_nothing_identifying_leaves_the_machine(self):
        raw, d = self.run_collect()
        self.assertNotIn("client", raw)         # ni le nom du projet
        self.assertNotIn("secret", raw)         # ni le texte des prompts
        self.assertNotIn("/Users/", raw)        # ni le chemin du poste
        self.assertEqual(d["machines"][0]["projects"][0]["key"], "project-01")
        self.assertTrue(d["anonymized"])

    def test_totals_sit_at_the_top_level_whatever_the_machine_count(self):
        # Les cartes lisent le total la ou il a toujours ete : un poste de
        # plus ne doit pas casser leur lecture.
        _, d = self.run_collect()
        self.assertEqual(d["totals"]["sessions"], 2)
        self.assertEqual(d["machines"][0]["name"], "Tour")

    def test_real_names_only_on_explicit_request(self):
        raw, d = self.run_collect(["--keep-project-names"])
        self.assertIn("client", raw)
        self.assertFalse(d["anonymized"])
        self.assertNotIn("secret de fabrication", raw)   # le contenu ne sort jamais


if __name__ == "__main__":
    unittest.main()
