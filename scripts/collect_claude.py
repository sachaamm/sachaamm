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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="one workstation",
                    help="libelle du poste, affiche tel quel sur la carte")
    ap.add_argument("--claude-home", default=os.path.join(HOME, ".claude"),
                    help="racine des donnees Claude Code (defaut ~/.claude)")
    ap.add_argument("--keep-project-names", action="store_true",
                    help="garde les vrais noms de projet (deconseille : noms de clients)")
    ap.add_argument("--out", default="data/claude-code.json")
    args = ap.parse_args()

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

    out = {
        "schema": "claude-code-usage/1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": args.machine,
        "scope": "single machine — Claude Code stores nothing centrally",
        "anonymized": not args.keep_project_names,
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

    dest = args.out if os.path.isabs(args.out) else os.path.join(os.getcwd(), args.out)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    t = out["totals"]
    print("ecrit %s" % args.out)
    print("  %(sessions)d sessions, %(transcripts_on_disk)d transcripts sur disque, "
          "%(agents)d agents, %(prompts)d prompts, %(projects)d projets" % t)
    print("  periode %s -> %s, poste : %s"
          % (out["period"]["first"], out["period"]["last"], out["machine"]))


if __name__ == "__main__":
    main()
