#!/usr/bin/env python3
"""
github_profile_export.py
------------------------
Extrait un profil technique complet depuis l'API GitHub (repos publics ET prives)
et produit un JSON ANONYMISE, pret a etre partage.

Le token ne quitte JAMAIS ta machine : le script tourne en local.

Usage:
    export GITHUB_TOKEN=ghp_xxxxx
    python3 github_profile_export.py

Options:
    --keep-private-names   garde les vrais noms des repos prives (par defaut ils
                           sont remplaces par private-001, private-002, ...)
    --max-commit-pages N   nb max de pages de commits par repo (defaut 12 = 1200)
    --out FICHIER          chemin de sortie (defaut github-profile.json)

Aucune dependance externe. Python 3.8+.
"""

import os, sys, json, time, base64, argparse, hashlib
from collections import defaultdict
import urllib.request, urllib.error, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from statslib import (loc_from_tree, est_lines, repos_to_name,
                      apply_naming, author_churn)

API = "https://api.github.com"

# ----------------------------------------------------------------------------
# Fichiers marqueurs : leur presence revele le stack reel
# ----------------------------------------------------------------------------
MARKERS = {
    # JS / TS
    "package.json": "Node/JS project",
    "angular.json": "Angular",
    ".angular-cli.json": "Angular (legacy CLI)",
    "next.config.js": "Next.js", "next.config.mjs": "Next.js", "next.config.ts": "Next.js",
    "nuxt.config.ts": "Nuxt", "nuxt.config.js": "Nuxt",
    "vite.config.ts": "Vite", "vite.config.js": "Vite",
    "webpack.config.js": "Webpack",
    "nx.json": "Nx monorepo",
    "turbo.json": "Turborepo",
    "lerna.json": "Lerna",
    "tsconfig.json": "TypeScript",
    "tailwind.config.js": "Tailwind CSS", "tailwind.config.ts": "Tailwind CSS",
    "svelte.config.js": "Svelte",
    "astro.config.mjs": "Astro",
    "remix.config.js": "Remix",
    "metro.config.js": "React Native",
    "app.json": "React Native/Expo",
    "capacitor.config.ts": "Capacitor", "capacitor.config.json": "Capacitor",
    "ionic.config.json": "Ionic",
    "pnpm-lock.yaml": "pnpm", "yarn.lock": "Yarn", "package-lock.json": "npm",
    "bun.lockb": "Bun",
    "deno.json": "Deno",
    "jest.config.js": "Jest", "vitest.config.ts": "Vitest",
    "playwright.config.ts": "Playwright",
    "cypress.config.ts": "Cypress", "cypress.json": "Cypress",
    "karma.conf.js": "Karma",
    # .NET
    "global.json": ".NET SDK",
    "nuget.config": "NuGet", "NuGet.config": "NuGet",
    "Directory.Build.props": ".NET (MSBuild)",
    # Python
    "requirements.txt": "Python", "pyproject.toml": "Python (modern)",
    "Pipfile": "Pipenv", "poetry.lock": "Poetry", "setup.py": "Python package",
    "manage.py": "Django",
    # PHP
    "composer.json": "PHP/Composer", "artisan": "Laravel",
    "symfony.lock": "Symfony",
    # Autres langages
    "go.mod": "Go", "Cargo.toml": "Rust", "Gemfile": "Ruby",
    "pom.xml": "Java/Maven", "build.gradle": "Java/Gradle",
    "build.gradle.kts": "Kotlin/Gradle",
    "pubspec.yaml": "Flutter/Dart",
    "Package.swift": "Swift",
    # Infra / CI / Ops
    "Dockerfile": "Docker", "dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose", "docker-compose.yaml": "Docker Compose",
    "Makefile": "Make",
    "vercel.json": "Vercel", "netlify.toml": "Netlify",
    "railway.json": "Railway", "railway.toml": "Railway",
    "fly.toml": "Fly.io", "render.yaml": "Render",
    "Procfile": "Heroku",
    "serverless.yml": "Serverless Framework",
    "terraform.tf": "Terraform", "main.tf": "Terraform",
    "Chart.yaml": "Helm",
    "skaffold.yaml": "Kubernetes/Skaffold",
    ".gitlab-ci.yml": "GitLab CI",
    "azure-pipelines.yml": "Azure DevOps",
    "Jenkinsfile": "Jenkins",
    "sonar-project.properties": "SonarQube",
    # Data / BaaS
    "supabase/config.toml": "Supabase",
    "firebase.json": "Firebase",
    "prisma/schema.prisma": "Prisma",
    "schema.prisma": "Prisma",
    "knexfile.js": "Knex",
    # IA / agents
    "CLAUDE.md": "Claude Code",
    ".cursorrules": "Cursor",
    ".windsurfrules": "Windsurf",
    "AGENTS.md": "Agents (Codex/OpenAI)",
    ".mcp.json": "MCP servers",
    "mcp.json": "MCP servers",
}

