# Analyse dual-sensitivity obsidian-wiki (s0/s2)

**Date** : 2026-04-18
**Session kiss-claw** : 20260417-223204
**Statut** : Phase 4 complete, audit exhaustif termine

---

## 1. Objectif

Adapter obsidian-wiki pour fonctionner en dual-zone de sensibilite :
- **s0** (public / non-sensible) : traitable par un LLM cloud
- **s2** (prive / sensible) : traitable par un LLM souverain/local

**Pourquoi** : compliance et separation public/prive. A terme, deux chaines LLM distinctes traiteront les donnees selon leur sensibilite.

**Contraintes** :
- Mecanisme deterministe (pas de logique dans les skills)
- Cross-linking asymetrique : s2 peut referencer s0, jamais l'inverse
- Isolation complete : chaque zone a ses propres index.md, log.md, .manifest.json

---

## 2. Evaluation des solutions

### 2.1 Mecanismes evalues

| # | Mecanisme | Difficulte | Avantages | Inconvenients |
|---|-----------|-----------|-----------|---------------|
| 1 | **Multi-.env** (.env.s0, .env.s2) | Faible | Simple, auto-documente, un fichier par zone | Variables communes dupliquees, risque d'oubli de source |
| 2 | **Wrapper script** | Faible | Deterministe, centralise, validant | Couche indirecte |
| 3 | **Profils dans un seul .env** | Moyenne | DRY | Format non standard, parser custom requis |
| 4 | **Config globale avec profils** | Moyenne | Cross-projet | N'existe pas encore, format a definir |
| 5 | **Symlinks dynamiques** | Faible | Transparent pour les skills | Fragile, etat global mutable, pas multi-agent safe |
| 6 | **Variable SENSITIVITY_LEVEL** | Moyenne | Explicite | Modif de tous les skills |
| 7 | **Parametre de zone dans les skills** | Moyenne-Haute | Self-documenting | Modif de tous les skills, fork upstream |
| 8 | **Agent-level routing** | Faible | Zero modif | Pas de validation automatique |
| 9 | **Override env vars par appel** | Faible | Zero modif skills, deterministe | Verbose, pas de validation |
| 10 | **Vault composite** | Faible | Un seul index, cross-linking naturel | Complexe a segreger |

### 2.2 Analyse des chemins par skill

**Constat cle** : tous les skills resolvent tous leurs chemins relativement a `OBSIDIAN_VAULT_PATH`. C'est la seule variable pivot. Deux overrides suffisent par zone : `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_RAW_DIR`.

| Skill | Variables lues | Source config | Fichiers partages touches |
|-------|---------------|---------------|---------------------------|
| wiki-ingest | VAULT_PATH, RAW_DIR, SOURCES_DIR, QMD_* | ~/.obsidian-wiki/config > .env | .manifest.json, index.md, log.md |
| wiki-status | VAULT_PATH, SOURCES_DIR, HISTORY_PATH | .env | .manifest.json, _insights.md, log.md |
| wiki-lint | VAULT_PATH | .env | index.md, log.md |
| cross-linker | VAULT_PATH | .env | index.md, log.md |
| tag-taxonomy | VAULT_PATH | .env | _meta/taxonomy.md, index.md, log.md |
| wiki-query | VAULT_PATH, QMD_* | ~/.obsidian-wiki/config > .env | index.md |
| wiki-rebuild | VAULT_PATH | .env | .manifest.json, index.md, log.md |
| wiki-setup | VAULT_PATH, SOURCES_DIR | .env (cree) | Cree toute la structure |
| wiki-update | VAULT_PATH, WIKI_REPO | ~/.obsidian-wiki/config | .manifest.json, index.md, log.md |
| wiki-export | VAULT_PATH | .env | Aucun (genere dans wiki-export/) |
| data-ingest | VAULT_PATH | .env | .manifest.json, index.md, log.md |
| claude-history-ingest | VAULT_PATH, HISTORY_PATH | .env | .manifest.json, index.md, log.md |
| codex-history-ingest | VAULT_PATH, HISTORY_PATH | .env | .manifest.json, index.md, log.md |
| wiki-history-ingest | N/A | N/A (routeur) | Aucun |
| llm-wiki | VAULT_PATH, SOURCES_DIR, CATEGORIES | .env | Reference/documentation |

### 2.3 Matrice de comparaison des 3 finalistes

