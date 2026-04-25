# Analyse d'impact : déplacer `patches/` → `vendor/patches/`

## 1. Faisabilité : OUI, peu invasif

Le moteur Python est déjà **entièrement paramétré** autour d'une variable `patches_dir` passée en argument. Le seul endroit où le chemin `patches/` est *codé en dur relativement à la racine du projet* se trouve dans **2 fichiers** :

| Fichier | Lignes | Nature |
|---|---|---|
| `.claude/skills/patch-system/scripts/patch-system` (shim bash) | 19 (commentaire), 38 (walk-up), 103 (plausibilité) | résolution du root |
| `.claude/skills/patch-system/scripts/patch_system/cli.py` | 86-87 (`_patches_dir`), 703 (help-text) | calcul par défaut |

Tout le reste (`apply.py`, `rollback.py`, `refresh.py`, `detect.py`, `runtime.py`, `verify.py`, `registry.py`) reçoit `patches_dir` en paramètre et fonctionnera sans modification.

## 2. Point crucial : les `.patch` eux-mêmes ne bougent pas sémantiquement

Les chemins cibles dans les `.patch` sont `a/.skills/...`, `a/.env`, `a/.cursor/...` — **relatifs au `cwd` de `git apply`**, qui est `vendor/obsidian-wiki/`. Ce `cwd` ne change pas. **Aucun `.patch` n'a besoin d'être régénéré** et les SHA256 des patches/targets restent identiques. C'est la meilleure garantie de faisabilité.

## 3. Inventaire complet des impacts

### A. Code à modifier (2 fichiers)

**`scripts/patch-system` (bash shim)** :
- L.38 : `if [[ -f "$dir/patches/series.json" ]]` → `if [[ -f "$dir/vendor/patches/series.json" ]]`
- L.103 : sentinelle de plausibilité → `$dir/vendor/patches/series.json`
- L.19, 104 : messages/commentaires.

**`scripts/patch_system/cli.py`** :
- L.86-87 : `_patches_dir()` → `_project_root() / "vendor" / "patches"`
- L.703 (help-text `--series`).

### B. Configuration (1 fichier)
- `.gitignore` L.14 : `patches/.lock` → `vendor/patches/.lock` (critique, sinon le fichier de lock serait commité).

### C. Tests
- **À modifier (1 test E2E)** : `tests/test_b3_runtime_override.py` L.62 — chemin dur `self._proj / "patches" / "series.json"` → `"vendor" / "patches" / "series.json"`.
- **Inchangés** : tous les tests unitaires (`test_cli.py`, `test_apply*.py`, `test_verify.py`, `test_refresh.py`, `test_runtime.py`, `test_detect.py`) créent leur propre `tmp/patches/` comme fixture — indépendant de la layout de prod. À garder tel quel : ils testent le *composant*, pas le chemin racine.

