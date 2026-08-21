"""Tests des fonctions pures de statslib (aucun appel réseau)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from statslib import (is_vendored, lang_of_path, est_lines, loc_from_tree,
                      repos_to_name, author_churn, apply_naming)


class TestIsVendored(unittest.TestCase):
    def test_microsplat_generated_shader_is_vendored(self):
        self.assertTrue(is_vendored("Assets/MicroSplatData/MicroSplat.shader"))

    def test_amplify_shader_editor_plugin_is_vendored(self):
        self.assertTrue(is_vendored("Assets/AmplifyShaderEditor/Plugins/Editor.cs"))

    def test_hand_written_gameplay_script_is_not_vendored(self):
        self.assertFalse(is_vendored("Assets/Scripts/PlayerController.cs"))

    def test_node_modules_is_vendored(self):
        self.assertTrue(is_vendored("node_modules/lodash/index.js"))

    def test_unity_library_folder_is_vendored(self):
        self.assertTrue(is_vendored("Library/ScriptAssemblies/Assembly-CSharp.dll"))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(is_vendored("assets/microsplatdata/terrain.shader"))

    def test_segment_must_match_whole_directory_not_substring(self):
        # 'vendor' est un dossier tiers, 'vendorize.js' est du code écrit à la main
        self.assertFalse(is_vendored("src/vendorize.js"))
        self.assertTrue(is_vendored("src/vendor/jquery.js"))


class TestLangOfPath(unittest.TestCase):
    def test_cs_extension_maps_to_csharp(self):
        self.assertEqual(lang_of_path("Assets/Scripts/Player.cs"), "C#")

    def test_glsl_extension_is_recognised(self):
        self.assertEqual(lang_of_path("shaders/water.glsl"), "GLSL")

    def test_unknown_extension_returns_none(self):
        self.assertIsNone(lang_of_path("Assets/art/texture.png"))

    def test_file_without_extension_returns_none(self):
        self.assertIsNone(lang_of_path("LICENSE"))


class TestEstLines(unittest.TestCase):
    def test_csharp_uses_its_own_divisor(self):
        self.assertAlmostEqual(est_lines(3100, "C#"), 100.0)

    def test_unknown_language_falls_back_to_default_divisor(self):
        self.assertAlmostEqual(est_lines(3000, "Brainfuck"), 100.0)


class TestLocFromTree(unittest.TestCase):
    def test_splits_written_from_vendored_by_path(self):
        blobs = [
            {"path": "Assets/Scripts/Player.cs", "size": 3100},
            {"path": "Assets/MicroSplatData/MicroSplat.shader", "size": 2600},
        ]
        res = loc_from_tree(blobs)
        self.assertAlmostEqual(res["written"]["C#"], 100.0)
        self.assertAlmostEqual(res["vendored"]["ShaderLab"], 100.0)
        self.assertNotIn("ShaderLab", res["written"])

    def test_ignores_blobs_with_unknown_extension(self):
        res = loc_from_tree([{"path": "art/logo.png", "size": 999999}])
        self.assertEqual(res["written"], {})
        self.assertEqual(res["vendored"], {})

    def test_missing_size_is_treated_as_zero(self):
        res = loc_from_tree([{"path": "src/a.cs"}])
        self.assertEqual(res["written"], {})


class TestReposToName(unittest.TestCase):
    def setUp(self):
        self.repos = [
            {"id": "me/alpha",   "my_commits": 500, "churn": 10},
            {"id": "me/beta",    "my_commits": 400, "churn": 20},
            {"id": "me/gamma",   "my_commits": 300, "churn": 90},
            {"id": "me/delta",   "my_commits": 5,   "churn": 1},
        ]

    def test_keeps_top_n_by_commits(self):
        named = repos_to_name(self.repos, top_n=2)
        self.assertIn("me/alpha", named)
        self.assertIn("me/beta", named)

    def test_also_keeps_top_n_by_churn(self):
        # gamma est 3e en commits mais 1er en churn : il apparaîtra sur la carte
        named = repos_to_name(self.repos, top_n=2)
        self.assertIn("me/gamma", named)

    def test_leaves_everything_else_anonymous(self):
        named = repos_to_name(self.repos, top_n=2)
        self.assertNotIn("me/delta", named)

    def test_blocklist_wins_over_ranking(self):
        named = repos_to_name(self.repos, top_n=2, never_name={"me/alpha"})
        self.assertNotIn("me/alpha", named)


class TestAuthorChurn(unittest.TestCase):
    def test_sums_only_the_requested_author(self):
        stats = [
            {"author": {"login": "someone-else"}, "total": 9,
             "weeks": [{"a": 999, "d": 999}]},
            {"author": {"login": "sachaamm"}, "total": 3,
             "weeks": [{"a": 10, "d": 4}, {"a": 5, "d": 1}]},
        ]
        self.assertEqual(author_churn(stats, "sachaamm"),
                         {"commits": 3, "additions": 15, "deletions": 5})

    def test_author_absent_returns_none(self):
        self.assertIsNone(author_churn([], "sachaamm"))

    def test_pending_202_response_returns_none(self):
        # l'API répond {} tant qu'elle calcule les statistiques
        self.assertIsNone(author_churn({}, "sachaamm"))

    def test_login_match_is_case_insensitive(self):
        stats = [{"author": {"login": "SachaAmm"}, "total": 1,
                  "weeks": [{"a": 2, "d": 1}]}]
        self.assertIsNotNone(author_churn(stats, "sachaamm"))


class TestApplyNaming(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"id": "me/public-tool",  "private": False},
            {"id": "me/kept-private", "private": True},
            {"id": "me/secret-client", "private": True},
            {"id": "me/other-secret",  "private": True},
        ]

    def test_public_repos_always_keep_their_real_name(self):
        apply_naming(self.entries, named={})
        self.assertEqual(self.entries[0]["id"], "me/public-tool")

    def test_whitelisted_private_repo_keeps_its_real_name(self):
        apply_naming(self.entries, named={"me/kept-private"})
        self.assertEqual(self.entries[1]["id"], "me/kept-private")

    def test_private_repo_outside_whitelist_is_anonymised(self):
        apply_naming(self.entries, named={"me/kept-private"})
        self.assertEqual(self.entries[2]["id"], "private-001")
        self.assertEqual(self.entries[3]["id"], "private-002")

    def test_anonymised_entry_keeps_no_trace_of_the_real_name(self):
        self.entries[2]["description"] = "Prospection comptables Signarafast"
        self.entries[2]["homepage"] = "https://signarafast.example"
        apply_naming(self.entries, named=set())
        blob = repr(self.entries[2])
        self.assertNotIn("signarafast", blob.lower())
        self.assertNotIn("secret-client", blob)

    def test_reports_which_names_were_published(self):
        published = apply_naming(self.entries, named={"me/kept-private"})
        self.assertEqual(published, ["me/kept-private", "me/public-tool"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