| Critere | Multi-.env (#1) | Wrapper (#2) | Override env (#9) |
|---------|:-:|:-:|:-:|
| Simplicite implementation | 4 | 4 | 5 |
| Determinisme | 4 | **5** | 3 |
| Robustesse multi-agent | **5** | **5** | 4 |
| Ergonomie d'usage | 3 | **4** | 3 |
| Maintenabilite | 4 | **5** | 3 |
| Compatibilite upstream | **5** | **5** | **5** |
| Support cross-linking | 3 | 3 | 2 |
| **TOTAL** | **28** | **31** | **25** |

### 2.4 Solution retenue

**Wrapper script (#2) + Multi-.env (#1) en combinaison**

- Le wrapper obtient le meilleur score (31/35)
- La combinaison avec multi-.env apporte la source de verite declarative
- Zero modification des skills upstream
- 3 fichiers a creer : `.env.s0`, `.env.s2`, `scripts/set-wiki-env.sh`

---

## 3. Implementation

### 3.1 Fichiers crees

```
knlg-repo/
  .env.s0                    # OBSIDIAN_VAULT_PATH=.../vault/s0, OBSIDIAN_RAW_DIR=.../_raw/s0
  .env.s2                    # OBSIDIAN_VAULT_PATH=.../vault/s2, OBSIDIAN_RAW_DIR=.../_raw/s2
  scripts/set-wiki-env.sh    # Wrapper : charge le bon .env, valide, execute
  vault/s0/                  # index.md, log.md, .manifest.json, _meta/taxonomy.md
  vault/s2/                  # idem
```

### 3.2 set-wiki-env.sh — Fonctionnalites

- **3 modes** : info (affiche config), env (exporte pour sourcing), command (execute dans l'env)
- **Validation** : VAULT_PATH, RAW_DIR, CATEGORIES (variables + repertoires + fichiers de base)
- **Overrides CLI** : `--vault`, `--raw`, `--categories`, `--env`, `--no-validate`
- **Aide** : `-h` / `--help`
- **Robustesse** : `set -euo pipefail`, couleurs TTY-aware, stderr pour erreurs, codes de sortie significatifs

### 3.3 Usage

```bash
./scripts/set-wiki-env.sh s0              # Affiche la config s0
./scripts/set-wiki-env.sh s2              # Affiche la config s2
source <(./scripts/set-wiki-env.sh s0 env) # Charge s0 dans le shell
./scripts/set-wiki-env.sh s0 make ingest  # Execute commande dans l'env s0
./scripts/set-wiki-env.sh s0 --vault /alt # Override vault path
```

---

## 4. Validation

### 4.1 Phase 3 — Ingest isole

| Zone | Source | Pages | Isolation |
|------|--------|-------|-----------|
| s0 | `_raw/s0/2026-04/llm-patterns.md` | 3 pages mises a jour (RAG, CoT, Tool Use) | PASS |
| s2 | `_raw/s2/2026-04/pkm-mvp-kickoff.md` | 3 pages creees (pkm-pipeline, sensitivity-isolation, ephemeral-container-workflow) | PASS |

**Verification cross-contamination** :
- vault/s0 grep pour contenu s2 : PASS (zero references pkm-pipeline, sensitivity-isolation)
- vault/s2 grep pour contenu s0 : PASS (zero references vault/s0, llm-patterns, chain-of-thought)
- Aucune page s0 ne reference une page s2 et vice versa

**Verdict** : mecanisme d'isolation fonctionne correctement.

### 4.2 Phase 4 — Maintenance isolee

| Skill | s0 | s2 | Isolation |
|-------|----|----|-----------|
| wiki-status | 38 pages, 17 raw pending | 3 pages, 31 raw pending | PASS |
| wiki-lint | 4 broken links, 4 orphans, 1 sans frontmatter | Clean (0 issues) | PASS |
| cross-linker | Rien a ajouter (deja linke) | Rien a ajouter | PASS |
| tag-taxonomy | 32 tags (non normalises, taxonomy vide) | 14 tags | PASS |

**8 runs, 0 fuites cross-zone.** Tous les skills de maintenance fonctionnent avec le mecanisme de contexte.

---

## 5. Audit exhaustif — Adherences ancienne structure

### 5.1 Synthese

**25 fichiers scannes dans vendor/obsidian-wiki + knlg-repo**

| Classification | Nombre | Description |
|----------------|--------|-------------|
| BLOQUANT | 4 | Le skill echouera ou ecrira au mauvais endroit |
| TROMPEUR | 22 | Le skill fonctionne mais la doc/instruction est inexacte |
| OK | 7 fichiers | Entierement compatible dual-zone |

### 5.2 Anomalies BLOQUANTES

#### B1 — wiki-ingest fallback `$VAULT_PATH/_raw/`
- **Fichier** : `vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md` ligne 62
- **Probleme** : le raw mode utilise `OBSIDIAN_VAULT_PATH/_raw/ (or OBSIDIAN_RAW_DIR)` comme fallback. En dual-zone, `_raw/` est hors du vault — le fallback pointerait vers `vault/s0/_raw/` qui n'existe pas.
- **Impact** : si `OBSIDIAN_RAW_DIR` n'est pas defini, le skill lit le mauvais repertoire.
- **Mitigation actuelle** : `.env.s0`/`.env.s2` definissent `OBSIDIAN_RAW_DIR` en absolu, donc le fallback ne s'active pas.
- **Propositions** :
  - A) **Modifier wiki-ingest/SKILL.md** : remplacer le fallback par `$OBSIDIAN_RAW_DIR` uniquement. [+] Robuste. [-] Fork vendor.
  - B) **Documenter dans CLAUDE.md local** que `OBSIDIAN_RAW_DIR` est obligatoire. [+] Zero modif vendor. [-] Fragile.
  - **Recommandation** : A (modifier vendor) — c'est un bug de robustesse du skill.

#### B2 — wiki-ingest verification securite hardcodee
- **Fichier** : `vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md` ligne 64
- **Probleme** : `verify the resolved path is inside $OBSIDIAN_VAULT_PATH/_raw/` — en dual-zone, les raw sont dans `$OBSIDIAN_RAW_DIR` (hors du vault), donc cette verification bloquerait la suppression apres promotion.
- **Propositions** :
  - A) **Modifier** : remplacer par `verify the resolved path is inside $OBSIDIAN_RAW_DIR`. [+] Correct. [-] Fork vendor.
  - B) **Ne pas supprimer les raw** en dual-zone (contournement). [+] Zero modif. [-] Accumulation de fichiers.
  - **Recommandation** : A — la verification doit suivre la configuration.