### D. Documentation (mises à jour textuelles)
- `patches/README.md` (maintainer guide — ~10 occurrences)
- `.claude/skills/patch-system/SKILL.md` (5 mentions)
- `.claude/skills/patch-system/references/tutorial.md`, `how-to.md`, `reference.md`, `explanation.md`
- `docs/260420-patch-system-design.md` §2, §3.1 (diagrammes d'arborescence)
- `docs/260420-patch-system-soa.md`
- `docs/adr/ADR-0001-vendor-submodule-pristine.md`, `ADR-0002-registre-runtime-separation.md`

### E. État Git
- Un `git mv patches vendor/patches` préserve l'historique (renommage détecté automatiquement).
- `vendor/obsidian-wiki` est un submodule ; `vendor/patches/` sera **un répertoire normal dans le super-repo** (comme `patches/` actuellement). Pas de nouveau submodule, pas de changement dans `.gitmodules`.

## 4. Points de vigilance / tradeoffs

1. **Sémantique** : placer `patches/` à côté des submodules `vendor/obsidian-wiki` et `vendor/my-claude-minion` peut prêter à confusion — quelqu'un pourrait croire que `vendor/patches/` est un submodule. À atténuer avec un `vendor/patches/README.md` qui rappelle explicitement que c'est un répertoire du super-repo, pas un submodule.

2. **Workflows externes** : si des scripts/hooks (hors repo) font référence à `patches/` depuis le root, ils casseront. J'ai vérifié : rien dans `.omc/`, `.kiss/`, `.kiss-claw/`, pas de hook global ne référence ce chemin.

3. **Variable utilisateur `$PATCH_SYSTEM_ROOT`** : reste au niveau du repo (elle pointe vers le root, pas vers `patches/`). Le mécanisme d'override continue à fonctionner identiquement.

4. **Walk-up resolution** : si un utilisateur lance `patch-system` depuis `vendor/obsidian-wiki/`, le walk-up tombe d'abord sur `vendor/patches/series.json` quand il remonte vers `vendor/` — **comportement correct** (équivalent à avant, puisque le root résolu sera `vendor/patches/../..` = repo root). À tester explicitement.

5. **Option alternative à considérer** : au lieu de coder en dur `vendor/patches`, rendre le chemin configurable via `PATCH_SYSTEM_PATCHES_SUBDIR` (défaut `vendor/patches`). Plus flexible, mais ajoute une surface d'API. **Recommandation : non, coder en dur**. Le skill est couplé à ce repo (il hardcode déjà `vendor/obsidian-wiki` comme vendor-root). Pas de gain à généraliser cette seule variable.

---

# Plan d'action

Proposition en **5 phases** séquentielles, chacune commitable indépendamment pour permettre rollback ciblé.

## Phase 1 — Préparation & validation (sans rien casser)
1. Lancer la suite pytest actuelle depuis `.claude/skills/patch-system/` → baseline verte.
2. Lancer `patch-system verify` + `patch-system status` → snapshot de l'état actuel.
3. Noter les sha256 de tous les `.patch` (ils ne doivent pas changer).

## Phase 2 — Déplacement du dossier
1. `git mv patches vendor/patches` (préserve l'historique).
2. Mettre à jour `.gitignore` : `patches/.lock` → `vendor/patches/.lock`.
3. **Ne rien commiter encore** — le CLI est cassé à ce stade (il cherche `patches/` au root).

## Phase 3 — Adaptation du code (2 fichiers)
1. `scripts/patch_system/cli.py` L.87 : `"patches"` → `"vendor/patches"` (via `_project_root() / "vendor" / "patches"`), plus help-text L.703.
2. `scripts/patch-system` L.38 & L.103 : sentinelle `patches/series.json` → `vendor/patches/series.json`, + mise à jour des commentaires L.19, L.104.
3. `tests/test_b3_runtime_override.py` L.62 : chemin de `series.json`.

## Phase 4 — Validation fonctionnelle
1. `python -m pytest tests/` → doit passer (y compris `test_b3_runtime_override`).
2. `patch-system verify --strict` depuis le root → exit 0.
3. `patch-system status` → identique au snapshot Phase 1.
4. `patch-system apply b3-vendor-env-remove --dry-run` → exit 0 (vérifie que le runtime.json override se résout toujours).
5. Walk-up resolution : `cd vendor/obsidian-wiki && ../../.claude/skills/patch-system/scripts/patch-system status` → doit trouver le root via le nouveau sentinel.
6. **Commit** phases 2+3+4 ensemble (un commit "chore(patch-system): move patches/ under vendor/").

## Phase 5 — Documentation (commit séparé)
1. `patches/README.md` → déplacé en `vendor/patches/README.md` (déjà fait par git mv). Mettre à jour tous les chemins mentionnés dans le texte + ajouter note "ceci n'est pas un submodule".
2. `SKILL.md`, `references/*.md` : mettre à jour tous les chemins littéraux.
3. Docs design + ADR : ajouter une note "Historique : le dossier a été déplacé de `patches/` à `vendor/patches/` le 2026-04-22 (voir commit XXXX)". Ne pas réécrire en masse l'arborescence de référence : préserver la trace historique.
4. **Commit** "doc(patch-system): update paths after patches/ relocation".

## Phase 6 — Rollback plan (au cas où)
Si casse en prod :
- `git revert` des deux commits suffit (git mv est réversible via revert).
- Le `.lock` éventuellement créé à `vendor/patches/.lock` peut rester — inoffensif.

---

# Recommandation

**Foncer.** L'impact est très limité (2 fichiers de code, 1 fichier de test, 1 `.gitignore`), la garantie de stabilité des patches est forte (les SHA ne bougent pas), et le git mv préserve l'historique. Phase 5 (doc) peut suivre dans un second temps sans bloquer l'usage.
