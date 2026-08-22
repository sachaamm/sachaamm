# Profile stats — how it works

The stat cards in the README are **generated from the GitHub API across all my
repositories, private ones included**, and refreshed weekly by GitHub Actions.

Third-party README widgets can only see public repositories. Mine cover 229 repos,
of which 171 are private — a very different picture.

## Pipeline

```
scripts/collect.py        GitHub API  →  data/github-profile.json  (anonymised, gitignored)
scripts/collect_claude.py ~/.claude   →  data/claude-code.json     (anonymised, COMMITTED)
scripts/render_cards.py   both JSONs  →  assets/*.svg              (12 files: 6 cards × light/dark)
.github/workflows/update-stats.yml    runs collect.py + render, weekly, and commits the SVGs
```

None of the three scripts has an external dependency — plain Python 3.8+ and `urllib`.

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

## Claude Code snapshot

The *Claude Code usage* card is the one card Actions cannot refresh. Claude Code
keeps no central record: sessions, prompts and subagent metadata live in
`~/.claude` on whichever machine you typed on. A CI runner has none of it.

So `data/claude-code.json` is **committed**, unlike `data/github-profile.json`
which is regenerated on every run — that is why `.gitignore` uses `data/*` plus
an explicit exception rather than `data/`.

### Several workstations

The snapshot holds one entry per machine and the sum on top. Run the collector
on each machine, against the same file — it replaces the entry with that name
and recomputes the totals, so re-running is idempotent and never double-counts:

```bash
# on the desktop
python3 scripts/collect_claude.py --machine "Tour" --out data/claude-code.json
# on the laptop, after pulling
python3 scripts/collect_claude.py --machine "MacBook Air" --out data/claude-code.json
python3 scripts/render_cards.py
git add data/claude-code.json assets/claude-*.svg
```

For a machine where the repository is not checked out, run the one-line reader
there and transcribe the figures instead:

```bash
python3 scripts/collect_claude.py --add-machine "Tour" \
  --sessions 1546 --transcripts 151 --agents 19 --prompts 6249 --projects 101 \
  --months "2025-10:30,2025-11:22" --out data/claude-code.json
```

Such an entry is marked `"source": "reported"`. It carries no per-model
breakdown — the short reader does not produce one — so the aggregate leaves it
out of that sum rather than counting it as zero, and records in
`model_split_machines` how many machines the model bar actually covers.

The two sets never collide: session ids are UUIDs generated per machine.

Three consequences worth stating on the card itself, and the card does state them:

- **Per machine.** Nothing is collected remotely; each workstation is read
  where it sits, then merged into the same file.
- **A floor, not a total.** `history.jsonl` only reaches back as far as the local
  file does — sessions older than that are gone.
- **Sessions ≠ transcripts.** Sessions are counted from each machine's prompt
  history; transcripts still on disk are far fewer, because Claude Code prunes.
  The card prints both instead of picking the flattering one.

What the collector reads: counters, timestamps, and each subagent's
`.meta.json` (type, model, depth). What it never reads: the text of prompts or
of agent transcripts. Project paths are replaced by `project-01`, `project-02`,
… before anything is written — they carry client names. `--keep-project-names`
disables that, and is not what you want for a public profile.

If `data/claude-code.json` is absent, `render_cards.py` simply drops the card
and renders the other five. A checkout that never ran the collector still works.

## Privacy

Repository names follow a **whitelist**. A repo keeps its real name only if a card
actually shows it — the top 10 by commits, which is exactly how the *Top repositories*
table sorts. Naming a repo nobody will see would expose a name for nothing. Everything
else is anonymised before a single byte reaches the disk:

- names become `private-001`, `private-002`, …
- descriptions, homepages and topics are dropped entirely
- what remains is counts, languages and library names

Public repos always keep their name; they are already visible to everyone. Collection
progress printed to the console stays masked either way, because Actions logs on a
public repository are readable by anyone.

Two levers, both in `update-stats.yml`:

- `--name-top N` — how many repos keep their real name, matching the rows the card
  displays (default 10)
- `--never-name a,b` — repos that stay anonymous whatever their rank

The workflow runs a **safety check** between collection and rendering. It aborts if the
naming mode is not `whitelist`, if any private repo outside the whitelist still carries
a real name, or if the whitelist grows far beyond what the cards display. The raw JSON
is gitignored anyway — only the SVGs are committed.

## How lines of code are counted

The GitHub API returns **bytes per language**, not line counts. Fetching every file to
count lines would mean hundreds of thousands of extra requests, so lines are estimated:

```
lines ≈ bytes / average_bytes_per_line[language]
```

The per-language divisors live in `BYTES_PER_LINE` in `statslib.py` (C# 31, TypeScript
29, HTML 38, and so on).

**Third-party and generated code is excluded by path, not by language.** `collect.py`
already downloads the full file tree of every repo, so each file's path and size are
free. `is_vendored()` in `statslib.py` drops anything under a dependency, build or
Asset Store directory: `node_modules/`, `vendor/`, `Library/`, `dist/`, plus the
directories written by Unity shader generators — `MicroSplat*`, `AmplifyShaderEditor/`,
`Visual Design Cafe/` — and files carrying Amplify's `ASE_` prefix.

Why by path: the earlier rule excluded the *languages* `ShaderLab`, `GLSL` and `HLSL`
outright, which was wrong in both directions. It counted the 43 MB of ShaderLab in
`rastignac-vendor-versionned`, a vendored repo, as nothing special, while discarding
hand-written shader work elsewhere. And it implied that the Unity repositories were
shader dumps: `generativeroads` is 11.3 MB of C# against 0.4 MB of shaders — its code
was never excluded at all.

In `st-game-final`, path exclusion catches 20.3 of 21.8 MB of shaders, and every
excluded file sits under a `MicroSplatData/` or `AmplifyShaderEditor/` directory or
carries the `ASE_` prefix. Those are generated by Asset Store tools, not typed by hand.

**Some repositories are third-party end to end**, and no path rule can save them:
their folders carry Asset Store publisher names — `NatureManufacture Assets`,
`Hovl Studio`, `KriptoFX` — a list with no end. `rastignac-vendor-versionned` holds
44.8 MB of source across 348 files for 22 commits: about 78,000 lines per commit, which
nobody writes. Those repos are listed in `VENDORED_REPOS` and excluded whole, or passed
at run time with `--vendored-repos a,b`.

The excluded volume is reported as `loc_vendored` and never silently dropped. It is
larger than the counted volume: 4.85M excluded against 2.99M written.

To count everything instead, empty `VENDORED_DIRS`, `VENDORED_DIR_PREFIXES` and
`VENDORED_FILE_PREFIXES` in `statslib.py`.

## Lines added and deleted

The *Top repositories* card shows real additions and deletions from
`/repos/{owner}/{repo}/stats/contributors`, filtered to your own commits. One API call
per repository, no cloning.

Read them as **churn, not authorship**: they cover every file in every commit, asset
imports included. A Unity repo showing +54M lines across 487 commits is importing
packages, not typing 111,000 lines per commit. The card says so in its footer.

That endpoint answers `202` and computes in the background on first call — measured up
to 45 s on the largest repos. `collect.py` therefore makes two passes: one to trigger
the computation, one to collect it, then retries what is still pending. A repository
whose stats never arrive shows `—`, never `0`.

## Tests

`python3 -m unittest discover -s tests` — no dependencies, no network. Covers path
exclusion, line estimation, the naming whitelist, churn aggregation, the rendering
of the *Top repositories* and *Claude Code usage* cards, and the anonymisation of the
Claude Code collector. CI runs them before rendering.

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
