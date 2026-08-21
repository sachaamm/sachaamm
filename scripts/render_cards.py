#!/usr/bin/env python3
"""
render_cards.py — transforme data/github-profile.json en cartes SVG statiques
pour un README de profil GitHub (une version claire + une version sombre).

    python3 scripts/render_cards.py

Aucune dépendance externe. Les SVG produits ne contiennent ni script, ni police
externe, ni animation : GitHub les affiche tels quels.
"""
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("PROFILE_DATA") or os.path.join(HERE, "data", "github-profile.json")
OUT  = os.path.join(HERE, "assets")

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
 "light": dict(bg="#fcfcfb", line="#e4e3de", tp="#0b0b0b", ts="#52514e", tm="#8a8983",
               s1="#2a78d6", s2="#eb6834", s3="#1baf7a", gray="#8a8983", soft="#e8f0fc"),
 "dark":  dict(bg="#1a1a19", line="#33332f", tp="#ffffff", ts="#c3c2b7", tm="#8a8983",
               s1="#3987e5", s2="#d95926", s3="#199e70", gray="#8a8983", soft="#1e2c3f"),
}

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def txt(x, y, s, size=13, fill="tp", weight="400", anchor="start", th=None, font=FONT):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" fill="{th[fill]}" text-anchor="{anchor}">{esc(s)}</text>')

def frame(w, h, th, title, subtitle=None):
    o  = f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="{th["bg"]}" stroke="{th["line"]}"/>'
    o += txt(24, 34, title, 16, "tp", "600", th=th)
    if subtitle:
        o += txt(24, 54, subtitle, 12, "tm", th=th)
    return o

def nfmt(n):
    return f"{n:,}".replace(",", " ")   # espace fine

# ---------------------------------------------------------------- chargement
if not os.path.exists(DATA):
    sys.exit(f"Fichier introuvable : {DATA}\nLance d'abord scripts/collect.py")
with open(DATA, encoding="utf-8") as _f:
    d = json.load(_f)
A, T, R = d["account"], d["totals"], d["repos"]

months = d["commits_by_month"]
yr = defaultdict(int)
for k, v in months.items():
    yr[k[:4]] += v

lb = d["language_bytes"]; ltot = sum(lb.values()) or 1
GROUP = {"C#": "gfx_no", "ASP.NET": "net"}
def group_of(lang):
    if lang in ("C#", "ASP.NET"):                       return "net"
    if lang in ("ShaderLab", "GLSL", "HLSL", "C++", "C", "Processing"): return "gfx"
    if lang in ("TypeScript", "JavaScript", "HTML", "CSS", "SCSS"):     return "web"
    return "other"
g = defaultdict(int)
for k, v in lb.items():
    g[group_of(k)] += v

# Lignes calculees en amont par collect.py, a partir des chemins reels de
# chaque fichier : le code tiers et le code genere sont deja ecartes.
loc_written  = T.get("loc_written", 0)
loc_vendored = T.get("loc_vendored", 0)

def mfmt(n):
    """54074266 -> 54.1M ; 31034 -> 31k."""
    if n >= 1e6:  return f"{n/1e6:.1f}M"
    if n >= 1e3:  return f"{n/1e3:.0f}k"
    return str(int(n))

def period(r):
    a = (r.get("first_commit") or r.get("created_at") or "")[:4]
    b = (r.get("last_commit") or r.get("pushed_at") or "")[:4]
    if not a: return "—"
    return a if a == b else f"{a}–{b}"

def dom(pred):
    rs = [r for r in R if pred(r)]
    return len(rs), sum(r.get("my_commits", 0) for r in rs)
net_n, net_c = dom(lambda r: (r.get("languages") or {}).get("C#"))
web_n, web_c = dom(lambda r: (r.get("languages") or {}).get("TypeScript"))
gfx_n, gfx_c = dom(lambda r: any((r.get("languages") or {}).get(x)
                                 for x in ("ShaderLab", "HLSL", "GLSL")))

sm = d["stack_markers"]
FW_KEEP = ["Angular", "Docker", "Vercel", "Next.js", "GitHub Actions", "Tailwind CSS",
           "Claude Code", "Vitest", "Railway", "Playwright", "Firebase", "Prisma"]
