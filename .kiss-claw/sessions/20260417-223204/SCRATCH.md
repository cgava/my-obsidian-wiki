=== Phase 2 Validation Tests ===
Date: 2026-04-17

Test 1: ./wiki.sh s0 — PASS
  Displays correct vault path and raw dir for s0

Test 2: ./wiki.sh s2 — PASS
  Displays correct vault path and raw dir for s2

Test 3: ./wiki.sh s3 — PASS (expected failure)
  Error: vault directory not found (exit code 1)

Test 4: ./wiki.sh s0 env | grep OBSIDIAN — PASS
  All OBSIDIAN_* variables exported correctly

Files created:
  knlg-repo/.env.s0
  knlg-repo/.env.s2
  knlg-repo/wiki.sh (executable)
  knlg-repo/vault/s0/index.md
  knlg-repo/vault/s0/log.md
  knlg-repo/vault/s0/.manifest.json
  knlg-repo/vault/s0/_meta/taxonomy.md
  knlg-repo/vault/s2/index.md
  knlg-repo/vault/s2/log.md
  knlg-repo/vault/s2/.manifest.json
  knlg-repo/vault/s2/_meta/taxonomy.md

=== Phase 3 — Ingest Isolation Verification Report ===
Date: 2026-04-17

## Step 1: s0 Ingest (llm-patterns.md)
Source: _raw/s0/2026-04/llm-patterns.md (2824 bytes)
Hash: sha256:cc5c5189c54325baf36f1e368ac38616c5c0203e264580fbbdfb8ff829feecd9
Pages updated: 3 (concepts/retrieval-augmented-generation.md, concepts/chain-of-thought.md, concepts/tool-use.md)
Pages created: 0 (pages already existed from prior ingest)
Metadata updated: .manifest.json, index.md, log.md
s2 contamination check: PASS (no files modified in vault/s2 during s0 ingest)

## Step 2: s2 Ingest (pkm-mvp-kickoff.md)
Source: _raw/s2/2026-04/pkm-mvp-kickoff.md (942 bytes)
Hash: sha256:c705b655bd7bff0832a7cbebf1ab9c70a52ffaada0f88ac3e8d538707aa4ef35
Pages created: 3 (concepts/pkm-pipeline.md, concepts/sensitivity-isolation.md, skills/ephemeral-container-workflow.md)
Pages updated: 0
Metadata updated: .manifest.json, index.md, log.md
s0 contamination check: PASS (no new files in vault/s0, no s0 metadata modified during s2 ingest)

## Step 3: Cross-Contamination Verification
- vault/s0 grep for s2 content: PASS (only pre-existing architectural mentions of "S2" concept, no pkm-pipeline/sensitivity-isolation/ephemeral references)
- vault/s2 grep for s0 content: PASS (zero matches for vault/s0, llm-patterns, chain-of-thought, retrieval-augmented, tool-use)
- No s2 wiki page references any s0 wiki page
- No s0 wiki page references any s2 wiki page

VERDICT: Isolation mechanism works correctly. Each zone ingests independently.
## Phase 4 — Maintenance isolée

### wiki-status
- s0: 38 pages totales dans le vault, 1 source ingérée (llm-patterns.md → 3 pages updated). 17 sources raw non-ingérées dans _raw/s0/. Le skill lit correctement $OBSIDIAN_VAULT_PATH et .manifest.json.
- s2: 3 pages dans le vault, 1 source ingérée (pkm-mvp-kickoff.md → 3 pages created). 31 sources raw non-ingérées dans _raw/s2/. Le skill lit correctement les chemins s2.
- Isolation: PASS — chaque exécution ne voit que sa propre zone via $OBSIDIAN_VAULT_PATH.

### wiki-lint
- s0: 4 broken wikilinks trouvés (ADR-004, Architecture du pipeline PKM, Niveaux de sensibilité, wikilinks), 4 orphan pages, 1 page sans frontmatter (concepts/savoir-implicite.md). Le skill a correctement audité uniquement vault/s0/.
- s2: 0 broken links, 0 orphans, 0 frontmatter issues — les 3 pages sont bien formées et mutuellement linkées. Le skill a correctement audité uniquement vault/s2/.
- Isolation: PASS — aucune référence croisée entre zones.

### cross-linker
- s0: Les 3 pages ingérées (RAG, CoT, Tool Use) sont déjà mutuellement cross-linkées. Aucun unlinked mention détecté. Rien à ajouter.
- s2: Les 3 pages (pkm-pipeline, sensitivity-isolation, ephemeral-container-workflow) sont déjà complètement cross-linkées (chacune linke les 2 autres). Rien à ajouter.
- Isolation: PASS — le cross-linker scanne uniquement $OBSIDIAN_VAULT_PATH.

### tag-taxonomy
- s0: 32 tags uniques trouvés (top: llm×6, ai-agents×6, knowledge-management×5). Tous sont "unknown" car taxonomy.md est vide (pas de canonical tags définis). Le skill lit correctement _meta/taxonomy.md dans vault/s0/.
- s2: 14 tags uniques trouvés (pkm, pipeline, security, docker, oauth, etc.). Tous "unknown" pour la même raison. Le skill lit correctement _meta/taxonomy.md dans vault/s2/.
- Isolation: PASS — chaque audit ne voit que les tags de sa propre zone.