#### B3 — vendor/.env pointe vers knlg-repo/
- **Fichier** : `vendor/obsidian-wiki/.env` ligne 10
- **Probleme** : `OBSIDIAN_VAULT_PATH=/home/omc/workspace/my-obsidian-wiki/knlg-repo` — pointe vers la racine, pas vers une zone (vault/s0 ou vault/s2).
- **Impact** : si un skill lit ce `.env` en fallback (quand les variables ne sont pas pre-chargees), il travaillera dans le mauvais perimetre.
- **Propositions** :
  - A) **Supprimer vendor/.env** et ne garder que .env.s0/.env.s2 dans knlg-repo. [+] Elimine le piege. [-] Casse le fallback des skills.
  - B) **Modifier vendor/.env** pour pointer vers vault/s0 (zone par defaut). [+] Fallback safe. [-] Une seule zone.
  - C) **Renommer en .env.legacy** pour eviter la lecture automatique. [+] Preservatif. [-] A documenter.
  - **Recommandation** : A — le wrapper set-wiki-env.sh est le point d'entree, vendor/.env est un vestige.

#### B4 — vendor/.env OBSIDIAN_RAW_DIR relatif
- **Fichier** : `vendor/obsidian-wiki/.env` ligne 53
- **Probleme** : `OBSIDIAN_RAW_DIR=_raw` — chemin relatif interprete comme `$VAULT_PATH/_raw`. En dual-zone, doit etre absolu.
- **Impact** : subsume par B3 — si vendor/.env est supprime, B4 disparait.

### 5.3 Pattern TROMPEUR recurrent : "Read .env" (12 occurrences)

Les skills suivants disent `Read .env to get OBSIDIAN_VAULT_PATH` :

| Skill | Ligne |
|-------|-------|
| wiki-status | 19 |
| wiki-lint | 18 |
| cross-linker | 22 |
| tag-taxonomy | 20 |
| wiki-rebuild | 18 |
| wiki-export | 18 |
| data-ingest | 18 |
| claude-history-ingest | 19 |
| codex-history-ingest | 19 |
| .cursor/rules/obsidian-wiki.mdc | 13 |
| .windsurf/rules/obsidian-wiki.md | 13 |
| .github/copilot-instructions.md | 9 |

**Impact** : pas bloquant si les variables sont pre-chargees par set-wiki-env.sh. Mais un agent qui suit le skill a la lettre tentera de lire `.env` qui est soit absent soit pointe vers la mauvaise zone.