fw = {k: sm[k] for k in FW_KEEP if k in sm}
fw["NestJS"] = d["top_dependencies"].get("@nestjs/core", 0)
fw = dict(sorted(fw.items(), key=lambda x: -x[1])[:12])

AIM = {"Claude Code", "Agents (Codex/OpenAI)", "MCP servers"}
airepos = [r for r in R if set(r.get("markers", [])) & AIM
           or "openai" in r.get("dependencies", [])
           or "@anthropic-ai/sdk" in r.get("dependencies", [])
           or "anthropic" in r.get("dependencies", [])]
ai_year = defaultdict(int)
for r in airepos:
    ai_year[r["created_at"][:4]] += 1


# ================================================================= carte 1
def card_overview(th):
    W, H = 840, 286
    o = frame(W, H, th, "GitHub at a glance",
              f"{T['repos']} repositories · {T['private']} private · {A['years_on_github']} years of history")
    kpis = [(nfmt(T["repos"]), "repositories"),
            (nfmt(T["my_commits"]), "commits authored"),
            (str(A["years_on_github"]), "years active"),
            (f"{loc_written/1e6:.1f}M", "lines of code*"),
            (f"{T['files_indexed']//1000}k", "files indexed"),
            (f"{ltot/1e6:.0f} MB", "of source")]
    x, bw = 24, 130
    for val, lab in kpis:
        o += f'<rect x="{x}" y="70" width="{bw}" height="66" rx="9" fill="{th["soft"]}"/>'
        o += txt(x + 14, 102, val, 21, "tp", "650", th=th)
        o += txt(x + 14, 121, lab, 11, "ts", th=th)
        x += bw + 3
    o += txt(24, 168, "CODE DISTRIBUTION BY DOMAIN", 10, "tm", "600", th=th)
    segs = [("Graphics / Unity", g["gfx"], th["s3"]),
            (".NET Backend",     g["net"], th["s1"]),
            ("Web / TypeScript", g["web"], th["s2"]),
            ("Other",            g["other"], th["gray"])]
    x, BW = 24, W - 48
    for name, v, col in segs:
        w = BW * v / ltot
        o += f'<rect x="{x:.1f}" y="180" width="{max(w-2,1):.1f}" height="30" rx="5" fill="{col}"/>'
        if w > 64:
            o += (f'<text x="{x+w/2-1:.1f}" y="200" font-family="{FONT}" font-size="12" '
                  f'font-weight="650" fill="#ffffff" text-anchor="middle">{100*v/ltot:.0f}%</text>')
        x += w
    colw = (W - 48) / 4
    for i, (name, v, col) in enumerate(segs):
        x = 24 + colw * i
        o += f'<rect x="{x:.1f}" y="231" width="10" height="10" rx="3" fill="{col}"/>'
        o += txt(x + 16, 240, name, 11.5, "ts", th=th)
        o += txt(x + colw - 14, 240, f"{100*v/ltot:.1f}%", 11.5, "tp", "600", "end", th)
    o += txt(24, 259, "* estimated from source bytes, third-party and generated code excluded",
             10, "tm", th=th)
    return W, H, o


# ================================================================= carte 2
def card_activity(th):
    W, H = 840, 266
    years = [str(y) for y in range(2015, int(max(yr)) + 1)]
    vals  = [yr.get(y, 0) for y in years]
    mx    = max(vals) or 1
    o = frame(W, H, th, "Commit volume by year",
              f"{nfmt(T['my_commits'])} commits authored across {len(months)} active months")
    x0, x1, base, top = 30, W - 30, 208, 84
    slot = (x1 - x0) / len(years)
    bw = min(slot - 9, 52)
    for i, (y, v) in enumerate(zip(years, vals)):
        cx = x0 + slot * i + slot / 2
        h  = (v / mx) * (base - top)
        hi = (y == years[-1])
        col = th["s1"] if hi else th["soft"]
        o += (f'<rect x="{cx-bw/2:.1f}" y="{base-h:.1f}" width="{bw:.1f}" '
              f'height="{max(h,2):.1f}" rx="4" fill="{col}"/>')
        if v:
            o += txt(cx, base - h - 7, nfmt(v), 10.5, "tp" if hi else "tm",
                     "650" if hi else "400", "middle", th)
        o += txt(cx, base + 18, y, 10.5, "tp" if hi else "tm",
                 "650" if hi else "400", "middle", th)
    o += f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="{th["line"]}" stroke-width="1"/>'
    note = (f"Current year still in progress · per-year breakdown covers "
            f"{nfmt(sum(vals))} of {nfmt(T['my_commits'])} commits · "
            f"updated {d['generated_at'][:10]}")
    o += txt(30, H - 16, note, 10.5, "tm", th=th)
    return W, H, o


