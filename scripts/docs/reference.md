# Référence — patch-system

Documentation exhaustive, neutre, ordonnée par sujet. Pour apprendre,
[tutorial.md](./tutorial.md). Pour une procédure, [how-to.md](./how-to.md).
Pour comprendre, [explanation.md](./explanation.md).

---

## §1. CLI — commandes opérationnelles

Codes retour UNIX standard (design §4.1, cité verbatim) :

> Toutes les commandes sont sous `scripts/patch-system`. Codes retour UNIX
> standards : `0` = succes, `1` = echec operationnel (conflit non resolu,
> drift non arbitre), `2` = erreur d'invocation (argv invalide), `3` = etat
> registry invalide.
>
> Source : `docs/260420-patch-system-design.md §4.1`.

### 1.0 Dispatcher principal

```
usage: patch-system [-h] [--series SERIES] [--vendor-root VENDOR_ROOT]
                    command ...

Manage local patches on vendor/obsidian-wiki.

positional arguments:
  command
    list                List records from the registry.
    status              Per-record live detection state.
    describe            Full fiche for a single record.
    diff                Show the patch content.
    apply               Apply a patch.
    rollback            Reverse-apply a patch.
    verify              (stub until jalon 9/10) Integrity checks.
    refresh             (not yet implemented — jalon 10)
    record              (not yet implemented — jalon 11)

options:
  -h, --help            show this help message and exit
  --series SERIES       Path to series.json (default:
                        $PATCH_SYSTEM_ROOT/patches/series.json).
  --vendor-root VENDOR_ROOT
                        Vendor working tree root (default:
                        $PATCH_SYSTEM_ROOT/vendor/obsidian-wiki).
```

Les flags `--series` et `--vendor-root` sont **top-level** (avant la
sous-commande), pas per-subcommand.

### 1.1 `list`

**Synopsis**
```
usage: patch-system list [-h] [--json] [--status {active,disabled,obsolete}]
```

**Description**
Liste les records présents dans `series.json`. Source statique, ne consulte
pas le working tree.

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `-h, --help` | flag | — | Affiche l'aide et sort. |
| `--json` | flag | `false` | Sortie JSON (clé `records`). |
| `--status {active,disabled,obsolete}` | choix | tous | Filtre par `status` de cycle de vie du record. |

**Exemples**
```bash
./scripts/patch-system list
./scripts/patch-system list --json --status=active
```

**Exit codes** : `0` OK, `3` registre invalide.

### 1.2 `status`

**Synopsis**
```
usage: patch-system status [-h] [--json] [--id ID] [--only-failing]
```

**Description**
Pour chaque record, évalue l'état live via la détection composite
(sha256 + `git apply --check` + split per-hunk). Affiche un tableau ou
du JSON. Colonnes : `ID`, `SEV`, `TARGETS` (fraction N/M), `STATE`,
`ORDER`. Sous le tableau : ligne `Vendor baseline` + ligne `Summary`.

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `-h, --help` | flag | — | Aide. |
| `--json` | flag | `false` | Sortie JSON `{vendor_baseline, vendor_baseline_sha, summary, records}`. |
| `--id ID` | string | aucun | Restreint l'évaluation à un seul record. |
| `--only-failing` | flag | `false` | Filtre aux états `dirty` / `partial` / `absent`. |

**Exemples**
```bash
./scripts/patch-system status
./scripts/patch-system status --only-failing
./scripts/patch-system status --id=b3-vendor-env-remove --json
```

**Exit codes** : `0` OK, `1` record `--id` inconnu, `3` registre invalide.

### 1.3 `describe`

**Synopsis**
```
usage: patch-system describe [-h] [--json] [--limit-history LIMIT_HISTORY] id
```

**Description**
Fiche détaillée d'un record : métadonnées du registre, détection live
per-target, historique (depuis `patches/history/<order>-history.jsonl` quand
présent).

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `id` (positionnel) | string | — | Identifiant du record. |
| `-h, --help` | flag | — | Aide. |
| `--json` | flag | `false` | Sortie JSON. |
| `--limit-history N` | int | pas de limite | Ne garde que les N derniers événements d'historique. |