EXT_LANG = {
    ".cs": "C#", ".csproj": "C# project", ".sln": ".NET solution",
    ".ts": "TypeScript", ".tsx": "TypeScript/React", ".js": "JavaScript",
    ".jsx": "JavaScript/React", ".vue": "Vue", ".svelte": "Svelte",
    ".py": "Python", ".php": "PHP", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".swift": "Swift",
    ".dart": "Dart", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
    ".scss": "SCSS", ".css": "CSS", ".html": "HTML", ".razor": "Blazor",
    ".cshtml": "ASP.NET Razor", ".vb": "VB.NET", ".ipynb": "Jupyter",
}

# Manifestes dont on lit le CONTENU pour extraire les dependances
READ_CONTENT = {"package.json", "composer.json", "requirements.txt",
                "pyproject.toml", "go.mod"}


# ----------------------------------------------------------------------------
class GH:
    def __init__(self, token):
        self.token = token
        self.calls = 0

    def _req(self, url):
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + self.token)
        r.add_header("Accept", "application/vnd.github+json")
        r.add_header("X-GitHub-Api-Version", "2022-11-28")
        r.add_header("User-Agent", "profile-export")
        return r

    def get(self, path, params=None, raw=False):
        url = path if path.startswith("http") else API + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        for attempt in range(4):
            self.calls += 1
            try:
                with urllib.request.urlopen(self._req(url), timeout=45) as resp:
                    body = resp.read()
                    hdrs = dict(resp.headers)
                    rem = hdrs.get("X-RateLimit-Remaining")
                    if rem is not None and int(rem) < 40:
                        reset = int(hdrs.get("X-RateLimit-Reset", 0))
                        wait = max(0, reset - int(time.time())) + 5
                        print("\n  [rate limit] pause %ds..." % wait, flush=True)
                        time.sleep(wait)
                    return (body if raw else json.loads(body or b"null")), hdrs
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    reset = e.headers.get("X-RateLimit-Reset")
                    if reset:
                        wait = max(0, int(reset) - int(time.time())) + 5
                        print("\n  [rate limit] pause %ds..." % wait, flush=True)
                        time.sleep(wait); continue
                    time.sleep(10); continue
                if e.code in (404, 409, 451):
                    return None, {}
                if e.code >= 500:
                    time.sleep(3 * (attempt + 1)); continue
                return None, {}
            except Exception:
                time.sleep(3 * (attempt + 1))
        return None, {}

    def paginate(self, path, params=None, cap=100):
        params = dict(params or {}); params["per_page"] = 100
        page, out = 1, []
        while page <= cap:
            params["page"] = page
            data, _ = self.get(path, params)
            if not data:
                break
            out.extend(data)
            if len(data) < 100:
                break
            page += 1
        return out

    def count_via_link(self, path, params=None):
        """Compte total d'items sans tout telecharger (astuce header Link)."""
        p = dict(params or {}); p["per_page"] = 1
        data, hdrs = self.get(path, p)
        if data is None:
            return 0
        link = hdrs.get("Link") or hdrs.get("link") or ""
        if 'rel="last"' in link:
            for part in link.split(","):
                if 'rel="last"' in part:
                    u = part.split(";")[0].strip().strip("<>")
                    q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
                    return int(q.get("page", [1])[0])
        return len(data) if isinstance(data, list) else 0


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-private-names", action="store_true",
                    help="publie TOUS les vrais noms, y compris prives (deconseille)")
    ap.add_argument("--name-top", type=int, default=10,
                    help="nb de repos en tete de classement qui gardent leur vrai nom")
    ap.add_argument("--never-name", default="",
                    help="repos qui restent anonymes quoi qu'il arrive (separes par des virgules)")
    ap.add_argument("--max-commit-pages", type=int, default=12)
    ap.add_argument("--out", default="github-profile.json")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("ERREUR : export GITHUB_TOKEN=ghp_xxx  puis relance.")

    gh = GH(token)
    me, _ = gh.get("/user")
    if not me:
        sys.exit("ERREUR : token invalide ou sans acces. Verifie les scopes repo + read:org + read:user.")
    login = me["login"]
    print("Connecte en tant que : %s (%s)" % (login, me.get("name") or "?"))
    print("Compte cree le       : %s" % me.get("created_at", "")[:10])

    print("\nRecuperation de la liste des repos (publics + prives)...")
    repos = gh.paginate("/user/repos",
                        {"visibility": "all",
                         "affiliation": "owner,collaborator,organization_member",
                         "sort": "pushed"})
    print("  -> %d repos accessibles" % len(repos))

    orgs = gh.paginate("/user/orgs")
    print("  -> %d organisations" % len(orgs))

    out_repos = []
    monthly = defaultdict(int)
    dep_counter = defaultdict(int)
    marker_counter = defaultdict(int)
    ext_counter = defaultdict(int)
    ci_counter = defaultdict(int)
    priv_i = 0

    total = len(repos)
    for i, r in enumerate(repos, 1):
        full = r["full_name"]
        owner, name = full.split("/", 1)
        is_priv = r.get("private", False)
        if is_priv:
            priv_i += 1

        # Le vrai nom est conservé dans l'entrée : l'anonymisation est appliquée
        # à la fin, une fois le classement connu (voir apply_naming plus bas).
        # L'affichage, lui, reste masqué : les logs Actions d'un repo public
        # sont lisibles par tout le monde.
        shown = full if not is_priv else "private repo #%d" % priv_i
        sys.stdout.write("\r[%3d/%3d] %-52s" % (i, total, shown[:52]))
        sys.stdout.flush()

        entry = {
            "id": full,
            "private": is_priv,
            "fork": r.get("fork", False),
            "archived": r.get("archived", False),
            "owner_is_org": r.get("owner", {}).get("type") == "Organization",
            "is_mine": owner.lower() == login.lower(),
            "created_at": r.get("created_at"),
            "pushed_at": r.get("pushed_at"),
            "size_kb": r.get("size", 0),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "primary_language": r.get("language"),
            "license": (r.get("license") or {}).get("spdx_id"),
            "topics": r.get("topics", []) if not is_priv else [],
            "has_wiki": r.get("has_wiki"),
            "default_branch": r.get("default_branch"),
        }
        if not is_priv:
            entry["description"] = r.get("description")
            entry["homepage"] = r.get("homepage")

        # --- langages en octets -------------------------------------------
        langs, _ = gh.get("/repos/%s/languages" % full)
        entry["languages"] = langs or {}

        # --- commits de l'utilisateur -------------------------------------
        cpath = "/repos/%s/commits" % full
        entry["my_commits"] = gh.count_via_link(cpath, {"author": login})

        dates = []
        page = 1
        while page <= args.max_commit_pages:
            data, _ = gh.get(cpath, {"author": login, "per_page": 100, "page": page})
            if not data:
                break
            for c in data:
                d = (((c.get("commit") or {}).get("author") or {}).get("date") or "")[:7]
                if d:
                    dates.append(d)
            if len(data) < 100:
                break
            page += 1
        for d in dates:
            monthly[d] += 1
        entry["commit_months_sampled"] = len(dates)
        if dates:
            entry["first_commit"] = min(dates)
            entry["last_commit"] = max(dates)

        # --- arborescence complete (1 seul appel) --------------------------
        branch = r.get("default_branch") or "main"
        tree, _ = gh.get("/repos/%s/git/trees/%s" % (full, branch), {"recursive": "1"})
        paths = []
        if tree and isinstance(tree, dict):
            blobs = [t for t in tree.get("tree", []) if t.get("type") == "blob"]
            paths = [t["path"] for t in blobs]
            entry["file_count"] = len(paths)
            entry["tree_truncated"] = tree.get("truncated", False)
            # Lignes estimees, separees selon que le chemin est du code ecrit
            # ou du code tiers/genere. Aucun appel API en plus : l'arbre est
            # deja telecharge ci-dessus.
            if entry["tree_truncated"]:
                # Arbre tronque par GitHub (>100k entrees) : on retombe sur les
                # octets par langage, sans pouvoir distinguer le code tiers.
                entry["loc"] = {"written": {k: est_lines(v, k)
                                            for k, v in (entry.get("languages") or {}).items()},
                                "vendored": {}}
                entry["loc_source"] = "languages (arbre tronque)"
            else:
                entry["loc"] = loc_from_tree(blobs)
                entry["loc_source"] = "tree"

        found_markers, workflows = set(), []
        for p in paths:
            base = p.split("/")[-1]
            if base in MARKERS and ("/" not in p or p.count("/") <= 2):
                found_markers.add(MARKERS[base])
            if p in MARKERS:
                found_markers.add(MARKERS[p])
            if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")):
                workflows.append(base)
            dot = p.rfind(".")
            if dot > 0:
                ext = p[dot:].lower()
                if ext in EXT_LANG and "node_modules/" not in p and "/bin/" not in p:
                    ext_counter[EXT_LANG[ext]] += 1
        if workflows:
            found_markers.add("GitHub Actions")
            for w in workflows:
                ci_counter[w] += 1
        entry["markers"] = sorted(found_markers)
        for m in found_markers:
            marker_counter[m] += 1

        # --- dependances declarees ----------------------------------------
        deps = set()
        for mf in READ_CONTENT:
            if mf not in paths:
                continue
            blob, _ = gh.get("/repos/%s/contents/%s" % (full, mf), {"ref": branch})
            if not blob or "content" not in blob:
                continue
            try:
                txt = base64.b64decode(blob["content"]).decode("utf-8", "replace")
            except Exception:
                continue
            if mf == "package.json":
                try:
                    pj = json.loads(txt)
                    for k in ("dependencies", "devDependencies", "peerDependencies"):
                        deps.update((pj.get(k) or {}).keys())
                except Exception:
                    pass
            elif mf == "composer.json":
                try:
                    cj = json.loads(txt)
                    for k in ("require", "require-dev"):
                        deps.update((cj.get(k) or {}).keys())
                except Exception:
                    pass
            elif mf == "requirements.txt":
                for line in txt.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        deps.add(line.split("==")[0].split(">=")[0].split("[")[0].strip())
            elif mf == "go.mod":
                for line in txt.splitlines():
                    line = line.strip()
                    if line.startswith(("github.com/", "golang.org/", "google.golang.org/")):
                        deps.add(line.split()[0])
            elif mf == "pyproject.toml":
                for line in txt.splitlines():
                    ls = line.strip().strip('",')
                    if ls and not ls.startswith(("#", "[")) and "=" not in ls and len(ls) < 60:
                        deps.add(ls.split("==")[0].split(">=")[0].strip())
        deps = {d for d in deps if d and len(d) < 80}
        entry["dependencies"] = sorted(deps)
        for d in deps:
            dep_counter[d] += 1

        out_repos.append(entry)

    # ------------------------------------------------------------------
    # Churn : lignes ajoutees / supprimees, par toi seul.
    # /stats/contributors repond 202 et calcule en tache de fond la premiere
    # fois. D'ou deux passes : la premiere declenche les calculs, la seconde
    # les recolte une fois chauds.
    # ------------------------------------------------------------------
    print("\n\nChurn (lignes ajoutees/supprimees)...")
    by_id = {e["id"]: e for e in out_repos}
    paths_stats = {rid: "/repos/%s/stats/contributors" % rid for rid in by_id}
    for path in paths_stats.values():
        gh.get(path)                       # passe 1 : reveille le calcul

    pending = dict(paths_stats)
    for attempt in range(4):
        if not pending:
            break
        if attempt:
            time.sleep(15)                 # laisse GitHub finir de calculer
        still = {}
        for rid, path in pending.items():
            stats, _ = gh.get(path)
            churn = author_churn(stats, login)
            if churn is None:
                still[rid] = path
            else:
                by_id[rid]["churn_additions"] = churn["additions"]
                by_id[rid]["churn_deletions"] = churn["deletions"]
                by_id[rid]["churn"] = churn["additions"] + churn["deletions"]
        pending = still
        print("  passe %d : %d repos restants" % (attempt + 1, len(pending)))
    if pending:
        print("  %d repos sans statistiques (API toujours en calcul) : churn absent"
              % len(pending))

    # ------------------------------------------------------------------
    # Nommage : seuls les repos susceptibles d'apparaitre sur une carte
    # gardent leur vrai nom. Tous les autres sont anonymises ici, avant
    # meme d'etre ecrits sur le disque.
    # ------------------------------------------------------------------
    never = {x.strip() for x in args.never_name.split(",") if x.strip()}
    if args.keep_private_names:
        named = {e["id"] for e in out_repos} - never
    else:
        named = repos_to_name(out_repos, top_n=args.name_top, never_name=never)
    published = apply_naming(out_repos, named)
    hidden = len(out_repos) - len(published)
    print("\nNommage : %d noms reels publies, %d repos anonymises." % (len(published), hidden))

    print("\nAgregation...")

    lang_totals = defaultdict(int)
    for e in out_repos:
        for k, v in (e.get("languages") or {}).items():
            lang_totals[k] += v

    loc_written, loc_vendored = defaultdict(float), defaultdict(float)
    for e in out_repos:
        for k, v in (e.get("loc", {}).get("written") or {}).items():
            loc_written[k] += v
        for k, v in (e.get("loc", {}).get("vendored") or {}).items():
            loc_vendored[k] += v

    result = {
        "schema": "github-profile/1.2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "anonymized": hidden > 0,
        "naming_mode": "all" if args.keep_private_names else "whitelist",
        "name_top": args.name_top,
        "named_repos": published,
        "account": {
            "login": login,
            "name": me.get("name"),
            "company": me.get("company"),
            "location": me.get("location"),
            "bio": me.get("bio"),
            "blog": me.get("blog"),
            "created_at": me.get("created_at"),
            "public_repos": me.get("public_repos"),
            "followers": me.get("followers"),
            "years_on_github": round(
                (time.time() - time.mktime(time.strptime(
                    me.get("created_at", "2015-01-01T00:00:00Z"),
                    "%Y-%m-%dT%H:%M:%SZ"))) / 31557600, 1),
        },
        "orgs_count": len(orgs),
        "totals": {
            "repos": len(out_repos),
            "private": sum(1 for e in out_repos if e["private"]),
            "public": sum(1 for e in out_repos if not e["private"]),
            "forks": sum(1 for e in out_repos if e["fork"]),
            "archived": sum(1 for e in out_repos if e["archived"]),
            "owned": sum(1 for e in out_repos if e["is_mine"]),
            "in_orgs": sum(1 for e in out_repos if e["owner_is_org"]),
            "my_commits": sum(e.get("my_commits", 0) for e in out_repos),
            "stars_received": sum(e.get("stars", 0) for e in out_repos),
            "files_indexed": sum(e.get("file_count", 0) for e in out_repos),
            "loc_written": round(sum(loc_written.values())),
            "loc_vendored": round(sum(loc_vendored.values())),
            "churn_additions": sum(e.get("churn_additions", 0) for e in out_repos),
            "churn_deletions": sum(e.get("churn_deletions", 0) for e in out_repos),
            "api_calls": gh.calls,
        },
        "loc_by_language": dict(sorted(((k, round(v)) for k, v in loc_written.items()),
                                       key=lambda x: -x[1])),
        "loc_vendored_by_language": dict(sorted(((k, round(v)) for k, v in loc_vendored.items()),
                                                key=lambda x: -x[1])),
        "language_bytes": dict(sorted(lang_totals.items(), key=lambda x: -x[1])),
        "file_extensions": dict(sorted(ext_counter.items(), key=lambda x: -x[1])),
        "stack_markers": dict(sorted(marker_counter.items(), key=lambda x: -x[1])),
        "ci_workflows": dict(sorted(ci_counter.items(), key=lambda x: -x[1])[:60]),
        "top_dependencies": dict(sorted(dep_counter.items(), key=lambda x: -x[1])[:400]),
        "commits_by_month": dict(sorted(monthly.items())),
        "repos": out_repos,
    }

    outdir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(outdir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    t = result["totals"]
    print("=" * 62)
    print("  Fichier ecrit : %s" % args.out)
    print("  Repos         : %d  (%d publics / %d prives)" % (t["repos"], t["public"], t["private"]))
    print("  Commits (toi) : %d" % t["my_commits"])
    print("  Fichiers vus  : %d" % t["files_indexed"])
    print("  Langages      : %s" % ", ".join(list(result["language_bytes"])[:8]))
    print("  Appels API    : %d" % t["api_calls"])
    print("  Anonymise     : %s" % ("OUI" if result["anonymized"] else "NON"))
    print("=" * 62)


if __name__ == "__main__":
    main()