# ================================================================= carte 3
def card_stack(th):
    rows = list(fw.items())
    W, H = 840, 108 + len(rows) * 23 + 46
    o = frame(W, H, th, "Detected stack",
              "Repositories where the marker actually exists in the file tree")
    mxv = max(v for _, v in rows) or 1
    LX, TX, TW = 24, 168, W - 168 - 66
    y = 90
    for k, v in rows:
        o += txt(LX + 128, y + 12, k, 12, "ts", anchor="end", th=th)
        o += f'<rect x="{TX}" y="{y}" width="{TW}" height="17" rx="4" fill="{th["soft"]}"/>'
        o += f'<rect x="{TX}" y="{y}" width="{max(TW*v/mxv,3):.1f}" height="17" rx="4" fill="{th["s1"]}"/>'
        o += txt(TX + TW + 10, y + 12, str(v), 12, "tp", "600", th=th)
        y += 23
    prof = (f"{net_n} .NET repos ({nfmt(net_c)} commits)  ·  "
            f"{web_n} TypeScript repos ({nfmt(web_c)} commits)  ·  "
            f"{gfx_n} Unity / shader repos ({nfmt(gfx_c)} commits)")
    o += txt(24, y + 22, prof, 11.5, "tm", th=th)
    return W, H, o


# ================================================================= carte 4
def card_agentic(th):
    W, H = 840, 226
    o = frame(W, H, th, "AI / agentic tooling",
              "Agent configuration committed to the repositories themselves")
    kpis = [(str(len(airepos)), "repos with AI signal"),
            (str(sm.get("Claude Code", 0)), "with CLAUDE.md"),
            (str(sm.get("Agents (Codex/OpenAI)", 0)), "with AGENTS.md"),
            (str(sm.get("MCP servers", 0)), "with .mcp.json")]
    x, bw = 24, 194
    for val, lab in kpis:
        o += f'<rect x="{x}" y="70" width="{bw}" height="62" rx="9" fill="{th["soft"]}"/>'
        o += txt(x + 14, 100, val, 20, "tp", "650", th=th)
        o += txt(x + 14, 118, lab, 10.5, "ts", th=th)
        x += bw + 4
    o += txt(24, 158, "NEW AI-ENABLED REPOSITORIES PER YEAR", 10, "tm", "600", th=th)
    ys = [str(y) for y in range(2022, int(max(yr)) + 1)]
    vs = [ai_year.get(y, 0) for y in ys]
    mx = max(vs) or 1
    x, base, hmax = 24, 200, 32
    for y, v in zip(ys, vs):
        h = (v / mx) * hmax
        o += f'<rect x="{x}" y="{base-h:.1f}" width="42" height="{max(h,2):.1f}" rx="3" fill="{th["s1"]}"/>'
        o += txt(x + 21, base - h - 6, str(v), 10.5, "tp", "650", "middle", th)
        o += txt(x + 21, base + 15, y, 10.5, "tm", anchor="middle", th=th)
        x += 56
    return W, H, o