**Exemple**
```bash
./scripts/patch-system describe t0001-readme-add-section
```

**Exit codes** : `0` OK, `1` record inconnu, `3` registre invalide.

### 1.4 `diff`

**Synopsis**
```
usage: patch-system diff [-h] [--no-color] [--targets-only] id
```

**Description**
Affiche le contenu du fichier `patches/<patch_file>`. Coloration ANSI par
défaut si stdout est un TTY (`+` vert, `-` rouge, `@@` cyan, headers `+++`
/ `---` non colorés).

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `id` (positionnel) | string | — | Identifiant du record. |
| `-h, --help` | flag | — | Aide. |
| `--no-color` | flag | `false` | Désactive la coloration ANSI. |
| `--targets-only` | flag | `false` | Affiche seulement les chemins cible extraits des lignes `+++ b/...`. |

**Exemples**
```bash
./scripts/patch-system diff t0001-readme-add-section --no-color
./scripts/patch-system diff t0001-readme-add-section --targets-only
```

**Exit codes** : `0` OK, `1` record inconnu ou fichier `.patch` manquant.

### 1.5 `apply`

**Synopsis**
```
usage: patch-system apply [-h] [--dry-run] [--yes] id
```

**Description**
Applique le patch du record `id` via `git apply --index` (forward), en
respectant la règle d'idempotence et le garde-fou non-interactif.

Comportement selon l'état initial (résultat de la détection composite) :

- `clean` → applique (ou simule en `--dry-run`).
- `patched` → no-op, message `patched -> skip (already applied)`, exit `0`.
- `absent` → refuse, exit `1` (un ou plusieurs targets manquent).
- `dirty` / `partial` sans `--yes` → refuse (`arbitration required`), exit `1`.
- `dirty` / `partial` avec `--yes` → refuse quand même (`--yes mode forbids
  interactive arbitration`), exit `1`. Le mode interactif (jalon 12) et
  `--force` (jalon 14) ne sont pas encore implémentés.

En cas de succès, écrit dans `series.json` :
- `last_applied` : instant UTC ISO-8601 (ex. `"2026-04-20T10:52:13Z"`)
- `last_result` : l'état post-apply (typiquement `"patched"`)

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `id` (positionnel) | string | — | Identifiant du record. |
| `-h, --help` | flag | — | Aide. |
| `--dry-run` | flag | `false` | Invoque seulement `git apply --check`. N'écrit ni sur disque ni dans le registre. |
| `--yes` | flag | `false` | Non-interactif strict. Comme il n'existe pas encore de mode interactif (J12), `--yes` revient pour l'instant à refuser les états ambigus avec un message explicite. |

**Flags documentés dans le design mais pas encore implémentés**

| Flag | Jalon | Statut |
|---|---|---|
| `--interactive` | J12 | Non implémenté — absent du parser argparse. |
| `--force` | J14 | Non implémenté — absent du parser argparse. |
| `--auto-3way` | J14 | Non implémenté. |

**Exemples**
```bash
./scripts/patch-system apply <id> --dry-run
./scripts/patch-system apply <id>
```

**Exit codes** : `0` succès (y compris no-op idempotent), `1` échec
opérationnel (état ambigu, `git apply` en erreur, target absent).

### 1.5bis Options batch et interactives de `apply` (J12-J14)

Depuis les jalons J12-J14, `apply` accepte les flags supplémentaires
suivants. Ils s'ajoutent à ceux du §1.5 ; tous sont implémentés dans
`scripts/patch_system/cli.py` (sous-parser `apply`) et
`scripts/patch_system/apply.py`.

**Synopsis complet (J15)**
```
usage: patch-system apply [-h] [--dry-run] [--yes] [--interactive] [--force]
                          [--auto-3way] [--all] [--stop-on-fail] [id]
```

Le positionnel `id` devient optionnel : il est absent lorsque `--all`
est fourni.

**Flags ajoutés**