### Conclusion
Les 4 skills de maintenance fonctionnent correctement avec le mécanisme de contexte dual-sensitivity :
- Chaque skill utilise $OBSIDIAN_VAULT_PATH pour scoper ses opérations
- L'isolation est totale : aucune donnée ne fuit entre zones
- Les skills read-only (wiki-status, wiki-lint, tag-taxonomy) n'ont rien modifié
- Le cross-linker n'a rien modifié car les pages sont déjà bien linkées
- Seul point d'attention : les taxonomy.md sont vides dans les 2 zones (attendu à ce stade)
## Audit — Adherences ancienne structure

### Resume
- **16 anomalies** trouvees (3 critiques, 9 warnings, 4 info)

---

### Cat 1 : Fichiers orphelins de l'ancienne structure

#### Anomalie 1.1 — .manifest.json a la racine de knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/.manifest.json`
- **Ligne(s)**: 3 (`vault_path: "/home/omc/workspace/my-obsidian-wiki/knlg-repo"`)
- **Description**: Manifest de 478 lignes qui pointe vers `knlg-repo` (pas une zone). Contient des chemins relatifs comme `_raw/llm-patterns.md` et `concepts/retrieval-augmented-generation.md` sans prefixe de zone. Ce manifest a ete cree avant la restructuration dual-zone. Les zones `vault/s0` et `vault/s2` ont chacune leur propre `.manifest.json`. Ce fichier est donc un vestige.
- **Severite**: **CRITIQUE** — Si un skill lit ce manifest par erreur (car il est a la racine du submodule knlg-repo), il obtiendra des chemins invalides. Les chemins `_raw/llm-patterns.md` ne correspondent plus a rien (les fichiers sont maintenant dans `_raw/s0/...`).
- **Propositions**:
  - A) **Supprimer le fichier** — Les vrais manifests sont dans `vault/s0/.manifest.json` et `vault/s2/.manifest.json`. [+] Simple, propre. [-] Perte de l'historique d'ingestion pre-restructuration.
  - B) **Archiver dans `_archives/pre-dual-zone/`** puis supprimer de la racine — [+] Preserve l'historique. [-] Un repertoire archive de plus.
  - C) **Laisser en l'etat mais ajouter un champ `deprecated: true`** — [+] Aucun risque de perte. [-] Toujours visible, risque de confusion.
- **Recommandation**: **B** — Archiver puis supprimer. L'historique pre-restructuration a de la valeur documentaire.

#### Anomalie 1.2 — index.md a la racine de knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/index.md`
- **Ligne(s)**: fichier entier
- **Description**: Master index de l'ancien vault plat. Liste des pages avec des chemins comme `[[concepts/retrieval-augmented-generation|...]]` sans prefixe de zone. Les vrais index sont dans `vault/s0/index.md` et `vault/s2/index.md`.
- **Severite**: **CRITIQUE** — Un skill (wiki-lint, cross-linker, wiki-query) qui lit VAULT_PATH+`/index.md` depuis un context ou VAULT_PATH pointe vers knlg-repo lira cet ancien index avec des liens casses.
- **Propositions**:
  - A) **Supprimer** — Redondant avec les index par zone. [+] Propre. [-] Perte.
  - B) **Transformer en index de navigation dual-zone** — Pointer vers `vault/s0/index.md` et `vault/s2/index.md`. [+] Utile comme point d'entree. [-] A maintenir.
  - C) **Archiver + supprimer** (meme logique que 1.1)
- **Recommandation**: **B** ou **C**. Si on veut un point d'entree a la racine de knlg-repo, B est utile. Sinon, C.

#### Anomalie 1.3 — log.md a la racine de knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/log.md`
- **Ligne(s)**: 7 (`vault_path="/home/omc/workspace/my-obsidian-wiki/knlg-repo/vault"`)
- **Description**: Log de l'ancien vault plat. Contient des refs comme `_raw/llm-patterns.md` sans prefixe de zone. Les vrais logs sont dans `vault/s0/log.md` et `vault/s2/log.md`. Note : la ligne INIT mentionne `knlg-repo/vault` (pas `knlg-repo`), ce qui est un troisieme chemin different des deux zones.
- **Severite**: **warning** — Moins critique que le manifest (les skills lisent le log pour contexte, pas pour routing). Mais genere de la confusion.
- **Propositions**:
  - A) **Archiver + supprimer** — [+] Propre. [-] Perte de l'historique.
  - B) **Transformer en aggregat** qui merge les logs des zones — [+] Vue unifiee. [-] A maintenir.
- **Recommandation**: **A** — Archiver. Un aggregat serait couteux a maintenir.

---

### Cat 2 : Chemins hardcodes vers l'ancienne structure

