#!/usr/bin/env python3
"""
collect_claude.py — instantane d'usage de Claude Code, pris sur CETTE machine.

    python3 scripts/collect_claude.py --machine "MacBook Air" --out data/claude-code.json

Difference majeure avec collect.py : les donnees de Claude Code n'existent
QUE en local (~/.claude). Aucune API ne les expose, donc GitHub Actions ne
peut pas les regenerer. Le JSON produit est donc VERSIONNE, contrairement au
reste de data/ : c'est un instantane, date, valable pour un seul poste.

Rien du contenu des conversations ne sort d'ici : le script ne lit que des
compteurs et des metadonnees d'agents. Les chemins de projet sont remplaces
par project-01, project-02, ... — ils portent des noms de clients.

Aucune dependance externe. Python 3.8+.
"""
import os, sys, json, re, glob, argparse, datetime
from collections import defaultdict, Counter

HOME = os.path.expanduser("~")


def encode_project(path):
    """Reproduit l'encodage de Claude Code : /Users/x/a_b -> -Users-x-a-b.

    Permet de rapprocher une entree d'historique (qui stocke le chemin brut)
    du repertoire correspondant dans ~/.claude/projects.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def read_history(root):
    """Prompts saisis : le seul endroit qui garde trace des sessions purgees.

    Retourne (nb_prompts, sessions par projet, prompts par projet, par mois).
    Le texte des prompts est lu puis jete : seuls les compteurs sortent.
    """
    path = os.path.join(root, "history.jsonl")
    prompts = 0
    sessions = defaultdict(set)
    per_project = Counter()
    per_month = Counter()
    stamps = []
    if not os.path.exists(path):
        return prompts, sessions, per_project, per_month, stamps

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue            # ligne tronquee : on l'ignore, on ne devine pas
            prompts += 1
            key = encode_project(e["project"]) if e.get("project") else "-unknown"
            per_project[key] += 1
            if e.get("sessionId"):
                sessions[key].add(e["sessionId"])
            if e.get("timestamp"):
                t = datetime.datetime.fromtimestamp(e["timestamp"] / 1000)
                per_month[t.strftime("%Y-%m")] += 1
                stamps.append(t)
    return prompts, sessions, per_project, per_month, stamps


def read_transcripts(root):
    """Transcripts encore sur disque, par projet.

    Toujours moins nombreux que les sessions de l'historique : Claude Code
    elague. Publier les deux chiffres est plus honnete que n'en publier qu'un.
    """
    per_project = Counter()
    for p in glob.glob(os.path.join(root, "projects", "*", "*.jsonl")):
        per_project[os.path.basename(os.path.dirname(p))] += 1
    return per_project


def read_agents(root):
    """Sous-agents lances, d'apres leurs fichiers .meta.json.

    Chaque agent laisse un couple <id>.jsonl + <id>.meta.json. On ne lit que
    le second : il porte le type, le modele et la profondeur, jamais le
    contenu de la tache.
    """
    per_project = Counter()
    by_model = Counter()
    by_type = Counter()
    nested = 0
    for p in glob.glob(os.path.join(root, "projects", "*", "*", "subagents", "*.meta.json")):
        # .../projects/<projet>/<session>/subagents/<agent>.meta.json
        project = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(p))))
        per_project[project] += 1
        try:
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
        except (ValueError, OSError):
            by_model["unknown"] += 1
            continue
        by_model[m.get("model") or "unknown"] += 1
        by_type[m.get("agentType") or "unknown"] += 1
        if m.get("parentAgentId") or (m.get("spawnDepth") or 1) > 1:
            nested += 1
    return per_project, by_model, by_type, nested


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_snapshot(path, machines, anonymized=None):
    """Ecrit l'instantane : le detail par poste, plus le total en tete.

    Le total reste au premier niveau, a la place exacte qu'il occupait du
    temps ou il n'y avait qu'un poste : les cartes deja ecrites continuent de
    le lire sans rien savoir des machines.
    """
    if anonymized is None:                 # --add-machine ne juge pas de ca
        anonymized = True
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                anonymized = json.load(f).get("anonymized", True)

    out = {
        "schema": "claude-code-usage/2.0",
        "generated_at": stamp(),
        "scope": "%d machine(s) — Claude Code stores nothing centrally"
                 % len(machines),
        "anonymized": anonymized,
        "machines": machines,
    }
    out.update(aggregate(machines))

    dest = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    t = out["totals"]
    print("ecrit %s" % path)
    for m in machines:
        mt = m.get("totals") or {}
        print("  %-16s %4d sessions, %4d agents, %5d prompts%s"
              % (m["name"], mt.get("sessions", 0), mt.get("agents", 0),
                 mt.get("prompts", 0),
                 "" if m.get("source") == "collector" else "   (releve a la main)"))
    print("  %-16s %4d sessions, %4d agents, %5d prompts"
          % ("TOTAL", t.get("sessions", 0), t.get("agents", 0), t.get("prompts", 0)))
    print("  periode %s -> %s" % (out["period"]["first"], out["period"]["last"]))
    return out


def merge_month_counters(machines):
    out = Counter()
    for m in machines:
        out.update(m.get("prompts_by_month") or {})
    return dict(sorted(out.items()))


def aggregate(machines):
    """Additionne les postes en un total lisible d'un coup d'oeil.

    Chaque poste garde son detail : le total ne remplace pas les lignes, il
    les resume. Un poste qui n'a pas su remplir un champ (la tour, relevee a
    la main, ne connait pas la repartition par modele) ne fait pas mentir la
    somme : elle porte alors sur les seuls postes qui l'ont renseigne.
    """
    totals = Counter()
    for m in machines:
        totals.update(m.get("totals") or {})

    firsts = [m["period"]["first"] for m in machines if (m.get("period") or {}).get("first")]
    lasts = [m["period"]["last"] for m in machines if (m.get("period") or {}).get("last")]

    by_model, by_type, nested, reported = Counter(), Counter(), 0, 0
    for m in machines:
        if m.get("agents_by_model") is None:
            continue
        reported += 1
        by_model.update(m.get("agents_by_model") or {})
        by_type.update(m.get("agents_by_type") or {})
        nested += m.get("agents_nested") or 0

    return {
        "period": {"first": min(firsts) if firsts else None,
                   "last": max(lasts) if lasts else None},
        "totals": dict(totals),
        "prompts_by_month": merge_month_counters(machines),
        "agents_by_model": dict(by_model.most_common()),
        "agents_by_type": dict(by_type.most_common()),
        "agents_nested": nested,
        # Combien de postes ont su detailler leurs agents : la carte le dit
        # plutot que de laisser croire que la barre couvre tout le monde.
        "model_split_machines": reported,
    }


def load_existing(path):
    """Relit l'instantane, en acceptant l'ancienne forme a un seul poste."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("machines"):
        return d["machines"]
    if not d.get("totals"):
        return []
    return [{k: v for k, v in (
        ("name", d.get("machine", "unknown")),
        ("collected_at", d.get("generated_at")),
        ("source", "collector"),
        ("period", d.get("period")),
        ("totals", d.get("totals")),
        ("prompts_by_month", d.get("prompts_by_month")),
        ("agents_by_model", d.get("agents_by_model")),
        ("agents_by_type", d.get("agents_by_type")),
        ("agents_nested", d.get("agents_nested")),
        ("projects", d.get("projects")),
    ) if v is not None}]