| Flag | Jalon | Effet |
|---|---|---|
| `--interactive` | J12 | Force l'affichage du menu §4.2 (`y/n/s/d/3/r/q/?`) à chaque target, même pour les états `clean`. Mutuellement exclusif avec `--yes`. |
| `--force` | J14 | Équivaut à un `y` implicite sur tout état ambigu (`dirty`, `partial`) — écrase les modifications locales. Aucun prompt. |
| `--auto-3way` | J14 | Opt-in §5.5 : tente `git apply --3way --index` avant d'escalader vers le menu ou de refuser. Sur succès, continue comme un apply normal ; sur échec, retombe sur la logique interactive / `--yes`. |
| `--all` | J13 | Applique tous les records `status == active` par ordre croissant de `order`. `id` doit être absent. |
| `--stop-on-fail` | J13 | Avec `--all` : break à la première failure. Sans ce flag, la boucle continue et l'exit code final est `0` si tout a réussi, `1` sinon. |

**Exclusion mutuelle `--yes` / `--interactive`**

```
[<id>] invalid flags: --yes and --interactive are mutually exclusive.
```
Exit code : `0` n'est PAS émis — `apply` renvoie un résultat `success=False` (exit `1`).

**Message canonique du refus `--yes`** (design §4.3, via `ui.py`) :
```
[<id>] <state> -> ambiguous state.
  ERROR: --yes mode forbids interactive arbitration.
  Rerun with --interactive to resolve, or --force to overwrite.
```

**Menu interactif** (§4.2, implémenté dans `scripts/patch_system/ui.py`) — les
huit lettres du prompt :

| Lettre | Choix | Effet |
|---|---|---|
| `y` | apply | Force l'application (écrase les modifs locales si conflit). |
| `n` | skip | Laisse la cible telle quelle. **Défaut quand l'utilisateur tape Entrée vide.** Le status résultant sera `dirty`. |
| `s` | show | Affiche le diff 3-points (pristine / local / patched). |
| `d` | diff | Affiche le diff `patch -> local`. |
| `3` | 3way | Tente `git apply --3way`. |
| `r` | refresh | (redirige vers la commande `refresh` — à invoquer à part). |
| `q` | quit | Arrête la run ; les patches déjà traités restent appliqués (pas de rollback). |
| `?` | help | Ré-affiche le menu. |

Comportement EOF (stdin fermé / non-TTY) : équivaut à `n` (skip) avec un
message informatif. Lettres inconnues : le menu est ré-affiché.

**Sémantique `apply --all`**

- Itère les records `active` par `order` croissant (source :
  `cli.py::_cmd_apply_all`).
- Un `flock` unique est posé pour toute la run (§4.3 verbatim : « 1
  flock pour la run entière, pas par record »). Les read-only
  `list` / `status` / `describe` / `diff` / `verify` restent
  disponibles pendant la run.