#### Anomalie 2.1 — .manifest.json : vault_path pointe vers knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/.manifest.json`
- **Ligne(s)**: 3
- **Description**: `"vault_path": "/home/omc/workspace/my-obsidian-wiki/knlg-repo"` — pointe vers la racine, pas vers une zone. Meme anomalie dans les archives : `_archives/2026-04-15T12-00-00Z/.manifest.json` (ligne 3) et `_archives/2026-04-15T12-00-00Z/archive-meta.json` (ligne 7).
- **Severite**: **CRITIQUE** (pour le .manifest.json racine). **info** pour les copies archivees (elles sont figees, c'est attendu).
- **Propositions**: Subsumee par l'anomalie 1.1 — la correction est de supprimer/archiver le manifest racine.

#### Anomalie 2.2 — .manifest.json : chemins sources sans prefixe zone
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/.manifest.json`
- **Ligne(s)**: 10, 26, 41, 54, 170, 186 (cles `_raw/xxx.md`) et 18-19, 34-37, 49-50 (pages_created avec `concepts/xxx.md`)
- **Description**: Les cles source sont `_raw/llm-patterns.md` et les pages sont `concepts/retrieval-augmented-generation.md` — chemins de l'ancien vault plat. Aujourd'hui `_raw/llm-patterns.md` n'existe pas, les sources sont dans `_raw/s0/2026-04/...`.
- **Severite**: Subsumee par 1.1 et 2.1.

#### Anomalie 2.3 — knlg-repo/README.md : reference a `$OBSIDIAN_VAULT_PATH/_raw/`
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/README.md`
- **Ligne(s)**: 187
- **Description**: `Chaque fichier dans $OBSIDIAN_VAULT_PATH/_raw/ est traite comme une source` — dans la structure dual-zone, `_raw/` est separe de `vault/` et organise en `_raw/s0/`, `_raw/s2/`. La variable `OBSIDIAN_RAW_DIR` dans `.env.s0` pointe vers `knlg-repo/_raw/s0`, pas vers `VAULT_PATH/_raw/`. Cette reference est trompeuse.
- **Severite**: **warning**
- **Propositions**:
  - A) **Corriger** le texte pour mentionner `OBSIDIAN_RAW_DIR` au lieu de `$OBSIDIAN_VAULT_PATH/_raw/`.
  - B) **Laisser** car c'est de la documentation du framework (vendor), pas de knlg-repo.
- **Recommandation**: **A** — Le README de knlg-repo est la doc locale, elle doit refleter la realite locale. Corriger en `$OBSIDIAN_RAW_DIR` (qui est la variable configuree dans `.env.sX`).

---

### Cat 3 : Config et environnement

#### Anomalie 3.1 — vendor/obsidian-wiki/setup.sh cree un .env unique
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/vendor/obsidian-wiki/setup.sh`
- **Ligne(s)**: 50-57
- **Description**: Le setup.sh cree un `.env` unique a partir de `.env.example`. Dans le contexte dual-zone de knlg-repo, on utilise `.env.s0` et `.env.s2` via `set-wiki-env.sh`. Le setup.sh n'a pas connaissance du modele dual-zone.
- **Severite**: **warning** — C'est le comportement par defaut du framework (vendor). Le probleme n'est pas dans le framework mais dans le fait que setup.sh n'a pas ete adapte. Cependant, comme on n'utilise PAS setup.sh pour knlg-repo (on utilise set-wiki-env.sh), cela ne bloque rien.
- **Propositions**:
  - A) **Ne rien faire** — setup.sh est dans vendor (upstream), on ne le modifie pas. Le set-wiki-env.sh de knlg-repo prend le relais. [+] Pas de divergence avec upstream. [-] Confusion potentielle.
  - B) **Documenter** dans le README de knlg-repo que `setup.sh` ne doit PAS etre utilise et que `set-wiki-env.sh` le remplace. [+] Clair. [-] Minime.
- **Recommandation**: **B** — Ajouter une note dans le README.

#### Anomalie 3.2 — vendor/obsidian-wiki/setup.sh ecrit ~/.obsidian-wiki/config (mono-vault)
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/vendor/obsidian-wiki/setup.sh`
- **Ligne(s)**: 59-89
- **Description**: Le setup.sh ecrit un seul `OBSIDIAN_VAULT_PATH` dans `~/.obsidian-wiki/config`. Le modele dual-zone necessite deux chemins (un par zone). Si quelqu'un execute setup.sh, la config globale ne supporte qu'une seule zone.
- **Severite**: **warning** — Meme raisonnement que 3.1 : c'est le framework upstream, pas un fichier local. Mais `~/.obsidian-wiki/config` n'existe pas actuellement sur ce systeme (verifie), donc pas de conflit actif.
- **Propositions**: Memes propositions que 3.1.

#### Anomalie 3.3 — ~/.obsidian-wiki/config n'existe pas
- **Fichier**: `~/.obsidian-wiki/config`
- **Description**: Le fichier n'existe pas. Plusieurs skills (wiki-update, wiki-query, wiki-ingest) le cherchent en priorite. Leur fallback est `.env` dans le repo obsidian-wiki. Comme le repo obsidian-wiki n'a pas non plus de `.env` (seulement `.env.example`), ces skills ne trouveront aucune config en mode cross-project.
- **Severite**: **warning** — En pratique, quand on travaille depuis le contexte de knlg-repo, on utilise `set-wiki-env.sh` qui charge directement `.env.sX`. Mais les skills global (wiki-update depuis un autre projet) echoueront car aucune config n'est trouvable.
- **Propositions**:
  - A) **Creer `~/.obsidian-wiki/config`** pointant vers une zone par defaut (ex: s0) — [+] Les skills cross-project fonctionnent. [-] Une seule zone accessible en mode global.
  - B) **Ne rien faire** — les skills cross-project ne sont pas utilises dans le contexte dual-zone. [+] Simple. [-] Les skills globaux restent casses.
  - C) **Creer un wrapper** qui remplace la lecture de `~/.obsidian-wiki/config` par un choix de zone (analog a set-wiki-env.sh). [-] Modification du framework upstream.
- **Recommandation**: **A** — Creer la config globale pointant vers s0 (zone par defaut). C'est le minimum pour que les skills cross-project fonctionnent.