# ================================================================= carte 5
def card_repos(th):
    """Tableau pleine largeur : une ligne par repo, une colonne par mesure.

    Chaque colonne porte son titre : rien a decoder, contrairement aux deux
    panneaux serres de la version precedente.
    """
    W = 840
    rows  = sorted(R, key=lambda r: -(r.get("my_commits") or 0))[:10]
    H = 110 + len(rows) * 22 + 42
    o = frame(W, H, th, "Top repositories",
              f"Commits and lines authored by @{A['login']} \u00b7 {T['repos']} repositories scanned")

    # colonnes : x, titre, alignement
    X_NAME, X_LANG, X_PERIOD = 24, 232, 316
    X_BAR, BAR_W = 404, 118
    X_COMMITS, X_ADD, X_DEL = 566, 692, 816

    o += txt(X_NAME,    92, "REPOSITORY",    10, "tm", "600", th=th)
    o += txt(X_LANG,    92, "LANGUAGE",      10, "tm", "600", th=th)
    o += txt(X_PERIOD,  92, "PERIOD",        10, "tm", "600", th=th)
    o += txt(X_COMMITS, 92, "COMMITS",       10, "tm", "600", "end", th)
    o += txt(X_ADD,     92, "LINES ADDED",   10, "tm", "600", "end", th)
    o += txt(X_DEL,     92, "LINES DELETED", 10, "tm", "600", "end", th)
    o += f'<rect x="24" y="98" width="{W-48}" height="1" fill="{th["line"]}"/>'

    mx = max((r.get("my_commits") or 0) for r in rows) or 1
    y = 118
    for r in rows:
        priv = r.get("private")
        name = r["id"].split("/")[-1]
        if len(name) > 24:
            name = name[:23] + "\u2026"
        o += txt(X_NAME, y, name, 11.5, "ts" if priv else "tp", "500" if priv else "600", th=th)
        o += txt(X_LANG, y, r.get("primary_language") or "mixed", 11, "tm", th=th)
        o += txt(X_PERIOD, y, period(r), 11, "tm", th=th)

        c = r.get("my_commits") or 0
        o += f'<rect x="{X_BAR}" y="{y-10}" width="{BAR_W}" height="12" rx="3" fill="{th["soft"]}"/>'
        o += (f'<rect x="{X_BAR}" y="{y-10}" width="{max(BAR_W*c/mx, 3):.1f}" height="12" rx="3" '
              f'fill="{th["s2"] if priv else th["s1"]}"/>')
        o += txt(X_COMMITS, y, nfmt(c), 11.5, "tp", "600", "end", th)

        # Le churn peut manquer : l'API GitHub calcule ces statistiques en
        # tache de fond. Un tiret est honnete, un zero serait faux.
        add, dele = r.get("churn_additions"), r.get("churn_deletions")
        o += txt(X_ADD, y, f"+{mfmt(add)}" if add is not None else "\u2014",
                 11.5, "s3" if add is not None else "tm", "600" if add is not None else "400",
                 "end", th)
        o += txt(X_DEL, y, f"\u2212{mfmt(dele)}" if dele is not None else "\u2014",
                 11.5, "s2" if dele is not None else "tm", "600" if dele is not None else "400",
                 "end", th)
        y += 22

    fy = H - 20
    o += f'<rect x="24" y="{fy-9}" width="9" height="9" rx="2" fill="{th["s1"]}"/>'
    o += txt(38, fy, "public", 10.5, "tm", th=th)
    o += f'<rect x="90" y="{fy-9}" width="9" height="9" rx="2" fill="{th["s2"]}"/>'
    o += txt(104, fy, "private", 10.5, "tm", th=th)
    o += txt(W - 24, fy,
             "lines from GitHub contributor stats \u2014 all files, asset imports included",
             10.5, "tm", anchor="end", th=th)
    return W, H, o


CARDS = {"overview": card_overview, "activity": card_activity,
         "stack": card_stack, "repos": card_repos, "agentic": card_agentic}

def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in CARDS.items():
        for mode, th in THEMES.items():
            w, h, body = fn(th)
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                   f'viewBox="0 0 {w} {h}" role="img" aria-label="{name} card">{body}</svg>')
            p = os.path.join(OUT, f"{name}-{mode}.svg")
            open(p, "w", encoding="utf-8").write(svg)
            print("ecrit", os.path.relpath(p, HERE), f"({len(svg)} o)")
    print(f"\nOK \u2014 {len(CARDS)*2} cartes generees.")


if __name__ == "__main__":
    main()