- `q` dans le menu interactif : break avec `user quit`, exit `0`
  (run considérée interrompue par l'utilisateur, pas en échec).
- Résumé de fin de run imprimé sur stdout :
  ```
  apply --all: <N> applied, <M> skipped, <K> failed[ (user quit)]
  ```

**Exit codes `apply --all`**

| Cas | Exit |
|---|---|
| Tout appliqué ou idempotent | `0` |
| `q` dans le menu (user quit) | `0` |
| Au moins un record en failed, sans `--stop-on-fail` | `1` |
| Premier échec avec `--stop-on-fail` | `1` |

### 1.6 `rollback`

**Synopsis**
```
usage: patch-system rollback [-h] [--dry-run] [--yes] id
```

**Description**
Annule le patch via `git apply --reverse --index`. Garde-fou : refuse si
`record["last_result"] != "patched"` dans le registre. En cas de succès,
met à jour `last_applied` + `last_result` (typiquement `clean`).

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `id` (positionnel) | string | — | Identifiant du record. |
| `-h, --help` | flag | — | Aide. |
| `--dry-run` | flag | `false` | `git apply --reverse --check` uniquement. |
| `--yes` | flag | `false` | Accepté pour uniformité CLI ; n'a pas d'effet sur le garde-fou en J7. |

**Flag documenté dans le design mais pas encore implémenté**

| Flag | Jalon | Statut |
|---|---|---|
| `--force` | J14 | Non implémenté. Seule façon future d'outrepasser le garde-fou `last_result`. |

**Exit codes** : `0` succès, `1` refus (garde-fou ou `git apply --reverse` en
erreur).

### 1.6bis Options batch de `rollback` (J13)

Depuis le jalon J13, `rollback` accepte `--all` et `--stop-on-fail`.

**Synopsis complet (J15)**
```
usage: patch-system rollback [-h] [--dry-run] [--yes] [--all] [--stop-on-fail] [id]
```

**Flags ajoutés**

| Flag | Effet |
|---|---|
| `--all` | Pop l'ensemble des records `active` par ordre **décroissant** de `order` (design §4.1 ligne 307 verbatim). `id` doit être absent. |
| `--stop-on-fail` | Avec `--all` : break à la première failure. |

**Sémantique `rollback --all`** (source : `cli.py::_cmd_rollback_all`)

- Ordre décroissant : un LIFO sur la pile `apply --all`.
- Un `flock` unique pour toute la run (§4).
- Skip automatique des records dont `last_result != "patched"` — chaque
  skip produit une ligne :
  ```
  [<id>] skip (last_result != 'patched')
  ```
- Résumé de fin de run :
  ```
  rollback --all: <N> reverted, <M> skipped, <K> failed
  ```

**Exit codes**

| Cas | Exit |
|---|---|
| Tout reverted ou skippé | `0` |
| Au moins un échec, sans `--stop-on-fail` | `1` |
| Premier échec avec `--stop-on-fail` | `1` |

### 1.7 Commandes à venir (non opérationnelles en J8)

> **`verify` (jalon J9)**, **`refresh` (jalon J10)**, **`record` (jalon J11)**
> sont **présentes dans le parser argparse mais retournent un exit code non
> nul et un message « not yet implemented »** :
>
> - `verify` : sur registre vide, exit `0` avec warning ; sinon exit `1` avec
>   `"Phase 3 verify not yet implemented — jalons 9/10. (N record(s) would be
>   checked.)"` sur stderr.
> - `refresh <id>` : exit `2`, message `"patch-system: command 'refresh' not
>   yet implemented (design §7 — jalon 10)"`.
> - `record <id> [--from PATH]` : exit `2`, message `"patch-system: command
>   'record' not yet implemented (design §7 — jalon 11)"`.
>
> Se référer à [explanation.md](./explanation.md) pour la conception prévue.

### 1.8 `verify` (J9)

**Synopsis**
```
usage: patch-system verify [-h] [--json] [--strict]
```

**Description**
Exécute trois contrôles pour chaque record du registre (source :
`scripts/patch_system/verify.py`, aligné design §2.3 « Flux verify » et
§4.1 ligne 309) :

1. **Intégrité** : recalcule le sha-256 du fichier `.patch` et le compare
   à `patch_sha256` du record. Mismatch → le fichier `.patch` a été
   modifié depuis son enregistrement.
2. **Drift** : compare `vendor_baseline_sha` (racine du registre, si
   présent) à la tête du submodule vendor courant. Également, pour chaque
   target : si le sha courant du fichier ≠ `baseline_sha256` ET ≠
   `patched_sha256`, remonte un drift per-target.
3. **Cohérence des targets** : pour chaque record `active`, chaque
   `targets[].path` doit exister sous `vendor_root` (sinon incohérence
   dure).

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `-h, --help` | flag | — | Aide. |
| `--json` | flag | `false` | Sortie JSON `{registry_valid, vendor_baseline_recorded, vendor_baseline_current, records, summary, strict}`. |
| `--strict` | flag | `false` | Remonte les `drift` en failure (exit `1`). Sans `--strict`, un drift détecté est un warning et l'exit code reste `0`. |

**Sortie texte**

Une ligne par record :
```
[<id>] ok
[<id>] integrity=<mismatch|missing> coherence=<missing_targets> drift=<detected>
    - <issue 1>
    - <issue 2>
```

Ligne de pied de page : drift `vendor_baseline` si détecté, ou
`Vendor baseline: not recorded in series.json` si absent. Bannière finale :
`verify: all records ok` ou `verify: failures detected`.

**Exit codes** (design §4.1 verbatim)

| Cas | Exit |
|---|---|
| Tous OK (ou seulement warnings en mode non-strict) | `0` |
| Registre vide | `0` (message `verify: (empty registry — nothing to verify)`) |
| Intégrité mismatch / `.patch` manquant sur disque | `1` |
| Target manquante sur un record `active` | `1` |
| Drift détecté avec `--strict` | `1` |
| Registre invalide (schéma §2) | `3` |

**Exemples**
```bash
./scripts/patch-system verify
./scripts/patch-system verify --json
./scripts/patch-system verify --strict         # drift = failure
```

> Escalade drift : un drift n'est **jamais silencieux** (§5.5 design).
> Sans `--strict` il est remonté en texte + exit `0` ; avec `--strict` il
> devient un échec dur.

### 1.9 `refresh` (J10)

**Synopsis**
```
usage: patch-system refresh [-h] [--dry-run] [--yes] id
```

**Description**
Recalcule `baseline_sha256` ou `patched_sha256` du record `id` depuis
l'état courant des targets sur disque (source :
`scripts/patch_system/refresh.py`, aligné design §4.1 ligne 308 et §7
item 10).