---

### Cat 4 : Assumptions de vault plat dans les skills (vendor)

#### Anomalie 4.1 — wiki-ingest suppose _raw/ a l'interieur de VAULT_PATH
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md`
- **Ligne(s)**: 62, 64
- **Description**: `each file in OBSIDIAN_VAULT_PATH/_raw/` — dans la structure dual-zone, `_raw/` n'est PAS a l'interieur de `vault/s0/` mais dans un repertoire frere (`knlg-repo/_raw/s0/`). La variable `OBSIDIAN_RAW_DIR` est configuree correctement dans `.env.s0` avec un chemin absolu, ce qui contourne le probleme. Cependant, la mention `$OBSIDIAN_VAULT_PATH/_raw/` est un fallback hardcode qui echouerait.
- **Severite**: **warning** — Le fallback `OBSIDIAN_VAULT_PATH/_raw/` ne serait utilise que si `OBSIDIAN_RAW_DIR` est vide. Comme `.env.s0` et `.env.s2` definissent `OBSIDIAN_RAW_DIR` en chemin absolu, le fallback ne s'active pas.
- **Propositions**:
  - A) **Ne rien modifier dans vendor** — le `.env.sX` corrige le probleme. [+] Pas de divergence. [-] Fragile.
  - B) **Documenter dans le README knlg-repo** que `OBSIDIAN_RAW_DIR` est obligatoire (pas optionnel) dans le contexte dual-zone.
- **Recommandation**: **B** — Documenter la contrainte.

#### Anomalie 4.2 — CLAUDE.md/AGENTS.md : structure vault montre _raw/ dans VAULT_PATH
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/vendor/obsidian-wiki/CLAUDE.md` (et identique dans AGENTS.md)
- **Ligne(s)**: 17-33 (CLAUDE.md), 16-32 (AGENTS.md)
- **Description**: Le diagramme de structure vault montre `_raw/` comme sous-repertoire de `$OBSIDIAN_VAULT_PATH/`. En mode dual-zone, `OBSIDIAN_VAULT_PATH=.../vault/s0` et `_raw/` est un frere de `vault/`, pas un sous-repertoire.
- **Severite**: **info** — C'est la doc du framework upstream. Elle est correcte pour le cas d'usage standard (vault plat). Ce n'est pas une anomalie du framework mais une incompatibilite avec l'architecture dual-zone choisie dans knlg-repo. L'agent lit ces fichiers comme reference, ce qui pourrait causer de la confusion.
- **Propositions**:
  - A) **Ne rien modifier** — C'est la doc upstream. [+] Propre. [-] Confusion.
  - B) **Ajouter un CLAUDE.md local** dans knlg-repo qui overrides la structure attendue. [+] Contextualise. [-] A maintenir.
- **Recommandation**: **B** — knlg-repo devrait avoir son propre CLAUDE.md decrivant la structure reelle.

#### Anomalie 4.3 — .env.example : OBSIDIAN_RAW_DIR=_raw (relatif)
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/vendor/obsidian-wiki/.env.example`
- **Ligne(s)**: 53
- **Description**: `OBSIDIAN_RAW_DIR=_raw` — chemin relatif qui sera resolu comme `$OBSIDIAN_VAULT_PATH/_raw`. En dual-zone, `vault/s0/_raw/` n'existe pas ; la raw est dans `knlg-repo/_raw/s0/`. Les `.env.s0`/`.env.s2` utilisent des chemins absolus, donc cet exemple n'est pas utilise.
- **Severite**: **info** — C'est le template upstream. Pas d'impact car les `.env.sX` le surchargent.
- **Propositions**: Aucune action requise dans le contexte knlg-repo.

---

### Cat 5 : Validation dans set-wiki-env.sh

#### Anomalie 5.1 — set-wiki-env.sh valide index.md, log.md, .manifest.json dans VAULT_PATH
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/scripts/set-wiki-env.sh`
- **Ligne(s)**: 104-106
- **Description**: La validation verifie que `$OBSIDIAN_VAULT_PATH/index.md`, `$OBSIDIAN_VAULT_PATH/log.md` et `$OBSIDIAN_VAULT_PATH/.manifest.json` existent. C'est correct : ces fichiers existent bien dans `vault/s0/` et `vault/s2/`. Ce n'est PAS une anomalie.
- **Severite**: *Faux positif* — verification reussie.

---

### Cat 6 : Archives figees avec anciens chemins

#### Anomalie 6.1 — archive-meta.json : vault_path pointe vers knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/_archives/2026-04-15T12-00-00Z/archive-meta.json`
- **Ligne(s)**: 7
- **Description**: `"vault_path": "/home/omc/workspace/my-obsidian-wiki/knlg-repo"` — ancien chemin.
- **Severite**: **info** — Archive figee, ce chemin etait correct au moment de l'archivage. Le skill `wiki-rebuild` utilise ces metadonnees pour la restauration, mais une restauration a partir de cette archive recreerait le vault plat (ce qui est le comportement attendu pour un restore).
- **Propositions**: Aucune action requise. Les archives sont des snapshots historiques.