**Propositions** :
- A) **Modifier chaque skill** : remplacer `Read .env` par `Read ~/.obsidian-wiki/config (preferred) or .env (fallback)`. [+] Coherent avec wiki-ingest/wiki-query/wiki-update qui le font deja. [-] 12 fichiers a modifier, fork vendor.
- B) **Creer un CLAUDE.md local** dans knlg-repo qui override l'instruction. [+] Zero modif vendor. [-] Les skills disent toujours `.env`.
- **Recommandation** : B pour l'instant — le CLAUDE.md local est la correction la plus pragmatique.

### 5.4 Pattern TROMPEUR recurrent : "_raw/ dans le vault" (6 occurrences)

| Fichier | Ligne | Texte |
|---------|-------|-------|
| AGENTS.md (=CLAUDE.md=GEMINI.md) | 28 | `_raw/ # Staging area` dans structure vault |
| vendor/.env | 49 | `A directory inside OBSIDIAN_VAULT_PATH` |
| .env.example | 49 | Idem |
| README.md | 219-223 | `_raw/ is a staging area inside your vault` |
| wiki-setup/SKILL.md | 39 | `mkdir -p "$VAULT_PATH"/{...,_raw,...}` |
| wiki-ingest/SKILL.md | 58-62 | `_raw/ staging directory inside the vault` |

**Impact** : doc/instructions trompeuses en dual-zone. Pas bloquant si `OBSIDIAN_RAW_DIR` est correctement configure.

### 5.5 Autres anomalies (knlg-repo)

#### Fichiers orphelins a la racine de knlg-repo (P0 critique)

| Fichier | Probleme | Recommandation |
|---------|----------|----------------|
| `knlg-repo/.manifest.json` | Manifest ancien vault plat, chemins invalides | Archiver dans `_archives/pre-dual-zone/` puis supprimer |
| `knlg-repo/index.md` | Index ancien vault plat, liens sans prefixe zone | Idem |
| `knlg-repo/log.md` | Log ancien vault plat | Idem |

#### Absence de CLAUDE.md dans knlg-repo (P1)
- Aucun CLAUDE.md local. Les agents lisent celui de vendor/ (vault plat).
- **Recommandation** : creer `knlg-repo/CLAUDE.md` decrivant la structure dual-zone et l'usage de set-wiki-env.sh.

#### ~/.obsidian-wiki/config n'existe pas (P1)
- Les skills cross-projet (wiki-update, wiki-query) ne trouvent aucune config.
- **Recommandation** : creer avec zone par defaut s0.

#### .omc/ orphelins a 4 niveaux (P2)
- `.omc/` dans knlg-repo/, vault/, vault/s0/, vault/s2/
- **Recommandation** : nettoyer les vestiges racine, ajouter `.omc/` au .gitignore.

### 5.6 Fichiers entierement compatibles (OK)

- `wiki-query/SKILL.md` — lit `~/.obsidian-wiki/config` correctement
- `wiki-update/SKILL.md` — lit `~/.obsidian-wiki/config` correctement
- `wiki-history-ingest/SKILL.md` — pur routeur, pas de logique propre
- `wiki-ingest/references/ingest-prompts.md` — contenu conceptuel pur
- `llm-wiki/references/karpathy-pattern.md` — contenu conceptuel pur
- `claude-history-ingest/references/claude-data-format.md` — format de donnees pur
- `codex-history-ingest/references/codex-data-format.md` — format de donnees pur

---

## 6. Priorisation des corrections

| Priorite | Anomalies | Action |
|----------|-----------|--------|
| **P0** | B3, B4, orphelins racine | Supprimer vendor/.env, archiver .manifest.json/index.md/log.md racine |
| **P1** | B1, B2 | Corriger wiki-ingest/SKILL.md (fallback + verif securite) |
| **P1** | CLAUDE.md absent | Creer CLAUDE.md dans knlg-repo |
| **P1** | ~/.obsidian-wiki/config | Creer config globale (zone par defaut s0) |
| **P2** | 12x "Read .env" | Contourner via CLAUDE.md local |
| **P2** | 6x "_raw/ dans vault" | Documenter la difference dans CLAUDE.md local |
| **P2** | .omc/ orphelins | Nettoyer + .gitignore |
| **P3** | Archives figees | Aucune action (snapshots historiques) |

---

## 7. Phases restantes

### Phase 5 — Cross-linking asymetrique
- Implementer le mecanisme s2 → s0 (vault/s2 peut referencer vault/s0)
- Bloquer s0 → s2 (vault/s0 ne peut jamais referencer vault/s2)
- Potentiel : mode `./scripts/set-wiki-env.sh cross-link s2 s0`

### Phase 6 — Validation POC
- Demontrer les 2 chaines independantes
- Documenter le mecanisme final