Règle selon l'état composite du record au moment de l'appel :

| État courant | Champ recalculé | Autre champ |
|---|---|---|
| `clean` | `baseline_sha256` de chaque target | `patched_sha256` laissé intact. |
| `patched` | `patched_sha256` de chaque target | `baseline_sha256` laissé intact. |
| `dirty`, `partial`, `absent`, `unknown` | — | Refusé : résoudre (apply ou rollback) d'abord. |

Chaque refresh réussi écrit une ligne d'historique dans
`patches/history/<order>-history.jsonl` (§2.2), de la forme :
```json
{"ts": "...", "action": "refresh", "result": "clean|patched",
 "operator": "auto", "commit": null,
 "changes": [{"path": "...", "field": "baseline_sha256",
              "old": "<sha>", "new": "<sha>"}, ...]}
```

**Flags**

| Flag | Type | Défaut | Effet |
|---|---|---|---|
| `id` (positionnel) | string | — | Identifiant du record. |
| `-h, --help` | flag | — | Aide. |
| `--dry-run` | flag | `false` | Affiche les changements, n'écrit rien (ni registre ni historique). |
| `--yes` | flag | `false` | Saute la confirmation interactive `y/N`. |

**Confirmation interactive**

Sans `--yes` et après l'aperçu des diffs, `refresh` demande :
```
[<id>] apply <N> change(s) to series.json? (y/N)
```
Réponse `y` / `yes` (case-insensitive) confirme ; toute autre réponse
ou EOF annule (`aborted by user`, exit `1`).

**Exit codes** (design §4.1)

| Cas | Exit |
|---|---|
| Refresh écrit avec succès (ou `--dry-run`) | `0` |
| `id` inconnu | `2` |
| État incohérent (`dirty` / `partial` / `absent` / `unknown`), target absente, ou refus utilisateur | `1` |

**Exemples**
```bash
./scripts/patch-system refresh t0001-readme-add-section --dry-run
./scripts/patch-system refresh t0001-readme-add-section --yes
```

---

## §2. Schéma `series.json` v1

Source autoritaire : `docs/260420-patch-system-design.md §3.2`. Cité
verbatim ci-dessous.

**Structure racine**
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

> Source : `docs/260420-patch-system-design.md §3.2` (bloc JSON reproduit
> tel quel).

### 2.1 Champs obligatoires (cités verbatim design §3.2)

> **Champs obligatoires** : `id`, `order`, `status`, `severity`, `title`,
> `patch_file`, `patch_sha256`, `targets[]`. Chaque entree de `targets[]` doit
> contenir `path` + `baseline_sha256` + `patched_sha256`.

### 2.2 Champs optionnels (cités verbatim design §3.2)