#### Anomalie 6.2 — guide docs dans _raw/s0 et _archives referencent l'ancien .env
- **Fichier(s)**:
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/_raw/s0/2026-04/guide-obsidian-wiki/00-setup.md` (ligne 97)
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/_archives/2026-04-15T12-00-00Z/guide/00-setup.md` (ligne 97)
- **Description**: `OBSIDIAN_VAULT_PATH=/home/omc/workspace/my-obsidian-wiki/knlg-repo` — documentation du POC pre-dual-zone.
- **Severite**: **info** — Documents de guide/documentation, pas du code executable. Le guide dans `_raw/s0` est une source brute en attente d'ingestion ; l'archive est figee.
- **Propositions**: Aucune action requise. Le guide sera mis a jour lors de la prochaine ingestion ou manuellement.

---

### Cat 7 : .omc/ traces d'etat

#### Anomalie 7.1 — .omc/ presents a plusieurs niveaux
- **Fichier(s)**:
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/.omc/` (contient `state/hud-*.json`)
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/vault/.omc/` (contient `state/hud-*.json`)
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/vault/s0/.omc/`
  - `/home/omc/workspace/my-obsidian-wiki/knlg-repo/vault/s2/.omc/`
- **Description**: Repertoires `.omc/` (etat oh-my-claudecode) presents a 4 niveaux. Ceux a la racine de knlg-repo et de vault/ sont des vestiges de sessions anterieures. Les `.omc/` dans vault/s0 et vault/s2 sont probablement ceux des sessions actuelles.
- **Severite**: **warning** — Les `.omc/` en racine ne causent pas de probleme fonctionnel mais polluent l'arborescence et ne sont pas gitignored dans knlg-repo.
- **Propositions**:
  - A) **Supprimer les .omc/ de knlg-repo/ et vault/** (garder ceux dans s0/ et s2/ si pertinents). [+] Propre. [-] Aucun.
  - B) **Ajouter `.omc/` au .gitignore de knlg-repo** — [+] Prevention. [-] Ne nettoie pas l'existant.
- **Recommandation**: **A + B** — Nettoyer et ajouter au .gitignore.

---

### Cat 8 : Absence de config adapter dual-zone

#### Anomalie 8.1 — Aucun CLAUDE.md local dans knlg-repo
- **Fichier**: `/home/omc/workspace/my-obsidian-wiki/knlg-repo/CLAUDE.md` — N'EXISTE PAS
- **Description**: knlg-repo n'a pas de CLAUDE.md. Quand un agent travaille dans knlg-repo, il lit le CLAUDE.md de vendor/obsidian-wiki (via symlinks ou discovery). Ce CLAUDE.md decrit un vault plat avec `_raw/` dans VAULT_PATH et un seul `.env`. L'agent n'a aucune instruction sur le modele dual-zone, `set-wiki-env.sh`, ou les `.env.sX`.
- **Severite**: **warning** — L'absence de doc locale force l'agent a deviner le modele dual-zone ou a suivre les instructions vault-plat du framework (incorrectes dans ce contexte).
- **Propositions**:
  - A) **Creer un CLAUDE.md dans knlg-repo** decrivant la structure dual-zone, les commandes set-wiki-env.sh, et les contraintes locales.
  - B) **S'appuyer sur le README.md existant** qui decrit deja la structure. [-] Les agents lisent CLAUDE.md en priorite, pas README.md.
- **Recommandation**: **A** — Creer un CLAUDE.md dans knlg-repo.

---

### Conclusion

**Priorisation des corrections :**

1. **P0 (Critique)** — Anomalies 1.1, 1.2, 1.3, 2.1, 2.2 : Archiver et supprimer les fichiers orphelins a la racine de knlg-repo (`.manifest.json`, `index.md`, `log.md`). Ces fichiers contiennent des chemins de l'ancien vault plat et causent un risque de confusion pour les skills.

2. **P1 (Warning)** — Anomalie 8.1 : Creer un CLAUDE.md dans knlg-repo decrivant le modele dual-zone. Sans cela, les agents suivent les instructions vault-plat du framework.

3. **P1 (Warning)** — Anomalie 3.3 : Creer `~/.obsidian-wiki/config` pour que les skills cross-project (wiki-update, wiki-query) fonctionnent.

4. **P2 (Warning)** — Anomalies 4.1, 4.2, 3.1, 3.2 : Documenter dans le README de knlg-repo les contraintes du modele dual-zone vs framework upstream.

5. **P2 (Warning)** — Anomalie 7.1 : Nettoyer les `.omc/` orphelins et les gitignorer.

6. **P3 (Info)** — Anomalies 4.3, 6.1, 6.2 : Aucune action requise. Archives figees et templates upstream.

**Impact global :**
Le code executable (set-wiki-env.sh, .env.s0, .env.s2) est correctement configure pour le dual-zone. Le risque principal est documentaire/contextuel : les agents qui lisent CLAUDE.md, les manifests orphelins ou les anciens logs recevront des informations incorrectes sur la structure du vault. La priorite est de nettoyer les fichiers orphelins et d'ajouter la documentation locale (CLAUDE.md knlg-repo).

# Audit exhaustif vendor/obsidian-wiki — Adherences dual-zone

**Date** : 2026-04-17
**Agent** : kiss-executor
**Fichiers scannes** : 25

---

## SKILLS (16 fichiers)

---

### 1. wiki-ingest/SKILL.md

**Comment resout-il _raw/ ?** Dual : mentionne `OBSIDIAN_VAULT_PATH/_raw/` ET `OBSIDIAN_RAW_DIR` (ligne 62), mais le fallback reste `$OBSIDIAN_VAULT_PATH/_raw/`.
**Comment lit-il la config ?** Via `~/.obsidian-wiki/config` (preferred) ou `.env` (fallback) — ligne 18. OK.
**Touche-t-il des fichiers partages entre zones ?** Oui : `.manifest.json`, `index.md`, `log.md` — tous au vault root.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 18 | `Read ~/.obsidian-wiki/config (preferred) or .env (fallback) to get OBSIDIAN_VAULT_PATH and OBSIDIAN_SOURCES_DIR` | OK | Lit les variables dynamiquement |
| 58-62 | `_raw/ staging directory inside the vault` + `OBSIDIAN_VAULT_PATH/_raw/ (or OBSIDIAN_RAW_DIR)` | **BLOQUANT** | Suppose `_raw/` est dans le vault. En dual-zone, `OBSIDIAN_RAW_DIR` pointe hors du vault (`knlg-repo/_raw/s0`). Le fallback `$OBSIDIAN_VAULT_PATH/_raw/` ecrirait au mauvais endroit. |
| 64 | `verify the resolved path is inside $OBSIDIAN_VAULT_PATH/_raw/` | **BLOQUANT** | Verification de securite hardcodee sur `$OBSIDIAN_VAULT_PATH/_raw/`. En dual-zone, les fichiers raw sont dans `$OBSIDIAN_RAW_DIR` (hors du vault), donc cette verification bloque la suppression des raw apres promotion. |

---

### 2. wiki-ingest/references/ingest-prompts.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** N/A — templates mentaux uniquement.
**Touche-t-il des fichiers partages ?** Non.

**OK — compatible dual-zone.** Pur contenu conceptuel, aucune reference a des chemins.

---

### 3. wiki-status/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas directement.
**Comment lit-il la config ?** Lit `.env` directement (ligne 19).
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `_insights.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 19 | `Read .env to get OBSIDIAN_VAULT_PATH, OBSIDIAN_SOURCES_DIR, CLAUDE_HISTORY_PATH, CODEX_HISTORY_PATH` | **TROMPEUR** | Dit de lire `.env` directement, pas `~/.obsidian-wiki/config` ni les variables deja positionnees. En dual-zone, `.env` n existe pas car on charge `.env.s0` ou `.env.s2` via le wrapper. |

