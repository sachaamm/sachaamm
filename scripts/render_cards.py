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
DATA = os.path.join(HERE, "data", "github-profile.json")
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

# Octets par ligne, moyennes observées par langage. Sert à estimer les LOC
# à partir des octets renvoyés par l'API (GitHub ne fournit pas de compte de lignes).
BYTES_PER_LINE = {
 "C#":31,"ASP.NET":34,"TypeScript":29,"JavaScript":30,"HTML":38,"CSS":24,"SCSS":24,
 "Python":29,"Java":32,"Kotlin":30,"C++":29,"C":28,"PHP":30,"Go":28,"Rust":29,"Ruby":26,
 "Shell":26,"PowerShell":30,"ShaderLab":26,"GLSL":26,"HLSL":26,"Swift":30,"Dart":28,
 "Vue":30,"Svelte":30,"Processing":28,"EJS":34,"Astro":30,"Dockerfile":28,"Makefile":24,
}
BPL_DEFAULT = 30

# Langages de shaders : très majoritairement générés (Shader Graph) ou importés
# depuis l'Asset Store. Exclus du décompte de lignes écrites à la main.
GENERATED_LANGS = {"ShaderLab", "GLSL", "HLSL"}

def est_loc(langs, skip_generated=True):
    """Lignes estimées à partir des octets par langage."""
    t = 0.0
    for k, v in (langs or {}).items():
        if skip_generated and k in GENERATED_LANGS:
            continue
        t += v / BYTES_PER_LINE.get(k, BPL_DEFAULT)
    return t

# ---------------------------------------------------------------- chargement
if not os.path.exists(DATA):
    sys.exit(f"Fichier introuvable : {DATA}\nLance d'abord scripts/collect.py")
d = json.load(open(DATA, encoding="utf-8"))
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

loc_written  = est_loc(lb, skip_generated=True)
loc_shaders  = est_loc({k: v for k, v in lb.items() if k in GENERATED_LANGS},
                       skip_generated=False)

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
    o += txt(24, 259, "* lines estimated from source bytes, excluding generated shader code",
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
def _label(r, metric):
    """Libellé lisible : nom réel si public, description neutre si privé."""
    lang = r.get("primary_language") or "mixed"
    if not r["private"]:
        name = r["id"].split("/")[-1]
        return (name[:24] + "…") if len(name) > 25 else name
    if metric == "commits":
        a = (r.get("first_commit") or r.get("created_at", ""))[:4]
        b = (r.get("last_commit") or r.get("pushed_at", ""))[:4]
    else:
        a = (r.get("created_at") or "")[:4]
        b = (r.get("pushed_at") or "")[:4]
    span = a[2:] if a == b else f"{a[2:]}–{b[2:]}"
    return f"Private · {lang} · {span}"


def card_repos(th):
    W = 840
    by_commits = sorted(R, key=lambda r: -r.get("my_commits", 0))[:10]
    by_loc     = sorted(R, key=lambda r: -est_loc(r.get("languages")))[:10]
    rows = 10
    H = 118 + rows * 22 + 34
    o = frame(W, H, th, "Top repositories",
              "Private repositories are counted and described, never named")

    PW, GAP = 372, 24
    panels = [
        (24,            "BY COMMITS",       by_commits,
         lambda r: r.get("my_commits", 0), lambda v: nfmt(v), "commits"),
        (24 + PW + GAP, "BY SIZE (EST. LOC)", by_loc,
         lambda r: est_loc(r.get("languages")),
         lambda v: f"{v/1000:.0f}k" if v >= 1000 else f"{v:.0f}", "loc"),
    ]
    for px, head, items, val, fmt, metric in panels:
        o += txt(px, 92, head, 10, "tm", "600", th=th)
        mx = max(val(r) for r in items) or 1
        LW, BW = 150, 128
        y = 106
        for r in items:
            v = val(r)
            o += txt(px + LW - 8, y + 12, _label(r, metric), 10.5,
                     "ts" if r["private"] else "tp",
                     "400" if r["private"] else "600", "end", th)
            bx = px + LW
            o += f'<rect x="{bx}" y="{y+2}" width="{BW}" height="13" rx="3" fill="{th["soft"]}"/>'
            o += (f'<rect x="{bx}" y="{y+2}" width="{max(BW*v/mx,3):.1f}" height="13" rx="3" '
                  f'fill="{th["s1"] if not r["private"] else th["s2"]}"/>')
            o += txt(px + PW, y + 12, fmt(v), 10.5, "tp", "600", "end", th)
            y += 22
    o += f'<rect x="24" y="{H-30}" width="9" height="9" rx="2" fill="{th["s1"]}"/>'
    o += txt(38, {}, "public", 10.5, "tm", th=th).replace("{}", str(H - 22))
    o += f'<rect x="90" y="{H-30}" width="9" height="9" rx="2" fill="{th["s2"]}"/>'
    o += txt(104, H - 22, "private", 10.5, "tm", th=th)
    o += txt(W - 24, H - 22,
             f"{loc_written/1e6:.1f}M lines written · {loc_shaders/1e6:.1f}M generated shader lines excluded",
             10.5, "tm", anchor="end", th=th)
    return W, H, o

CARDS = {"overview": card_overview, "activity": card_activity,
         "stack": card_stack, "repos": card_repos, "agentic": card_agentic}

os.makedirs(OUT, exist_ok=True)
for name, fn in CARDS.items():
    for mode, th in THEMES.items():
        W, H, body = fn(th)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}" role="img" aria-label="{esc(name)} card">{body}</svg>')
        p = os.path.join(OUT, f"{name}-{mode}.svg")
        open(p, "w", encoding="utf-8").write(svg)
        print("écrit", os.path.relpath(p, HERE), f"({len(svg)} o)")
print(f"\nOK — {len(CARDS)*2} cartes générées.")
