# Design architecture — patch-system pour vendor/obsidian-wiki

**Date** : 2026-04-20
**Session kiss-claw** : 20260420-104751
**Phase** : 2 — Design
**Statut** : Accepted (inputs pour Phase 3 Implementation)
**Reference amont** : `docs/260420-patch-system-soa.md` (Phase 1, etat de l'art)

---

## 1. Contexte et cadrage

Ce document traduit la recommandation §4 de l'etat de l'art
`docs/260420-patch-system-soa.md` en design actionnable pour la Phase 3. Le but
est un systeme de patches locaux applique a `vendor/obsidian-wiki` (skills
bash/markdown trackes via un remote Git upstream non-forkable) qui traite les
4 anomalies bloquantes B1-B4, les ~18 occurrences trompeuses (p2-read-dotenv,
p2-raw-in-vault), et qui survit aux `git pull` upstream. Contraintes de stack
projet rappelees : bash + Python stdlib + JSON par defaut ; pip propre OK si
optionnel ; exotique (apt install d'un outil additionnel, runtime Go/Java) =
confirmation prealable. Le design reste strictement dans ce perimetre.

Le design s'appuie sur les briques retenues en §3 du SOA :
- **DEP-3** (enrichi) pour les metadonnees du patch (§2.1 SOA).
- **etc-update** (Gentoo) pour l'UX menu-par-conflit (§2.3 SOA).
- **Ansible `check_mode` + `--diff`** pour le modele d'idempotence (§2.6 SOA).
- **`git apply --check` + sha256** pour la detection tri-valuee (§2.7 SOA).
- **Quilt-like layout `patches/` + series** sans le binaire `quilt` (§2.1/§4.3
  SOA).

---

## 2. Architecture logique

### 2.1 Composants

Le patch-system est organise en six composants logiques. Les cinq premiers
sont internes (code Python stdlib), le sixieme est un service externe
(lecture du working tree vendor + invocation `git apply`/`patch`).

```
+------------------------------------------------------------+
|                    CLI dispatcher (bash)                   |
|         scripts/patch-system {status|apply|...}            |
+---------------------------+--------------------------------+
                            |
                            v
+------------------------------------------------------------+
|                   Python package patch_system              |
|                                                            |
|  +----------+   +----------+   +-----------+  +---------+  |
|  | Registre |-->| Moteur   |-->| Moteur    |->| Moteur  |  |
|  | (series) |   | detection|   | apply     |  | rollback|  |
|  +----------+   +----------+   +-----------+  +---------+  |
|       ^              |                |            |      |
|       |              v                v            v      |
|       |         +-----------------------------+           |
|       +---------| Couche UI/interactive (ui.py)|           |
|                 +-----------------------------+           |
|                              |                            |
|                              v                            |
|                 +-----------------------------+           |
|                 | Detection drift vendor      |           |
|                 | (git-rev comparison)        |           |
|                 +-----------------------------+           |
+------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------+
|          Services externes : git, patch, sha256           |
|                 (vendor/obsidian-wiki working tree)        |
+------------------------------------------------------------+
```

### 2.2 Responsabilites par composant

| Composant | Fichier | Role | Interdits |
|---|---|---|---|
| **CLI dispatcher** | `scripts/patch-system` (bash, 30-50 lignes) | Parse l'argv de surface, exporte `PATCH_SYSTEM_ROOT`, delegue a `python3 -m patch_system`. Pas de logique metier. | Pas de parsing de patch, pas de lecture series.json. |
| **Registre** | `scripts/patch_system/registry.py` | Load/save `series.json` (registre logique). Resolution `id -> record`. Validation de schema (champs obligatoires, types). Garant de l'immutabilite lexicographique en ecriture (clefs stables). | Pas d'appel a `git apply`. Pas d'IO reseau. |
| **Moteur detection** | `scripts/patch_system/detect.py` | Implemente la strategie composite sha256 + `git apply --check` + `--check --reverse` + `--3way`. Retourne un `TargetState` (`clean`/`patched`/`partial`/`dirty`/`absent`/`unknown`) par target. | Ne modifie rien. Tout appel git est via `--check`. |
| **Moteur apply** | `scripts/patch_system/apply.py` | Applique un patch via `git apply` (primaire) ou `patch(1)` (fallback). Met a jour `last_applied`, `last_result`, `history` dans series.json via le registre. | Ne decide pas de la strategie de detection. |
| **Moteur rollback** | `scripts/patch_system/rollback.py` | `git apply --reverse` + mise a jour registre. Refuse le rollback si `last_result != patched`. | Pas d'effacement de fichiers hors du perimetre patch. |
| **Couche UI** | `scripts/patch_system/ui.py` | Formatting TTY (tableau status), prompts interactifs, gestion couleurs/bold si TTY. Mode non-interactif strict si `!sys.stdout.isatty()`. | Pas de logique d'application. |
| **Detection drift vendor** | `scripts/patch_system/drift.py` | Compare le SHA courant du submodule vendor au `vendor_baseline_sha` enregistre dans `series.json` ; signale les records dont la baseline target peut etre obsolete. | Pas d'auto-refresh. Juste un signal pour `verify`/`status`. |

### 2.3 Flux de donnees principaux

**Flux `status`** :
```
CLI -> registry.load() -> for record in records:
         detect.evaluate(record) -> {target: state}
       -> ui.render_table(states)
```

**Flux `apply <id>`** :
```
CLI -> registry.get(id) -> detect.evaluate(record)
       if state == clean     -> apply.run(record) -> registry.update_history
       if state == patched   -> skip (idempotent)
       if state == partial   -> ui.interactive_menu() -> apply/skip/3way/refresh
       if state == dirty     -> ui.interactive_menu() or fail in --yes mode
       if state == absent    -> skip + warn
```

**Flux `apply --all --interactive`** : itere la serie dans l'ordre `order`
croissant, applique la logique ci-dessus par record, avec possibilite de
`quit` qui arrete proprement (les records deja appliques ne sont pas rolles
back).

**Flux `verify`** : pour chaque record, recalcule `patch_sha256` du
`.patch` sur disque, compare a la valeur enregistree ; detecte drift vendor ;
reporte.

---

## 3. Schema de storage

### 3.1 Layout fichiers — decision

**Layout retenu : quilt-like file-per-patch + registre JSON separe.**
Arbitrage detaille en §5.8 ; resume ici :

```
patches/
  series.json                                # registre logique ordonne
  runtime.json                               # config d'execution par patch
  .lock                                      # flock pour concurrence (§5.7)
  0001-wiki-ingest-raw-fallback.patch        # diff unifie + header DEP-3
  0002-wiki-ingest-security-check.patch
  0003-vendor-env-remove.patch
  0004-vendor-env-subsumed.patch
  0005-read-dotenv-wording.patch             # p2 — 12 targets (voir §5.1)
  0006-raw-in-vault-wording.patch            # p2 — 6 targets (voir §5.1)
  ...
  history/                                   # audit trail (decharge de series.json)
    0001-history.jsonl                       # 1 record d'historique par ligne
    0002-history.jsonl
    ...
  archive/                                   # patches retires (status obsolete)
    ...
```

Le choix **file-per-patch** (vs registre unique monolithique) repose sur 3
raisons deja exposees en §4.1 du SOA :

1. **Review-friendly** : un patch = un fichier ; diff git lisible.
2. **Discover-friendly** : `ls patches/` inventorie.
3. **Forwardable upstream** : le `.patch` avec son header DEP-3 est
   auto-suffisant — copier-coller dans un bug tracker/mailing list.

La separation **series.json (registre logique)** vs **runtime.json (config
d'execution)** tranche le point ouvert 8 (voir §5.8).

### 3.2 Schema d'un anomaly record — series.json

Un `series.json` est une liste ordonnee de **records registre logique** :

```json
{
  "schema_version": "1",
  "vendor_baseline_sha": "abc123def4567890...",
  "records": [
    {
      "id": "b1-wiki-ingest-raw-fallback",
      "order": 1,
      "status": "active",
      "severity": "BLOCKING",
      "title": "wiki-ingest — replace _raw/ fallback by OBSIDIAN_RAW_DIR",
      "audit_ref": "docs/260418-dual-sensitivity-analysis.md#b1",
      "patch_file": "0001-wiki-ingest-raw-fallback.patch",
      "patch_sha256": "a3f2...1c",
      "targets": [
        {
          "path": "vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md",
          "baseline_sha256": "3f4a...c8",
          "patched_sha256": "9bd1...ee"
        }
      ],
      "last_applied": "2026-04-20T10:52:13Z",
      "last_result": "patched"
    }
  ]
}
```

**Champs obligatoires** : `id`, `order`, `status`, `severity`, `title`,
`patch_file`, `patch_sha256`, `targets[]`. Chaque entree de `targets[]` doit
contenir `path` + `baseline_sha256` + `patched_sha256`.

**Champs optionnels** : `audit_ref` (trace vers l'audit dual-sensitivity),
`last_applied`, `last_result`, `notes`. L'historique complet (ancien champ
`history[]` du SOA §4.4) est externalise dans `patches/history/<order>-history.jsonl`
pour eviter le gonflement du registre (ajout/an d'audit = lignes a plat, pas
de serialisation JSON a reecrire integralement). Chaque ligne JSONL est un
evenement typique :

```json
{"ts":"2026-04-20T10:52:13Z","action":"apply","result":"patched","operator":"auto","commit":null}
```

**Types attendus** :
- `id` : string kebab-case, prefixe `<code-audit>-<slug>` (ex. `b1-*`, `p2-*`).
- `order` : integer > 0, unique dans la serie, pas forcement contigu.
- `status` : enum `active | disabled | obsolete` (cf. SOA §4.4).
- `severity` : enum `BLOCKING | TROMPEUR | COSMETIQUE | INFO`.
- `patch_sha256` / `baseline_sha256` / `patched_sha256` : string hex 64 chars.
- `last_result` : enum `clean | patched | partial | dirty | absent | unknown`.

**Exemple multi-targets** (record p2-read-dotenv, voir §5.1) :

```json
{
  "id": "p2-read-dotenv-wording",
  "order": 5,
  "status": "active",
  "severity": "TROMPEUR",
  "title": "Wording 'Read .env' → 'Read config' across 12 skill docs",
  "patch_file": "0005-read-dotenv-wording.patch",
  "patch_sha256": "cf9a...12",
  "targets": [
    {"path": "vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md",
     "baseline_sha256": "...", "patched_sha256": "..."},
    {"path": "vendor/obsidian-wiki/.skills/wiki-status/SKILL.md",
     "baseline_sha256": "...", "patched_sha256": "..."}
  ]
}
```

### 3.3 Schema runtime.json — separation explicite

`runtime.json` contient la **strategie d'execution** par patch. Elle est
lue par les moteurs `detect`/`apply`/`rollback` ; elle n'impacte pas
l'identite du patch. Separer permet de changer la strategie sans toucher le
registre logique (donc sans faire un "vrai" changement de patch) :

```json
{
  "schema_version": "1",
  "defaults": {
    "detection": {"strategy": "composite", "signals": ["checksum", "git-apply-reverse-check"]},
    "apply":    {"method": "git-apply", "args": ["--index", "--whitespace=nowarn"]},
    "rollback": {"method": "git-apply", "args": ["--reverse", "--index"]},
    "drift":    {"mode": "verbose"}
  },
  "overrides": {
    "b1-wiki-ingest-raw-fallback": {
      "apply": {"method": "patch", "args": ["-p1", "-N"]}
    }
  }
}
```

Lecture : chaque moteur applique `defaults` puis fusionne `overrides[id]`
si present. Cette separation facilite un changement global (ex. passer de
`git-apply --3way` a `patch -p1 --merge` en cas d'incident) sans toucher
chaque record.

### 3.4 Header DEP-3 enrichi d'un .patch

Le `.patch` conserve un header DEP-3 + champs `X-*` pour les extensions (voir
§5.4 pour l'arbitrage strict vs enrichi). Exemple :

```
Description: wiki-ingest — replace _raw/ fallback by OBSIDIAN_RAW_DIR
 In dual-zone mode, _raw/ lives outside the vault. The original fallback
 `$OBSIDIAN_VAULT_PATH/_raw/` would point to a non-existent directory.
 Fallback order inverted to honor OBSIDIAN_RAW_DIR first.
Origin: vendor
Author: opérateur <ops@example.invalid>
Forwarded: no
Last-Update: 2026-04-20
X-Audit-Ref: docs/260418-dual-sensitivity-analysis.md#b1
X-Severity: BLOCKING
X-Baseline-Sha256: 3f4ac8...
X-Patched-Sha256: 9bd1ee...
---
--- a/.skills/wiki-ingest/SKILL.md
+++ b/.skills/wiki-ingest/SKILL.md
@@ -58,7 +58,7 @@
 ...
```

Les champs `X-*` sont formellement des **extensions prefixees** pour marquer
le caractere non-DEP-3-canonique (cf. §5.4).

---

## 4. UX CLI detaillee

### 4.1 Commandes et flags

Toutes les commandes sont sous `scripts/patch-system`. Codes retour UNIX
standards : `0` = succes, `1` = echec operationnel (conflit non resolu,
drift non arbitre), `2` = erreur d'invocation (argv invalide), `3` = etat
registry invalide.

| Commande | Role | Flags principaux |
|---|---|---|
| `list` | Liste courte (id + status + severity) | `--json`, `--status=active\|disabled\|obsolete` |
| `status` | Tableau detaille par record/target | `--id=<id>`, `--json`, `--only-failing` |
| `describe <id>` | Fiche complete d'un record (metadata + history + targets) | `--json`, `--limit-history=N` |
| `diff <id>` | Affiche le `.patch` avec highlighting TTY | `--no-color`, `--targets-only` |
| `apply <id>` | Applique un patch | `--dry-run`, `--yes`, `--interactive`, `--force` |
| `apply --all` | Applique toute la serie dans l'ordre `order` | `--dry-run`, `--yes`, `--interactive`, `--stop-on-fail` |
| `rollback <id>` | Inverse d'apply | `--dry-run`, `--yes` |
| `rollback --all` | Pop toute la pile dans l'ordre inverse | `--dry-run`, `--yes`, `--stop-on-fail` |
| `refresh <id>` | Recalcule `baseline_sha256` + `patched_sha256` depuis l'etat courant | `--dry-run`, `--yes` |
| `verify` | Integrite : recalcul `patch_sha256`, drift vendor, coherence targets | `--json`, `--strict` |
| `record <id> --from <path>` | Cree un nouveau patch depuis les diffs actuels du working tree | `--title=...`, `--severity=...`, `--dry-run` |

**Flags transverses** :

- `--dry-run` : aucun ecrit disque / aucun appel `git apply` reel (seulement
  `--check`). Simule et affiche.
- `--yes` : non-interactif, echoue au premier choix ambigu au lieu de
  prompter. Mutuellement exclusif avec `--interactive`.
- `--interactive` : force le mode menu (§4.2) meme sur etats non ambigus.
- `--json` : sortie machine-lisible. Implique `--no-color`.
- `--verbose` / `--quiet` : dial sur le niveau de log (voir §5.5).

### 4.2 Mode interactif — prompts etc-update-like

Quand le moteur detection renvoie `partial` ou `dirty` pour un patch,
l'utilisateur est invite a arbitrer via un menu calque sur `etc-update` (SOA
§2.3) et enrichi des options specifiques a notre modele 3-points. Les lettres
sont choisies pour accrocher `git add -p` (y/n/s/d/?) + extensions locales :

```
Patch 0002 target vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md is partial.
   y  apply — force l'application (ecrase les modifs locales si conflit)
   n  skip  — laisse la cible telle quelle, status sera 'dirty'
   s  show  — affiche le diff 3-points (pristine | local | patched)
   d  diff  — affiche seulement le diff patch->local
   3  3way  — tente `git apply --3way` (merge automatique)
   r  refresh — met a jour baseline_sha256 depuis l'etat local courant
   q  quit  — arrete le run, les patches deja traites restent appliques
   ?  help  — re-affiche ce menu
Choice [y/n/s/d/3/r/q/?] (default n): _
```

**Regle de defaut** : la reponse vide = `n` (skip, non-destructif).

**Regle `q`** : `quit` n'est pas `abort` — les decisions prises jusque-la
sont persistees dans series.json ; rien n'est roulle back. Pour revenir a
l'etat pre-run, l'utilisateur doit explicitement lancer `rollback --all`.

### 4.3 Messages-types

**Succes d'apply** (non-interactif, clean → patched) :
```
[b1-wiki-ingest-raw-fallback] clean -> applying...
  target vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md: patched (sha256 9bd1ee...)
  registry updated: last_result=patched last_applied=2026-04-20T10:52:13Z
```

**Detection deja applique** (idempotence) :
```
[b1-wiki-ingest-raw-fallback] patched -> skip (already applied)
```

**Dry-run** :
```
[b3-vendor-env-remove] clean -> would apply patch 0003-vendor-env-remove.patch
  [dry-run] git apply --check --index 0003-vendor-env-remove.patch  OK
  [dry-run] no write performed
```

**Drift detecte lors d'un apply non-interactif avec `--yes`** :
```
[p2-read-dotenv-wording] partial -> 9/12 targets patchable, 3 in conflict
  ERROR: --yes mode forbids interactive arbitration.
  Rerun with --interactive to resolve, or --force to overwrite.
  exit 1
```

### 4.4 Sortie `status` — format

Le tableau `status` utilise une mise en forme compacte inspiree de
`systemctl status` + `ansible-playbook`. Les colonnes :

```
ID                                SEV       TARGETS   STATE      ORDER
b1-wiki-ingest-raw-fallback       BLOCKING  1/1       patched    1
b2-wiki-ingest-security-check     BLOCKING  1/1       patched    2
b3-vendor-env-remove              BLOCKING  1/1       clean      3
b4-vendor-env-subsumed            BLOCKING  0/1       absent     4
p2-read-dotenv-wording            TROMPEUR  9/12      partial    5
p2-raw-in-vault-wording           TROMPEUR  6/6       patched    6

Vendor baseline: ok (matches recorded sha abc123de)
Summary: 6 active / 3 patched / 1 clean / 1 partial / 1 absent
```

`--json` produit la meme info en structure :
```json
{"vendor_baseline":"ok","summary":{"active":6,"patched":3,...},
 "records":[{"id":"b1-...","state":"patched","targets":[...]}, ...]}
```

---

## 5. Arbitrage des 8 points ouverts

Chaque point reprend la formulation SOA §4.6 (plus le pt 8 ajoute par
REV-0001).

### 5.1 Granularite des patches multi-cibles

**Decision** : **1 patch = 1 theme**, un fichier `.patch` peut contenir
plusieurs hunks sur plusieurs fichiers si ils traitent la meme anomalie.
Ex. `p2-read-dotenv-wording` = **1 patch, 12 targets**, pas 12 patches.

**Motivation** :
- **Semantique** : l'anomalie est conceptuellement unique ("wording `Read
  .env` trompeur"). Eclater en 12 records genere 12 decisions de rollback
  independantes — semantiquement incoherent (soit on change le wording, soit
  on le laisse).
- **Review** : relire 12 patches identiques en 2 lignes est bruyant. Un patch
  groupe donne un diff consolide.
- **DEP-3 supporte** : un header DEP-3 peut decrire plusieurs hunks sur
  plusieurs fichiers (le format `diff` unifie le fait nativement).
- **Granularite de rollback** : le rollback d'un patch multi-cibles est
  atomique (toutes les cibles roulle back). Si une cible individuelle pose
  probleme, on extrait un sub-patch en Phase 4 (patch splitting) plutot
  qu'en prevention.

**Alternative rejetee** :
- **N patches atomiques (1 par target)** : rejete — genere 30+ patches pour
  un gain nul ; degrade la review ; complexifie series.json.
- **Mix "groupe + subtasks"** : rejete — pas de mecanisme clair pour exprimer
  la dependance "subtask n'a de sens que dans le groupe". Complexifierait
  series.json (nested records) pour un cas d'usage non demontre.

**Garde-fou** : l'UX interactive (§4.2) permet deja d'arbitrer target par
target ; l'atomicite du rollback reste au niveau du patch, mais la decision
granulaire est exposee au niveau de l'apply.

### 5.2 Auto-commit apres apply

**Decision** : **pas d'auto-commit** dans le vendor submodule (ou le
super-repo). Chaque `apply` laisse le working tree modifie. L'utilisateur
decide ensuite du commit.

**Motivation** :
- **Principe de surprise minimale** : un outil de patch ne devrait pas
  ecrire dans le graphe git sans demande explicite.
- **Coherent avec la strategie vendor retenue (§5.3, option c)** : les
  patches ne sont **jamais** commites dans le submodule. L'etat patched est
  re-genere a la demande.
- **Commit dans le super-repo** : peut etre automatise plus tard via un
  wrapper (`patch-system apply --commit`) mais hors scope Phase 3. La phase
  d'integration (hook post-apply -> commit) est une extension Phase 4.

**Alternative rejetee** :
- **Auto-commit dans submodule** : rejete — pollue l'historique submodule
  avec des commits non-upstreamables, complique les merges `git pull`
  upstream, et contre-indique l'option vendor retenue (5.3).
- **Auto-commit dans super-repo avec sub-ref bump** : rejete (Phase 3) —
  possible Phase 4, mais pas necessaire pour le pilote.

**Documentation** : le README du patch-system indiquera en tete : "l'apply
laisse le working tree sale ; `git add -p` + `git commit` sont de la
responsabilite de l'appelant".

### 5.3 Strategie vendor — critique

**Decision** : **option (a) — submodule git + regeneration deterministe**.
Les patches ne sont **jamais** commites dans le submodule. Le submodule
reste pristine (tracking upstream) ; l'etat patched est un *produit* de
`patch-system apply` sur le working tree du submodule, pas un commit.

**Motivation** :
- **Survit a `git pull` submodule** : le submodule reste a l'upstream. Un
  pull apporte le nouveau HEAD, le working tree post-pull n'est plus patched
  — c'est un etat attendu et detectable (`status` -> `clean` sur toutes
  targets, ou `partial` si drift). `patch-system apply` regenere.
- **Reversibilite** : `rollback --all` ou `git checkout .` dans le submodule
  suffit a revenir pristine. Aucun etat git orphelin a nettoyer.
- **Clarte historique** : le historique submodule reste "ce que l'upstream
  a produit" ; l'historique super-repo ne contient que les changements du
  patch-system (series.json + .patch files). Distinction nette entre "code
  upstream" et "nos corrections".
- **Pratique de l'ecosysteme** : c'est le pattern Debian 3.0 quilt (SOA
  §2.2) — pristine tarball + regeneration deterministe — transpose en
  git-submodule.

**Alternative rejetee — (b) subtree + commits locaux** :
- **Avantage** : les patches sont des vrais commits git, suivables via `git
  log`.
- **Inconvenient fatal** : les patches se melangent avec les merges
  upstream dans le historique (`git log vendor/` donne un mix). Le jour ou
  l'upstream corrige B1, on ne peut pas trivialement retirer notre patch
  local sans un `git revert` qui reintroduit nos modifs en sens inverse
  (double commit). La separation "upstream vs local" est **perdue** —
  contraire a l'esprit "pristine + patches documentes".

**Alternative rejetee — (c) submodule + commits-in-submodule** :
- **Avantage** : etat patched persistent, rechargement instantane au
  checkout.
- **Inconvenient fatal** : (1) un `git pull` dans le submodule genere des
  conflits a chaque upstream update puisque notre HEAD diverge. (2) Le sha
  du submodule dans le super-repo devient "un HEAD local prive" non
  partageable (collaboration impossible). (3) Chaque machine de dev doit
  rejouer nos commits — on re-invente le patch-system au niveau git avec
  tous ses inconvenients.

**Consequence pour le reste du design** :
- `patch-system apply` est idempotent et rapide → OK d'etre appele apres
  chaque checkout.
- `drift.py` compare `vendor_baseline_sha` (du super-repo) au HEAD courant
  du submodule → signale quand une mise a jour upstream a eu lieu.
- **ADR-0001 formalise cette decision** (voir `docs/adr/ADR-0001-*.md`).

### 5.4 DEP-3 strict vs enrichi

**Decision** : **DEP-3 enrichi avec prefixe `X-*`** pour les champs non
canoniques. Champs ajoutes : `X-Audit-Ref`, `X-Severity`, `X-Baseline-Sha256`,
`X-Patched-Sha256`.

**Motivation** :
- **DEP-3 n'interdit pas les extensions** (<https://dep-team.pages.debian.net/deps/dep3/>),
  mais la convention implicite RFC-822-like est que les champs
  non-standardises sont prefixes `X-` (cf. en-tetes email, HTTP ancien).
  Utiliser `X-*` signale clairement au lecteur qui connait DEP-3 : "champ
  ajoute par ce projet, pas attendu par un parser generique".
- **Rejet de l'approche "champ nu"** (`Baseline-Sha256` sans prefixe) :
  un parser DEP-3 strict lancerait potentiellement un warning `unknown
  field`. Le prefixe evite l'ambiguite.
- **Rejet de l'approche "tout en DEP-3 strict + sidecar JSON"** : les
  donnees sha256 et severity sont *naturelles dans l'en-tete* (aupres du
  `Description`), pas dans un registre separe. La duplication entre en-tete
  et series.json est acceptee (l'en-tete est pour l'humain, series.json
  pour la machine — ils peuvent derive, le moteur fait foi sur series.json).

**Alternative rejetee** :
- **DEP-3 strict + tout en JSON** : rejete — perd l'auto-suffisance du
  `.patch` pour forwardage upstream.

**Verification de coherence** : un check dedie dans `verify` : pour chaque
record, parser le header du `.patch`, verifier que les `X-Baseline-Sha256`
et `X-Patched-Sha256` matchent ceux de series.json. Divergence -> warning.

### 5.5 Upstream drift — escalade vs 3-way auto

**Decision** : **escalade a l'utilisateur par defaut** quand `git apply
--check` echoue. Le 3-way n'est jamais silencieux. Un dial `--auto-3way`
(opt-in explicite) permet de le tenter et d'accepter son resultat sans
prompt — destine aux environnements CI ou le prompt n'a pas de sens.

**Motivation** :
- **Principe de surprise minimale** : un `git apply --3way` qui reussit
  silencieusement peut changer la semantique de l'anomalie corrigee. Ex. :
  B1 corrige un ordre de fallback — un 3-way mal place pourrait inverser
  la correction et le patch-system dirait "patched" a tort.
- **Mode `verbose` par defaut** : les echecs `--check` et les tentatives
  `--3way` sont logges avec diff affiche, pour que l'operateur voie ce
  qu'il accepte.
- **Mode CI (`--auto-3way --yes`)** : reserve aux cas ou une suite de
  tests downstream validera le resultat. Affiche un warning explicite dans
  la sortie pour distinguer "applied from 3way merge" de "applied from
  clean pristine".

**Alternative rejetee** :
- **Auto-3way silencieux par defaut** : rejete — fail-silent, dangereux
  pour des patches audit-refed (B1-B4).
- **Pas de 3-way du tout** : rejete — le 3-way est precieux quand le drift
  est cosmetique (ajout de blank line upstream, etc.). Supprimer l'option
  aboutirait a trop de "partial" manuels pour des cas triviaux.

**Implementation** : `detect.evaluate()` renvoie un state + un
`can_auto_3way: bool` (vrai si le 3-way reussirait, detecte via `git apply
--3way --check`). Le caller (apply ou UI) decide d'afficher/proposer.

### 5.6 Framework tests

**Decision** : **`unittest` stdlib** pour la suite de tests Phase 3. Zero
dep pip.

**Motivation** :
- **Contrainte projet** : "Python stdlib par defaut" — `pytest` est une
  dep pip meme si ultra-standard.
- **Volume de tests modere** : 15-30 cas suffisent pour couvrir les 6 etats
  + les flows apply/rollback/refresh/verify. `unittest` tient ce volume
  sans friction.
- **Coherence avec `unidiff` optionnel** : le code applicatif accepte deja
  un degrade gracieux sans `unidiff` ; les tests doivent pouvoir tourner sur
  une install stdlib pure pour valider le chemin de fallback.
- **CI simple** : `python3 -m unittest discover` est un one-liner ; pas de
  `pytest.ini`/`pyproject.toml` a maintenir.

**Alternative rejetee** :
- **`pytest`** : rejete — dep pip ; les avantages (fixtures,
  parametrisation) sont reels mais non necessaires pour le volume Phase 3.
  Si la suite grossit en Phase 4 (>100 cas), reevaluer.
- **Mix `unittest` + `pytest`** : rejete — confusion (deux runners, deux
  styles de fixtures).

**Convention** : fichiers `scripts/patch_system/tests/test_*.py`,
discovery standard. Fixtures vendor fausses dans `tests/fixtures/` avec un
arbre minimal pre-construit (~ 5 fichiers) + 3-4 patches de test.

### 5.7 Verrou de concurrence

**Decision** : **`flock` obligatoire** sur toutes les operations mutantes
(`apply`, `rollback`, `refresh`, `record`). Fichier de lock :
`patches/.lock`.

**Motivation** :
- **Risque reel meme en mono-user** : un agent (ex. kiss-executor) et
  l'humain peuvent cohabiter. Deux `apply` paralleles corrompent
  `series.json` (write race).
- **Cout nul** : `flock` est un builtin util-linux present partout ; sa
  syntaxe shell est deja dans le dispatcher (`scripts/patch-system`).
- **Read-only operations non verrouillees** : `status`, `describe`,
  `diff`, `list`, `verify --read-only` — l'utilisateur peut consulter
  l'etat pendant qu'un apply tourne. `verify --strict` qui ecrit dans un
  log prend aussi le lock.

**Alternative rejetee** :
- **Pas de lock / scenario mono-user** : rejete — le cout (1 flock) est
  negligeable face au risque de corruption registre dans un scenario
  multi-agent de plus en plus plausible.

**Implementation** :
```bash
# dans scripts/patch-system (illustratif)
exec 9>"${PATCHES_DIR}/.lock"
flock -n 9 || { echo "patch-system: another operation in progress"; exit 1; }
```
Les operations read-only n'executent pas ce `flock`.

### 5.8 Separation registre / runtime — structure series.json

**Decision** : **deux fichiers separes, `series.json` + `runtime.json`**
(voir §3.1-3.3).

**Motivation** :
- **Responsabilites distinctes** : le registre logique identifie **ce qui
  doit etre patche** (id, order, status, severity, targets avec sha). Le
  runtime decrit **comment patcher** (detection.strategy, apply.method,
  args). Les deux evoluent a des rythmes differents.
- **Changement de runtime sans "churn" patch** : changer la strategie
  d'apply (de `git-apply` a `patch -p1 --merge`) n'a pas a toucher le
  registre — pas de pseudo-commit "update method" qui pollue les diffs
  review.
- **Defaults + overrides** : `runtime.json` a une structure `defaults` +
  `overrides[id]`. 99% des patches utilisent les defauts. Les overrides
  restent visibles a un endroit.
- **Testabilite** : les tests unitaires du moteur peuvent injecter une
  `runtime.json` mockee sans toucher le registre reel.

**Alternative rejetee** :
- **Un seul fichier avec sections melangees** (cf. exemple SOA §4.4) :
  rejete — mele les preoccupations ; chaque record duplique
  `detection/apply/rollback` meme quand tous les patches utilisent les
  defauts. Lourd a reviewer.
- **runtime encode en comments en tete de series.json** : rejete — JSON
  n'a pas de comments standard.

---

## 6. Traitement des notes REV-0001

### 6.1 Erratum `whatthepatch` (§2.8 SOA)

L'affirmation **"whatthepatch utilise par Black et pre-commit"** dans
§2.8 du SOA est non corroboree par inspection locale (cf. REV-0001). Ni
`black` ni `pre-commit` ne listent `whatthepatch` comme dependance runtime
dans leur `setup.py`/`pyproject.toml` recents.

**Traitement en design** : **pas de rework du SOA commite**. Cet erratum
est note ici. Le SOA reste en l'etat historique. La description correcte a
retenir pour la decision outillage : `whatthepatch` est **un parser
unified/context/git diff maintenu, pertinent si on voulait supporter des
formats varies**, sans affirmation d'usage par Black/pre-commit. Le design
retient **`unidiff` (optionnel)** et non `whatthepatch`.

### 6.2 Python 3.10+ vs 3.11+

**Decision design** : **Python 3.10+ minimum**. `tomllib` (stdlib a partir
de 3.11) **n'est pas utilise** ; la config runtime et le registre sont en
JSON (§3.2, §3.3). Donc pas de besoin de bumper a 3.11+.

**Justification** :
- Cible deploiement : Debian 12 (`python3` = 3.11), Debian 11 (`python3` =
  3.9 — non cible), Ubuntu 22.04 (3.10). 3.10+ couvre tous les environnements
  de dev/prod raisonnables.
- Si un besoin futur de TOML apparait (ex. un fichier de preferences
  utilisateur), on le traitera a ce moment-la (soit bump a 3.11, soit
  parser TOML manuel minimal, soit accepter la dep pip `tomli`).

### 6.3 Sources et methodologie

Les URLs citees dans §5 du SOA (Debian DEP-3, Quilt, Gentoo wiki, Nixpkgs
manual, Arch wiki, Fedora packaging, docs Ansible/Puppet, PyPI des libs
Python, etc.) **n'ont pas ete revérifiees live** dans la phase Phase 1 (pas
de WebFetch dispo a l'executor). Leur structure et leur contenu sont issus
du training knowledge de l'executor (standards stables depuis 10+ ans, mais
non verifie live).

**Engagement pour Phase 3+** : avant publication finale des ADRs (ce
document + ADR-0001) en dehors de la session de design, un **spot-check
manuel** des URLs sera effectue (resolution DNS + HTTP 200 + pertinence du
contenu pointe). Les eventuels `404` seront remplaces par des liens stables
(archive.org, permalink git, manpage debian version-ancree).

Ce caveat est explicite pour qu'un lecteur qui s'appuierait sur ces URLs
pour prendre une decision critique en soit averti.

---

## 7. Plan d'implementation Phase 3

Phase 3 cible le **pilote B3** (`vendor-env-remove`) pour bootstrapper le
framework, puis ajoute progressivement B1, B2, B4, p2-*. Jalons (sans detail
d'implementation) :

1. **Squelette package** — `scripts/patch_system/` + dispatcher bash.
   Import-able, commandes stubbed (`list`/`status` retournent vide).
2. **Registre + schema** — `registry.py` : load/save/validate `series.json`
   vide, implements schema version 1 (§3.2). Tests unittest.
3. **Fixtures tests** — `tests/fixtures/vendor-mini/` : arbre minimal 5
   fichiers + 3 patches synthetiques (clean/patched/drifted). Reutilisables
   par tous les tests.
4. **Moteur detection sha256** — `detect.py` v1 : seulement sha256 (pas de
   git apply check). Couvre `clean`/`patched`/`dirty`/`absent`. Tests.
5. **Moteur detection composite** — ajout `git apply --check` + `--reverse`
   pour state `patched` avec drift cosmetique, + detection `partial` via
   hunks rejetes. Tests de l'integralite du state machine.
6. **Moteur apply v1** — `git-apply --index` uniquement, pas de `--3way`, pas
   de fallback `patch(1)`. Integration avec registre pour `last_applied`/
   `last_result`. Flock en place. Tests.
7. **Moteur rollback** — `git-apply --reverse`. Garde-fou "refuse si
   `last_result != patched`". Tests.
8. **Commande `status` + `list` + `describe` + `diff`** — formatting TTY et
   `--json`. Tests de sortie.
9. **Commande `verify`** — recalcul patch_sha256, drift vendor, coherence
   targets. Tests.
10. **Commande `refresh`** — recalcul baseline/patched sha depuis l'etat
    courant. Tests.
11. **Premier patch reel** — `0003-vendor-env-remove.patch` (B3) cree via
    `record` ou main manuel. Entree correspondante dans series.json.
    Commit dans super-repo.
12. **Commande `apply` + mode interactif (etc-update-like)** — integration
    `ui.py`. Tests sur les 3 lettres principales `y`/`n`/`q`, puis `3`/`r`.
13. **`apply --all` + `rollback --all`** — iteration ordonnee + gestion
    `--stop-on-fail`. Tests.
14. **Fallback `patch(1)`** + dial `--auto-3way` + `runtime.json` overrides.
    Tests.
15. **B1/B2/B4 + p2-\*** — ajout progressif des patches restants, en
    exploitant le framework maintenant stable.
16. **Verify-in-CI** — integration minimale dans un hook git ou un
    `.gitlab-ci.yml` de validation (hors scope code, juste l'appel).

**Livrable Phase 3** : `scripts/patch-system` + `scripts/patch_system/`
fonctionnels sur les ~6 patches (B1-B4 + p2-*), tests passants, README
utilisateur.

---

## 8. References croisees

- Etat de l'art : `docs/260420-patch-system-soa.md` (sections citees tout
  au long : §2.1 quilt, §2.2 Debian 3.0, §2.3 etc-update, §2.6 Ansible,
  §2.7 detection, §4.1 storage, §4.4 record, §4.6 points ouverts).
- Audit cible : `docs/260418-dual-sensitivity-analysis.md` (anomalies
  B1-B4, p2-*).
- ADR structurante : `docs/adr/ADR-0001-vendor-submodule-pristine.md`
  (decision §5.3).

**Justification du nombre d'ADR** : une seule ADR produite en Phase 2
design — §5.3 est la seule decision dont l'impact est **transverse a tout
le reste** (elle contraint apply/rollback/drift/git-pull-survival et rend
§5.2 "pas d'auto-commit" quasi-obligatoire). Les autres decisions (§5.1
granularite, §5.4 DEP-3 enrichi, §5.5 escalade 3-way, §5.6 unittest, §5.7
flock, §5.8 separation series/runtime) sont documentees ici et pourront
faire l'objet d'ADRs posterieurs si elles sont remises en cause.