> **Champs optionnels** : `audit_ref` (trace vers l'audit dual-sensitivity),
> `last_applied`, `last_result`, `notes`. L'historique complet (ancien champ
> `history[]` du SOA §4.4) est externalise dans
> `patches/history/<order>-history.jsonl` pour eviter le gonflement du
> registre (ajout/an d'audit = lignes a plat, pas de serialisation JSON a
> reecrire integralement).

Chaque ligne JSONL est un événement de la forme :
```json
{"ts":"2026-04-20T10:52:13Z","action":"apply","result":"patched","operator":"auto","commit":null}
```

### 2.3 Types attendus (cités verbatim design §3.2)

> - `id` : string kebab-case, prefixe `<code-audit>-<slug>` (ex. `b1-*`, `p2-*`).
> - `order` : integer > 0, unique dans la serie, pas forcement contigu.
> - `status` : enum `active | disabled | obsolete` (cf. SOA §4.4).
> - `severity` : enum `BLOCKING | TROMPEUR | COSMETIQUE | INFO`.
> - `patch_sha256` / `baseline_sha256` / `patched_sha256` : string hex 64 chars.
> - `last_result` : enum `clean | patched | partial | dirty | absent | unknown`.

### 2.4 Multi-targets

Un record peut porter plusieurs entrées dans `targets[]` si elles traitent
la **même anomalie** (design §5.1). Exemple (tiré design §3.2) :

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

### 2.5 Séparation avec `runtime.json`

La **stratégie d'exécution** (détection, méthode d'apply, args) vit dans un
fichier séparé `patches/runtime.json` (schéma §3.3 design, ADR-0002). Elle
n'impacte pas l'identité des patches et n'est pas abordée ici — non consommée
par les commandes J1-J8.

---

## §3. États de détection

Source autoritaire : `docs/260420-patch-system-design.md §5` (detect
composite). Les règles ci-dessous sont citées en forme normalisée.

| État | Sémantique | Quand il apparaît |
|---|---|---|
| `clean` | Working tree = état pré-patch. Le patch s'appliquerait sans conflit. | `sha256(file) == baseline_sha256` pour toutes les targets **OU** sha-agg est `dirty` et `git apply --check` (forward) réussit → cosmetic drift + état lifecycle `clean` (source design §5). |
| `patched` | Working tree = état post-patch. Le patch peut être reverted proprement. | `sha256(file) == patched_sha256` pour toutes les targets **OU** sha-agg est `dirty` et `git apply --reverse --check` réussit → cosmetic drift + état lifecycle `patched`. |
| `partial` | Mélange : certaines targets sont dans un état cohérent, d'autres non, ou per-hunk certains hunks s'appliqueraient et d'autres non. | Mix `clean` + `patched` entre targets ; OU split per-hunk : `0 < applyable < total`. `drift_hint="semantic"`. |
| `dirty` | Working tree divergent. Aucun match sha, aucun `git apply --check` ne passe, aucun hunk applicable. | SHA ne matchent ni `baseline` ni `patched` ET forward+reverse+per-hunk échouent tous. `drift_hint="semantic"`. |
| `absent` | Une ou plusieurs targets sont **absentes** du disque. | Le fichier n'existe pas (résolu via `vendor_root` + path). |
| `unknown` | Agrégation impossible (record sans targets). | Pas de `targets[]`. |

> **Sémantique cosmétique vs sémantique (cité verbatim depuis
> `scripts/patch_system/detect.py` docstring, aligné design §5.5)** :
>
> > Forward `--check` success means the file is pre-patch with cosmetic
> > drift → state="clean". Reverse `--check` success means the file is
> > post-patch with cosmetic drift → state="patched". These are two
> > distinct semantics and must not be conflated.

**Métadonnées auxiliaires** (retournées par `evaluate()` et visibles dans
`describe --json`) :

- `per_target` : liste `[{"path": str, "state": str, "sha256": str|None}]`.
- `can_auto_3way` : `True` si `git apply --3way --check` passerait
  (uniquement consommé par la future UI interactive J12).
- `drift_hint` : `"cosmetic"` / `"semantic"` / `null`.