---

### 4. wiki-lint/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 18).
**Touche-t-il des fichiers partages ?** Oui : `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 18 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Meme probleme que wiki-status : dit `.env` au lieu de passer par les variables d environnement ou `~/.obsidian-wiki/config`. |

---

### 5. cross-linker/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 22).
**Touche-t-il des fichiers partages ?** Oui : `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 22 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem — dit `.env`. |

---

### 6. tag-taxonomy/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 20).
**Touche-t-il des fichiers partages ?** Oui : `_meta/taxonomy.md`, `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 20 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |

---

### 7. wiki-query/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Via `~/.obsidian-wiki/config` (preferred), `.env` (fallback) — lignes 18-19. OK.
**Touche-t-il des fichiers partages ?** Oui : `index.md`, `log.md`.

**OK — compatible dual-zone.** La config est lue correctement.

---

### 8. wiki-rebuild/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas directement.
**Comment lit-il la config ?** Lit `.env` directement (ligne 18).
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `index.md`, `log.md`, `_archives/`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 18 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |
| 93 | `Keep: .env (if present in vault)` | **TROMPEUR** | Suppose que `.env` puisse etre dans le vault. En dual-zone, ce n est pas le cas. Pas bloquant mais trompeur. |

---

### 9. wiki-setup/SKILL.md

**Comment resout-il _raw/ ?** Cree `_raw/` dans le vault (ligne 39 : `mkdir -p "$OBSIDIAN_VAULT_PATH"/{...,_raw,...}`).
**Comment lit-il la config ?** Cree `.env` a partir de `.env.example` (lignes 16-17).
**Touche-t-il des fichiers partages ?** Oui : cree `index.md`, `log.md`, `.obsidian/`, structure complete du vault.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 39 | `mkdir -p "$OBSIDIAN_VAULT_PATH"/{concepts,...,_raw,.obsidian}` | **BLOQUANT** | Cree `_raw/` comme sous-repertoire du vault. En dual-zone, `_raw/` est a `knlg-repo/_raw/s0`, hors du vault. Ce setup creerait un `_raw/` inutile dans le vault. |
| 16-17 | `If .env doesn t exist, create it from .env.example` | **TROMPEUR** | En dual-zone, on utilise `.env.s0`/`.env.s2` via le wrapper, pas `.env`. |
| 45 | `_raw/ — Staging area for unprocessed drafts` | **TROMPEUR** | Description suppose `_raw/` dans le vault. |

---

### 10. wiki-update/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Via `~/.obsidian-wiki/config` (lignes 16-19). OK.
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `index.md`, `log.md`.

**OK — compatible dual-zone.** Config lue correctement via `~/.obsidian-wiki/config`.

---

### 11. wiki-export/SKILL.md

**Comment resout-il _raw/ ?** Exclut `_raw/` des exports (ligne 22). Utilise le chemin relatif `_raw/` dans le vault.
**Comment lit-il la config ?** Lit `.env` directement (ligne 18).
**Touche-t-il des fichiers partages ?** Non (genere dans `wiki-export/`).

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 18 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |
| 22 | `excluding _archives/, _raw/, .obsidian/` | OK | Exclusion par nom est correcte meme si `_raw/` n est pas dans le vault (rien a exclure). |

---

### 12. data-ingest/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 18).
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 18 | `Read .env to get OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |

---

### 13. claude-history-ingest/SKILL.md + references/claude-data-format.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 19 du SKILL.md).
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 19 | `Read .env to get OBSIDIAN_VAULT_PATH and CLAUDE_HISTORY_PATH` | **TROMPEUR** | Idem. |

`references/claude-data-format.md` : **OK — compatible dual-zone.** Decrit le format de donnees Claude, aucune reference a des chemins vault.

---

### 14. codex-history-ingest/SKILL.md + references/codex-data-format.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** Lit `.env` directement (ligne 19 du SKILL.md).
**Touche-t-il des fichiers partages ?** Oui : `.manifest.json`, `index.md`, `log.md`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 19 | `Read .env to get OBSIDIAN_VAULT_PATH and CODEX_HISTORY_PATH` | **TROMPEUR** | Idem. |

`references/codex-data-format.md` : **OK — compatible dual-zone.** Decrit le format de donnees Codex, aucune reference a des chemins vault.

---

### 15. wiki-history-ingest/SKILL.md

**Comment resout-il _raw/ ?** Ne l utilise pas.
**Comment lit-il la config ?** N/A — c est un routeur pur, delegue aux skills specifiques.
**Touche-t-il des fichiers partages ?** Non.

**OK — compatible dual-zone.** Pur routeur sans logique propre.

---

### 16. llm-wiki/SKILL.md + references/karpathy-pattern.md

**Comment resout-il _raw/ ?** Mentionne `_raw/` dans la structure du vault (ligne dans AGENTS.md vault structure, reprise dans llm-wiki).
**Comment lit-il la config ?** Mentionne `.env` pour les variables d environnement (ligne 261-267).
**Touche-t-il des fichiers partages ?** Definit les fichiers partages : `index.md`, `log.md`, `.manifest.json`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 20 | `They live wherever the user keeps them (configured via OBSIDIAN_SOURCES_DIR in .env)` | OK | Mentionne `.env` comme source de la variable mais ne dit pas de lire le fichier directement. |
| (structure vault dans AGENTS.md) | `_raw/   # Staging area` dans la structure du vault | **TROMPEUR** | Montre `_raw/` comme sous-dossier du vault. En dual-zone, ce n est pas le cas. |

`references/karpathy-pattern.md` : **OK — compatible dual-zone.** Pur contenu conceptuel.

---

## CONFIG ET DOCS (9 fichiers)

---

### 17. AGENTS.md (= CLAUDE.md = GEMINI.md via symlinks)

**Comment resout-il _raw/ ?** Montre `_raw/` dans la structure du vault.
**Comment lit-il la config ?** Mentionne `~/.obsidian-wiki/config` (preferred) puis `.env` (fallback). OK pour le pattern.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 28 | `_raw/   # Staging area — drop rough notes here, next ingest promotes them` | **TROMPEUR** | Montre `_raw/` dans `$OBSIDIAN_VAULT_PATH/`. En dual-zone, `_raw/` est hors du vault. |

---

### 18. .env (le .env actuel de vendor)

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 10 | `OBSIDIAN_VAULT_PATH=/home/omc/workspace/my-obsidian-wiki/knlg-repo` | **BLOQUANT** | Pointe vers `knlg-repo/` globalement. En dual-zone, il faudrait `knlg-repo/vault/s0` ou `knlg-repo/vault/s2`. Ce chemin ne resout ni l un ni l autre vault. |
| 53 | `OBSIDIAN_RAW_DIR=_raw` | **BLOQUANT** | Chemin relatif. En dual-zone, `OBSIDIAN_RAW_DIR` doit etre un chemin absolu vers `knlg-repo/_raw/s0` ou `knlg-repo/_raw/s2`. Avec un chemin relatif, il sera interprete comme `$OBSIDIAN_VAULT_PATH/_raw` ce qui est le mauvais emplacement. |
| 49 | `A directory inside OBSIDIAN_VAULT_PATH for unprocessed draft pages` | **TROMPEUR** | Le commentaire dit "inside OBSIDIAN_VAULT_PATH". En dual-zone, c est hors du vault. |

---

### 19. .env.example

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 49 | `A directory inside OBSIDIAN_VAULT_PATH for unprocessed draft pages` | **TROMPEUR** | Meme commentaire trompeur que dans `.env`. |
| 53 | `OBSIDIAN_RAW_DIR=_raw` | **TROMPEUR** | Valeur par defaut relative. Pour un setup mono-vault c est OK, mais le commentaire ne mentionne pas qu en dual-zone il faut un chemin absolu. |

---

### 20. setup.sh

