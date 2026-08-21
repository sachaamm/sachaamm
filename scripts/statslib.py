"""
Fonctions pures partagées par collect.py et render_cards.py.

Aucun I/O, aucun appel réseau : tout est testable hors ligne (tests/test_statslib.py).
"""
from collections import defaultdict

# ---------------------------------------------------------------- vendored
# Dossiers de code tiers : dépendances installées, artefacts de build, et
# sorties d'outils Unity qui *génèrent* du shader (MicroSplat, Amplify Shader
# Editor) ou packs acquis sur l'Asset Store. Ce code existe dans le dépôt mais
# n'a pas été écrit à la main : il ne compte pas comme des lignes écrites.
VENDORED_DIRS = {
    "node_modules", "bower_components", "vendor", "third_party", "thirdparty",
    "packages", "library", "obj", "bin", "dist", "build", "out",
    "venv", ".venv", "site-packages", "pods", "carthage", "plugins",
    "migrations", "__pycache__",
}

# Préfixes de dossiers : une même famille d'outils crée plusieurs variantes
# (MicroSplatData, "MicroSplat 1", MicroSplatData/Scenes/...).
VENDORED_DIR_PREFIXES = (
    "microsplat", "amplifyshader", "visual design cafe", "assetstore",
)

# Préfixes de fichiers : Amplify Shader Editor préfixe ses shaders générés
# par ASE_, où qu'ils soient rangés.
VENDORED_FILE_PREFIXES = ("ase_",)


def is_vendored(path):
    """Vrai si le chemin désigne du code tiers, importé ou généré par un outil."""
    segs = path.lower().split("/")
    for seg in segs[:-1]:
        if seg in VENDORED_DIRS or seg.startswith(VENDORED_DIR_PREFIXES):
            return True
    return segs[-1].startswith(VENDORED_FILE_PREFIXES)


# ---------------------------------------------------------------- langages
EXT_LANG = {
    ".cs": "C#", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".vue": "Vue", ".svelte": "Svelte", ".py": "Python", ".php": "PHP",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".rb": "Ruby", ".swift": "Swift", ".dart": "Dart", ".sql": "SQL",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell",
    ".scss": "SCSS", ".sass": "SCSS", ".css": "CSS", ".html": "HTML",
    ".htm": "HTML", ".razor": "Blazor", ".cshtml": "ASP.NET",
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cc": "C++",
    ".m": "Objective-C", ".mm": "Objective-C", ".lua": "Lua", ".ex": "Elixir",
    ".shader": "ShaderLab", ".cginc": "ShaderLab", ".hlsl": "HLSL",
    ".glsl": "GLSL", ".vert": "GLSL", ".frag": "GLSL", ".compute": "HLSL",
    ".ino": "C++", ".pde": "Processing", ".astro": "Astro", ".ejs": "EJS",
}

# Octets par ligne, moyennes observées par langage. L'API GitHub renvoie des
# octets, jamais des lignes : les LOC sont donc estimées, pas comptées.
BYTES_PER_LINE = {
    "C#": 31, "ASP.NET": 34, "TypeScript": 29, "JavaScript": 30, "HTML": 38,
    "CSS": 24, "SCSS": 24, "Python": 29, "Java": 32, "Kotlin": 30, "C++": 29,
    "C": 28, "PHP": 30, "Go": 28, "Rust": 29, "Ruby": 26, "Shell": 26,
    "PowerShell": 30, "ShaderLab": 26, "GLSL": 26, "HLSL": 26, "Swift": 30,
    "Dart": 28, "Vue": 30, "Svelte": 30, "Processing": 28, "EJS": 34,
    "Astro": 30, "SQL": 26, "Lua": 26, "Objective-C": 30, "Blazor": 34,
    "Elixir": 28,
}
BPL_DEFAULT = 30


def lang_of_path(path):
    """Langage déduit de l'extension, ou None si l'extension est inconnue."""
    base = path.rsplit("/", 1)[-1]
    dot = base.rfind(".")
    if dot <= 0:
        return None
    return EXT_LANG.get(base[dot:].lower())


def est_lines(size, lang):
    """Lignes estimées pour `size` octets de `lang`."""
    return size / BYTES_PER_LINE.get(lang, BPL_DEFAULT)


def loc_from_tree(blobs):
    """Sépare les lignes écrites des lignes tierces, à partir de l'arbre git.

    `blobs` : itérable de {"path": str, "size": int}, tel que renvoyé par
    l'API /git/trees?recursive=1. Les fichiers sans extension connue et les
    fichiers vides sont ignorés.
    """
    res = {"written": defaultdict(float), "vendored": defaultdict(float)}
    for b in blobs:
        size = b.get("size") or 0
        if not size:
            continue
        lang = lang_of_path(b["path"])
        if lang is None:
            continue
        bucket = "vendored" if is_vendored(b["path"]) else "written"
        res[bucket][lang] += est_lines(size, lang)
    return {k: dict(v) for k, v in res.items()}


# ---------------------------------------------------------------- nommage
def repos_to_name(repos, top_n=10, never_name=()):
    """Repos autorisés à porter leur vrai nom.

    Seuls ceux qui peuvent réellement apparaître sur une carte : les `top_n`
    premiers par commits et les `top_n` premiers par churn. Tous les autres
    restent anonymes, y compris dans le JSON intermédiaire. `never_name` a
    toujours le dernier mot.
    """
    named = set()
    for key in (lambda r: r.get("my_commits") or 0, lambda r: r.get("churn") or 0):
        for r in sorted(repos, key=key, reverse=True)[:top_n]:
            named.add(r["id"])
    return named - set(never_name)


# ---------------------------------------------------------------- churn
def author_churn(stats, login):
    """Commits, lignes ajoutées et supprimées pour un auteur donné.

    `stats` : réponse de /repos/{o}/{r}/stats/contributors. L'API renvoie un
    objet vide tant qu'elle calcule les statistiques (HTTP 202) : on renvoie
    alors None plutôt qu'un zéro trompeur.
    """
    if not isinstance(stats, list):
        return None
    for c in stats:
        author = c.get("author") or {}
        if (author.get("login") or "").lower() != login.lower():
            continue
        weeks = c.get("weeks") or []
        return {"commits": c.get("total", 0),
                "additions": sum(w.get("a", 0) for w in weeks),
                "deletions": sum(w.get("d", 0) for w in weeks)}
    return None


def apply_naming(entries, named):
    """Applique la liste blanche : anonymise sur place tout le reste.

    Un repo public garde toujours son nom, il est déjà visible de tous. Un repo
    privé ne le garde que s'il figure dans `named`, c'est-à-dire s'il peut
    réellement apparaître sur une carte. Les autres deviennent private-001,
    private-002… et perdent description et homepage, qui trahiraient le nom.

    Renvoie la liste triée des noms réels effectivement publiés.
    """
    published, n = [], 0
    for e in entries:
        if not e.get("private") or e["id"] in named:
            published.append(e["id"])
            continue
        n += 1
        e["id"] = "private-%03d" % n
        e.pop("description", None)
        e.pop("homepage", None)
        e.pop("topics", None)
    return sorted(published)