---

## §4. Verrou et concurrence

Source autoritaire : `docs/260420-patch-system-design.md §5.7`.

> **Decision** : **`flock` obligatoire** sur toutes les operations mutantes
> (`apply`, `rollback`, `refresh`, `record`). Fichier de lock :
> `patches/.lock`.
>
> Source : `docs/260420-patch-system-design.md §5.7`.

### 4.1 Commandes qui prennent le lock

- `apply`
- `rollback`
- `refresh` (stub, le lock est pris même si l'exécution échoue)
- `record` (stub, idem)

### 4.2 Commandes qui ne prennent PAS le lock (cité verbatim §5.7)

> **Read-only operations non verrouillees** : `status`, `describe`,
> `diff`, `list`, `verify --read-only` — l'utilisateur peut consulter
> l'etat pendant qu'un apply tourne.

### 4.3 Comportement du `flock`

Le dispatcher bash `scripts/patch-system` pose un `flock -n` non-bloquant :

```bash
# dans scripts/patch-system (extrait, design §5.7)
exec 9>"${PATCHES_DIR}/.lock"
flock -n 9 || { echo "patch-system: another operation in progress"; exit 1; }
```

Si le lock est déjà détenu :
```
patch-system: another mutating operation is in progress (lock: <path>/.lock)
```
Exit code : `1`. Le fichier `patches/.lock` est créé à la volée si absent.

---

## §5. Niveaux de sévérité

Source autoritaire : `docs/260420-patch-system-design.md §3.2` (types
attendus, severity enum).

> `severity` : enum `BLOCKING | TROMPEUR | COSMETIQUE | INFO`.

Sémantique (convention projet, voir `docs/260418-dual-sensitivity-analysis.md`) :

| Sévérité | Sémantique |
|---|---|
| `BLOCKING` | Anomalie qui casse un flow critique (ex. B1-B4 de l'audit dual-sensitivity). Le skipper rend le vendor inutilisable dans le mode dual-zone. |
| `TROMPEUR` | Wording ou comportement qui induit en erreur l'opérateur, sans casser le flow (ex. `Read .env` → `Read config` dans 12 docs skills). |
| `COSMETIQUE` | Diff visuel pur, pas d'impact fonctionnel. |
| `INFO` | Annotation documentaire, non exécutable. |

---

## §6. Variables d'environnement

Extraits du dispatcher `scripts/patch-system` (lignes 1-22) :

```bash
#!/usr/bin/env bash
# patch-system — bash dispatcher for the Python patch_system package.
...
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PATCH_SYSTEM_ROOT="${PATCH_SYSTEM_ROOT:-${PROJECT_ROOT}}"

# Make scripts/ dir importable so `python3 -m patch_system` resolves.
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
```

| Variable | Défaut | Rôle |
|---|---|---|
| `PATCH_SYSTEM_ROOT` | parent de `scripts/` | Racine super-repo. `$PATCH_SYSTEM_ROOT/patches/series.json` et `$PATCH_SYSTEM_ROOT/vendor/obsidian-wiki/` sont lus par défaut. Surchargeable par les flags top-level `--series` / `--vendor-root`. |
| `PYTHONPATH` | ajoute `scripts/` | Pour que `python3 -m patch_system` résolve le package. Le dispatcher l'exporte automatiquement. |

**Résolution des chemins target** (via `scripts/patch_system/detect.py`
`_resolve_target_path`) : les `path` dans `series.json` sont de la forme
`vendor/<name>/...` ; lors de la résolution, le préfixe `vendor/<name>/` est
strippé et le reste est joint à `vendor_root`. Cela permet à la même entrée
registre de pointer vers un working tree arbitraire (en particulier les
fixtures de test).

---

## §7. Schéma `runtime.json` (J14)

Source autoritaire : `docs/260420-patch-system-design.md §3.3` et
`docs/adr/ADR-0002-registre-runtime-separation.md`. Implémentation :
`scripts/patch_system/runtime.py`.

`patches/runtime.json` est la **config d'exécution** — complémentaire et
séparée du registre logique `series.json` (§2). Elle est **optionnelle** :
absente, les defauts codés en dur s'appliquent.

### 7.1 Structure

```json
{
  "schema_version": "1",
  "defaults": {
    "detection": {
      "strategy": "composite",
      "signals": ["checksum", "git-apply-reverse-check"]
    },
    "apply":    {"method": "git-apply", "args": ["--index", "--whitespace=nowarn"]},
    "rollback": {"method": "git-apply", "args": ["--reverse", "--index"]},
    "drift":    {"mode": "verbose"}
  },
  "overrides": {
    "<record-id>": {
      "apply":    {"method": "patch", "args": ["-p1", "-N"]},
      "rollback": {"method": "patch", "args": ["-p1", "-R"]}
    }
  }
}
```

### 7.2 Clés reconnues

| Clé top-level | Obligatoire | Valeur |
|---|---|---|
| `schema_version` | oui | Chaîne `"1"` (seule version supportée). |
| `defaults` | non | Objet regroupant les sections par défaut. |
| `overrides` | non | Table `{record_id: {section: value, ...}}`. |

**Sections reconnues** dans `defaults[*]` et chaque bloc `overrides[id]` :
`detection`, `apply`, `rollback`, `drift`. Toute autre section (top-level
ou dans un override) déclenche une erreur `RuntimeError_`.

### 7.3 Defaults hardcodés

Si `runtime.json` est absent, les défauts retournés par `default_runtime()`
(verbatim design §3.3) sont :

| Section | Valeur par défaut |
|---|---|
| `detection` | `{"strategy": "composite", "signals": ["checksum", "git-apply-reverse-check"]}` |
| `apply` | `{"method": "git-apply", "args": ["--index", "--whitespace=nowarn"]}` |
| `rollback` | `{"method": "git-apply", "args": ["--reverse", "--index"]}` |
| `drift` | `{"mode": "verbose"}` |

Si `runtime.json` est présent mais sans la section `defaults` pour une
clé donnée, la valeur hardcodée correspondante est utilisée (merge).

### 7.4 Résolution par record

Pour appliquer ou rollback un record `<id>`,
`runtime_mod.resolve_strategy(<id>, runtime)` retourne une copie des
defauts avec les sections de `overrides[<id>]` substituées intégralement
(remplacement par section, pas key-par-key).

**Méthodes `apply.method` supportées**

| Méthode | Effet | Args typiques |
|---|---|---|
| `git-apply` (défaut) | `git apply <args> <patch_file>` depuis `vendor_root`. | `["--index", "--whitespace=nowarn"]` |
| `patch` | `patch <args> < <patch_file>` depuis `vendor_root`. Vérifie la présence du binaire `patch(1)` ; absence → echec avec message `patch(1) not available, fallback impossible`. | `["-p1", "-N"]` (apply), `["-p1", "-R"]` (rollback) |

### 7.5 Exemple livré — override B3 vers `patch(1)`

`patches/runtime.json` (livré jalon J14) :
```json
{
  "schema_version": "1",
  "overrides": {
    "b3-vendor-env-remove": {
      "apply":    {"method": "patch", "args": ["-p1", "-N"]},
      "rollback": {"method": "patch", "args": ["-p1", "-R"]}
    }
  }
}
```

Raison : la target `vendor/obsidian-wiki/.env` est gitignored dans le
vendor repo ; `git apply --index` refuse avec `error: <file>: does not
exist in index`. Le binaire `patch(1)` n'a pas cette contrainte. Voir
`patches/README.md §« Contourner les fichiers gitignored »` pour la
discussion mainteneur.

### 7.6 Conditions d'erreur

`runtime_mod.load_runtime` lève `RuntimeError_` dans les cas suivants :

- Fichier non JSON ou racine non objet.
- Clé top-level inconnue (autre que `schema_version`, `defaults`,
  `overrides`).
- `schema_version` ≠ `"1"`.
- `defaults` ou `overrides` pas un objet.
- Section inconnue dans `defaults` ou dans un bloc `overrides[id]`.
- Bloc `overrides[id]` pas un objet.