**Comment resout-il _raw/ ?** Ne le mentionne pas.
**Comment lit-il la config ?** Cree `.env` a partir de `.env.example` et ecrit `~/.obsidian-wiki/config`.

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 51-57 | Cree `.env` depuis `.env.example` si absent | **TROMPEUR** | En dual-zone, on utilise `.env.s0`/`.env.s2` via wrapper. Le `.env` cree par setup.sh ne serait pas utilise. Pas bloquant car setup.sh ne sera probablement pas relance, mais trompeur. |
| 85-88 | Ecrit `~/.obsidian-wiki/config` avec `OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Ecrit un seul `OBSIDIAN_VAULT_PATH`. En dual-zone, il y en a deux (s0 et s2). La config globale ne peut pointer que vers un seul vault a la fois. |

---

### 21. SETUP.md

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 13-14 | `set OBSIDIAN_VAULT_PATH to your Obsidian vault` + `OBSIDIAN_VAULT_PATH=/path/to/your/vault` | **TROMPEUR** | Suppose un vault unique. |
| 87 | Structure du vault avec `_archives/`, `index.md`, etc. mais pas de `_raw/` mentionne dans la structure | OK | N introduit pas de confusion supplementaire. |
| 95-99 | `projects/my-project/_project.md` | **TROMPEUR** | Montre `_project.md` dans la structure du vault. Les skills eux-memes disent d utiliser `<project-name>.md` a la place. Incoherence interne (pas liee a dual-zone mais notable). |

---

### 22. README.md

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 95-99 | `_project.md` dans la structure du vault | **TROMPEUR** | Meme incoherence que SETUP.md — montre `_project.md` alors que les skills disent `<project-name>.md`. |
| 191 | `_raw/ staging directory. Drop rough notes... Configured via OBSIDIAN_RAW_DIR in .env (defaults to _raw)` | **TROMPEUR** | Correct sur le nom de variable mais suppose un chemin relatif dans le vault. |
| 219-223 | `_raw/ is a staging area inside your vault` | **TROMPEUR** | Dit explicitement "inside your vault". En dual-zone, c est hors du vault. |

---

### 23. .cursor/rules/obsidian-wiki.mdc

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 13 | `Read .env for OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Dit de lire `.env` directement. |

---

### 24. .windsurf/rules/obsidian-wiki.md

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 13 | `Read .env for OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |

---

### 25. .github/copilot-instructions.md

| Ligne | Texte problematique | Classification | Explication |
|-------|---------------------|----------------|-------------|
| 9 | `Key Config: .env contains OBSIDIAN_VAULT_PATH` | **TROMPEUR** | Idem. |

---

## SYNTHESE

### Statistiques

| Classification | Nombre |
|----------------|--------|
| **BLOQUANT** | 4 |
| **TROMPEUR** | 22 |
| **OK** | 6 fichiers entierement OK |

### Adherences BLOQUANTES (4)

1. **wiki-ingest/SKILL.md L62** — `OBSIDIAN_VAULT_PATH/_raw/` comme fallback pour raw mode. En dual-zone, les fichiers raw sont dans `$OBSIDIAN_RAW_DIR` (hors du vault).
2. **wiki-ingest/SKILL.md L64** — Verification de securite hardcodee : `verify the resolved path is inside $OBSIDIAN_VAULT_PATH/_raw/`. Bloque la suppression des raw apres promotion en dual-zone.
3. **vendor .env L10** — `OBSIDIAN_VAULT_PATH=/home/omc/workspace/my-obsidian-wiki/knlg-repo` pointe vers knlg-repo/ globalement au lieu de vault/s0 ou vault/s2.
4. **vendor .env L53** — `OBSIDIAN_RAW_DIR=_raw` est relatif. Doit etre absolu en dual-zone.

### Pattern TROMPEUR recurrent : "Read .env" (12 occurrences)

Les skills suivants disent `Read .env` au lieu de `~/.obsidian-wiki/config` (preferred) ou variables d environnement :
- wiki-status, wiki-lint, cross-linker, tag-taxonomy, wiki-rebuild, wiki-export, data-ingest, claude-history-ingest, codex-history-ingest
- .cursor/rules, .windsurf/rules, .github/copilot-instructions.md

Note : ce n est pas bloquant en soi car dans notre setup, les variables sont deja chargees par le wrapper `set-wiki-env.sh` avant que l agent ne demarre. Mais c est trompeur si un agent essaie de lire `.env` directement alors que seuls `.env.s0`/`.env.s2` existent.

### Pattern TROMPEUR recurrent : "_raw/ dans le vault" (6 occurrences)

AGENTS.md, .env, .env.example, README.md, wiki-setup/SKILL.md, wiki-ingest/SKILL.md — tous montrent ou declarent `_raw/` comme sous-repertoire de `$OBSIDIAN_VAULT_PATH`.

### Fichiers entierement OK (compatible dual-zone)

1. `wiki-ingest/references/ingest-prompts.md`
2. `wiki-query/SKILL.md` — lit `~/.obsidian-wiki/config` correctement
3. `wiki-update/SKILL.md` — lit `~/.obsidian-wiki/config` correctement
4. `wiki-history-ingest/SKILL.md` — pur routeur
5. `llm-wiki/references/karpathy-pattern.md` — conceptuel pur
6. `codex-history-ingest/references/codex-data-format.md` — format de donnees pur
7. `claude-history-ingest/references/claude-data-format.md` — format de donnees pur

### Fichiers partages entre zones

Les fichiers suivants sont au vault root et seraient partages/distincts selon la zone :
- `.manifest.json` — un par vault (s0 et s2 ont chacun le leur) : OK
- `index.md` — idem : OK
- `log.md` — idem : OK
- `_meta/taxonomy.md` — idem : OK
- `_insights.md` — idem : OK

Puisque chaque zone a son propre vault (`vault/s0/`, `vault/s2/`), ces fichiers sont naturellement isoles. Pas d adherence ici.

### Incoherence interne (non liee a dual-zone)

README.md L95-99 et SETUP.md L95-99 montrent `_project.md` dans la structure du vault, mais tous les skills (wiki-update, claude-history-ingest, codex-history-ingest, llm-wiki) disent explicitement d utiliser `<project-name>.md` a la place. Incoherence de documentation.

