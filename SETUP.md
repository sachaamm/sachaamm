# Profile stats — how it works

The stat cards in the README are **generated from the GitHub API across all my
repositories, private ones included**, and refreshed weekly by GitHub Actions.

Third-party README widgets can only see public repositories. Mine cover 229 repos,
of which 171 are private — a very different picture.

## Pipeline

```
scripts/collect.py       GitHub API  →  data/github-profile.json   (anonymised)
scripts/render_cards.py  that JSON   →  assets/*.svg               (8 files: 4 cards × light/dark)
.github/workflows/update-stats.yml   runs both, weekly, and commits the SVGs
```

Neither script has external dependencies — plain Python 3.8+ and `urllib`.

## One-time setup

**1. Create a Personal Access Token**

Go to <https://github.com/settings/tokens> → *Generate new token (classic)*.

Scopes: `repo`, `read:org`, `read:user`. Set a long expiry — you will get an email
before it lapses.

**2. Store it as a repository secret**

Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*.

- Name: `STATS_TOKEN`
- Value: the token

> It **must not** be called `GITHUB_TOKEN` — that name is reserved by Actions, and the
> token Actions injects automatically only has access to this one repository, which is
> not enough to enumerate the others.

**3. Allow the workflow to push**

Repo → *Settings* → *Actions* → *General* → *Workflow permissions* →
**Read and write permissions**.

**4. Trigger the first run**

*Actions* tab → *Update profile stats* → *Run workflow*. Takes 5–10 minutes
(roughly 1,000 API calls, with automatic rate-limit backoff).

## Running it locally

```bash
export GITHUB_TOKEN=ghp_xxx
python3 scripts/collect.py --out data/github-profile.json
python3 scripts/render_cards.py
```

## Privacy

Private repositories are anonymised **at source**, before anything is written to disk:

- names become `private-001`, `private-002`, …
- descriptions, homepages and topics are dropped entirely
- what remains is counts, languages and library names

The workflow runs a **safety check** between collection and rendering that aborts the
whole run if anonymisation is off or if any real private repo name is present. The raw
JSON is gitignored anyway — only the SVGs are committed.

## How lines of code are counted

The GitHub API returns **bytes per language**, not line counts. Fetching every file to
count lines would mean hundreds of thousands of extra requests, so lines are estimated:

```
lines ≈ bytes / average_bytes_per_line[language]
```

The per-language divisors live in `BYTES_PER_LINE` in `render_cards.py` (C# 31, TypeScript
29, HTML 38, and so on).

**Generated shader code is excluded.** `ShaderLab`, `GLSL` and `HLSL` are listed in
`GENERATED_LANGS` and left out of the line count. The reason is concrete: two Unity
repositories hold 65 MB of shader source between them — one of them 43 MB across 22,614
files for just 22 commits. That is Shader Graph output and imported Asset Store content,
not hand-written code. Including it would inflate the total from 3.0M to 5.7M lines and
make the whole figure worthless.

The excluded volume is still reported, in the footer of the *Top repositories* card, so
nothing is hidden.

To count everything instead, empty the `GENERATED_LANGS` set.

## Customising

- **Cadence** — the `cron` line in `update-stats.yml` (currently Mondays 04:17 UTC).
- **Which frameworks appear** — `FW_KEEP` in `render_cards.py`.
- **Colours** — the `THEMES` dict in `render_cards.py`. The palette is
  colourblind-safe: the three domain hues clear a ΔE ≥ 8 separation under deuteranopia
  and tritanopia simulation, in both light and dark.
- **Adding a card** — write a `card_yourname(th)` returning `(width, height, svg_body)`
  and add it to the `CARDS` dict. Both themes are rendered automatically.

## Note on GitHub's image cache

GitHub proxies README images through Camo and caches them. After a refresh the new
cards normally appear within minutes; a hard reload (Cmd+Shift+R) clears a stale one.