def upsert(machines, entry):
    """Remplace le poste du meme nom, sinon l'ajoute. Recollecter est idempotent."""
    out = [m for m in machines if m.get("name") != entry["name"]]
    out.append(entry)
    out.sort(key=lambda m: -((m.get("totals") or {}).get("sessions") or 0))
    return out


def parse_months(text):
    """'2026-03:10,2026-04:50' -> {'2026-03': 10, '2026-04': 50}."""
    out = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, _, value = chunk.partition(":")
        key = key.strip()
        if not re.match(r"^\d{4}-\d{2}$", key) or not value.strip().isdigit():
            raise SystemExit("mois illisible : %r (attendu AAAA-MM:nombre)" % chunk)
        out[key] = int(value)
    return dict(sorted(out.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="one workstation",
                    help="libelle du poste, affiche tel quel sur la carte")
    ap.add_argument("--claude-home", default=os.path.join(HOME, ".claude"),
                    help="racine des donnees Claude Code (defaut ~/.claude)")
    ap.add_argument("--keep-project-names", action="store_true",
                    help="garde les vrais noms de projet (deconseille : noms de clients)")
    ap.add_argument("--out", default="data/claude-code.json")

    # Relever un poste ou le depot n'est pas clone : on y lance la commande
    # courte, on recopie ses chiffres ici. Ce poste rejoint l'instantane sans
    # que son ~/.claude soit lisible depuis cette machine.
    ap.add_argument("--add-machine", metavar="NOM",
                    help="ajoute un poste a partir de chiffres releves ailleurs")
    ap.add_argument("--sessions", type=int, default=0)
    ap.add_argument("--transcripts", type=int, default=0)
    ap.add_argument("--agents", type=int, default=0)
    ap.add_argument("--prompts", type=int, default=0)
    ap.add_argument("--projects", type=int, default=0)
    ap.add_argument("--months", default="",
                    help="prompts par mois : '2026-03:10,2026-04:50'")
    args = ap.parse_args()

    if args.add_machine:
        months = parse_months(args.months)
        entry = {
            "name": args.add_machine,
            "collected_at": stamp(),
            # Releve a la main : la commande courte ne donne pas la
            # repartition par modele. Ne pas inventer le champ le dit mieux
            # qu'un zero, et l'agregation sait l'ignorer.
            "source": "reported",
            "period": {"first": min(months) if months else None,
                       "last": max(months) if months else None},
            "totals": {"sessions": args.sessions,
                       "transcripts_on_disk": args.transcripts,
                       "agents": args.agents,
                       "prompts": args.prompts,
                       "projects": args.projects},
            "prompts_by_month": months,
        }
        write_snapshot(args.out, upsert(load_existing(args.out), entry))
        return

    root = args.claude_home
    if not os.path.isdir(root):
        sys.exit("Introuvable : %s — Claude Code n'a jamais tourne sur ce poste ?" % root)

    prompts, sess_by_proj, prompts_by_proj, by_month, stamps = read_history(root)
    transcripts = read_transcripts(root)
    agents_by_proj, by_model, by_type, nested = read_agents(root)

    # Un projet compte des qu'il apparait dans l'une des trois sources : un
    # projet dont tous les transcripts ont ete elagues existe quand meme.
    keys = set(sess_by_proj) | set(transcripts) | set(agents_by_proj)
    rows = []
    for k in keys:
        rows.append({"key": k,
                     "sessions": len(sess_by_proj.get(k, ())),
                     "transcripts": transcripts.get(k, 0),
                     "agents": agents_by_proj.get(k, 0),
                     "prompts": prompts_by_proj.get(k, 0)})
    rows.sort(key=lambda r: (-r["sessions"], -r["agents"], r["key"]))
    for i, r in enumerate(rows, 1):
        if not args.keep_project_names:
            r["key"] = "project-%02d" % i

    entry = {
        "name": args.machine,
        "collected_at": stamp(),
        "source": "collector",
        "period": {
            "first": min(stamps).strftime("%Y-%m-%d") if stamps else None,
            "last":  max(stamps).strftime("%Y-%m-%d") if stamps else None,
        },
        "totals": {
            "sessions": sum(len(v) for v in sess_by_proj.values()),
            "transcripts_on_disk": sum(transcripts.values()),
            "agents": sum(agents_by_proj.values()),
            "prompts": prompts,
            "projects": len(keys),
        },
        "prompts_by_month": dict(sorted(by_month.items())),
        "agents_by_model": dict(by_model.most_common()),
        "agents_by_type": dict(by_type.most_common()),
        "agents_nested": nested,
        "projects": rows,
    }
    write_snapshot(args.out, upsert(load_existing(args.out), entry),
                   anonymized=not args.keep_project_names)


if __name__ == "__main__":
    main()
