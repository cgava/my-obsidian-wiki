# Recettes — patch-system

Recettes courtes et indépendantes pour les tâches courantes. Chaque recette
suppose que vous connaissez déjà les concepts (voir
[explanation.md](./explanation.md)) et la CLI (voir
[reference.md](./reference.md)). Si vous débutez, passez d'abord par le
[tutoriel](./tutorial.md).

> **Pré-requis de toutes les recettes** : `PATCH_SYSTEM_ROOT` pointe sur la
> racine du super-repo (contient `patches/series.json` et
> `vendor/obsidian-wiki/`). Par défaut, le dispatcher
> `scripts/patch-system` utilise `$(pwd)` — lancer depuis la racine du repo
> suffit.

---

## Comment inspecter l'état global des patches ?

Deux commandes complémentaires :

1. `list` — inventaire statique du **registre** (`series.json`), indépendant
   du working tree.
2. `status` — inspection **dynamique** du working tree, colonne `STATE`
   calculée par la détection composite.

```bash
./scripts/patch-system list
./scripts/patch-system status
```

Lecture de la sortie `status` (colonnes, [reference.md §1.2](./reference.md#12-status)) :

- `ID` : identifiant du record (clé stable, format `<code-audit>-<slug>`)
- `SEV` : sévérité (BLOCKING, TROMPEUR, COSMETIQUE, INFO)
- `TARGETS` : fraction `N/M` des targets dans un état cohérent avec
  l'agrégation
- `STATE` : état agrégé (`clean` / `patched` / `partial` / `dirty` / `absent`)
- `ORDER` : clé d'ordonnancement

Pour filtrer sur les records problématiques uniquement :

```bash
./scripts/patch-system status --only-failing
```

---

## Comment appliquer un patch individuel ?

```bash
./scripts/patch-system apply <id>
```

Vérifier d'abord en `--dry-run` (aucune écriture) :

```bash
./scripts/patch-system apply <id> --dry-run
```

Puis, une fois que le dry-run indique `OK`, relancer sans `--dry-run`. La
sortie canonique en cas de succès (design §4.3) :

```
[<id>] clean -> applying...
  target(s) patched -> state=patched
  registry updated: last_result=patched last_applied=<ISO-UTC>
```

Confirmer que le state est passé à `patched` :

```bash
./scripts/patch-system status --id=<id>
```

Exit codes : `0` succès, `1` échec opérationnel (working tree `dirty` /
`partial` / `absent` sans `--interactive`).

---

## Comment rollback un patch ?

```bash
./scripts/patch-system rollback <id>
```

**Garde-fou** : `rollback` refuse si `last_result != "patched"` dans le
registre. Message observé en cas de refus :

```
[<id>] refuse to rollback : last_result='clean' (expected 'patched').
  If you know what you're doing, rerun with --force (jalon 14, not yet implemented).
```

Exit code du refus : `1`.

Si l'état enregistré est `patched`, `rollback` invoque `git apply --reverse
--index` et met à jour le registre (`last_result=clean`).

Pour un rollback à blanc :

```bash
./scripts/patch-system rollback <id> --dry-run
```

> Source : docs/260420-patch-system-design.md §7 pt 7 (rollback — garde-fou
> `last_result == patched`).

---

## Comment diagnostiquer un état `partial` ou `dirty` ?

Étape 1 : localiser le record problématique :

```bash
./scripts/patch-system status --only-failing
```

Étape 2 : regarder **par target** :

```bash
./scripts/patch-system describe <id>
```

La sortie détaille chaque target avec `baseline` / `patched` / `observed`
(sha256) et son `state` individuel. Si un target est `clean` et un autre
`dirty`, l'agrégé est `partial`.

Étape 3 : lire le patch lui-même pour comprendre ce qui est attendu :

```bash
./scripts/patch-system diff <id>
```

Options de résolution :

- Si le drift est **cosmétique** (blank-line upstream, re-indentation) : la
  détection composite aura déjà promu l'état en `clean` ou `patched` (voir
  [reference.md §3](./reference.md#3-états-de-détection)). Pas d'action
  requise.
- Si le drift est **sémantique** (hunk rejeté) : utiliser `--interactive`,
  `--force` ou `--auto-3way` (voir recette « Comment arbitrer un conflit
  (mode interactif, `--force`, `--auto-3way`) ? » plus bas).
- Si les SHAs enregistrés sont simplement désuets après un
  `git submodule update` : voir recette « Comment rafraîchir les SHAs
  après un `git submodule update` ? » (`refresh <id>`).
- Si vous voulez juste ignorer : laissez tel quel, le record reste `partial`
  au `status`, rien ne se cassera.

> Source : docs/260420-patch-system-design.md §4.2 (menu d'arbitrage) et
> §5.5 (escalade vs 3-way auto).

---

## Comment lire le contenu d'un patch avant de l'appliquer ?

```bash
./scripts/patch-system diff <id>
```

Par défaut, coloration ANSI si stdout est un TTY (vert = ajouts, rouge =
suppressions, cyan = headers `@@`). Pour supprimer la couleur (pipe, fichier) :

```bash
./scripts/patch-system diff <id> --no-color
```

Pour n'obtenir que **la liste des fichiers touchés** (utile pour `grep`) :

```bash
./scripts/patch-system diff <id> --targets-only
```

---

## Comment comprendre `series.json` ?

`patches/series.json` est le **registre logique** : la source de vérité sur
« ce qui doit être patché ». Il contient un tableau `records[]`, chacun
décrivant un patch (id, order, status, severity, title, patch_file,
patch_sha256, targets[], last_applied, last_result).

Schéma exhaustif + exemple : [reference.md §2](./reference.md#2-schéma-seriesjson-v1).

Pour ne pas se noyer, `describe` affiche le record en format lisible :

```bash
./scripts/patch-system describe <id>
./scripts/patch-system describe <id> --json   # pour du scripting
```

> Source : docs/260420-patch-system-design.md §3.2 (schéma complet) et ADR-0002
> (séparation `series.json` / `runtime.json`).

---

## Que faire si `git apply` échoue ?

`apply` imprime le stderr de `git apply` en cas d'échec. Exemple de sortie :

```
[<id>] clean -> git apply FAILED
  error: patch failed: <file>:<line>
  error: <file>: patch does not apply
```

Exit code : `1`.

Marche à suivre :

1. Vérifier que le vendor est un dépôt git et que le working tree n'a pas été
   pollué par une édition manuelle :
   ```bash
   (cd vendor/obsidian-wiki && git status)
   ```
   Si des fichiers sont modifiés hors du scope du patch, c'est sans doute
   l'origine du conflit.
2. Relancer un `status` — la détection composite va arbitrer entre
   `cosmetic` (acceptable) et `semantic` (conflit réel). Regarder
   `drift_hint` dans `describe --json`.
3. Si le conflit est sémantique, trois options :
   - Éditer manuellement le fichier cible pour qu'il revienne à une baseline
     compatible, puis retry `apply`.
   - Régénérer le patch (`record`, J12) depuis l'état voulu (pas encore
     implémenté).
   - Utiliser `--interactive`, `--force` ou `--auto-3way` (voir recette
     « Comment arbitrer un conflit (mode interactif, `--force`,
     `--auto-3way`) ? » plus bas).
4. Les exit codes UNIX retournés (design §4.1) : `0` succès, `1` échec
   opérationnel, `2` argv invalide, `3` registre invalide.

> Source : docs/260420-patch-system-design.md §4.1 (exit codes) + §4.3
> (messages-types) + §5.5 (escalade drift).

---

## Comment filtrer `list` par statut de cycle de vie ?

```bash
./scripts/patch-system list --status=active
./scripts/patch-system list --status=disabled
./scripts/patch-system list --status=obsolete
```

Le `status` ici désigne le **statut du cycle de vie** du record (`active` /
`disabled` / `obsolete`), **pas** l'état de détection. Voir
[reference.md §2](./reference.md#2-schéma-seriesjson-v1).

---

## Comment obtenir une sortie JSON pour scripting ?

Toutes les commandes lecture supportent `--json` :

```bash
./scripts/patch-system list --json
./scripts/patch-system status --json
./scripts/patch-system describe <id> --json
```

Sortie : JSON valide sur stdout, exit code `0` si succès. `--json` implique
pas de coloration. À parser avec `jq` ou équivalent.

---

## Comment détecter qu'une opération mutante est en cours ?

Le dispatcher pose un `flock` non-bloquant sur `patches/.lock` pour
`apply` / `rollback` / `refresh` / `record`. Si un autre processus détient
déjà le lock :

```
patch-system: another mutating operation is in progress (lock: <path>/.lock)
```

Exit code : `1`.

Les commandes read-only (`list`, `status`, `describe`, `diff`, `verify`) ne
prennent pas le lock — elles peuvent tourner pendant qu'un apply est en
cours.

> Source : docs/260420-patch-system-design.md §5.7 (verrou `flock`
> obligatoire sur les opérations mutantes).

---

## Comment vérifier l'intégrité et le drift du registre ?

Depuis le jalon J9, `verify` exécute trois contrôles par record —
intégrité (sha-256 du `.patch`), drift (vendor baseline + per-target),
cohérence (targets existent). Voir
[reference.md §1.8](./reference.md#18-verify-j9).

```bash
./scripts/patch-system verify
```

Pour intégrer à un pipeline CI (échoue au premier drift, pas juste aux
failures dures) :

```bash
./scripts/patch-system verify --strict
```

Pour exploiter la sortie en script :

```bash
./scripts/patch-system verify --json | jq '.summary'
```

Exit codes utilisables :
- `0` : tout OK (ou uniquement drift en non-strict).
- `1` : intégrité mismatch, target manquante, ou drift avec `--strict`.
- `3` : registre invalide (schéma).

---

## Comment rafraîchir les SHAs après un `git submodule update` ?

Après un pull du submodule vendor, les `baseline_sha256` enregistrés
peuvent pointer vers un ancien état upstream. `refresh <id>` (J10)
recalcule les SHAs depuis le vendor courant, selon l'état composite
du record :

- Si l'état est `clean` → seul `baseline_sha256` est refreshé.
- Si l'état est `patched` → seul `patched_sha256` est refreshé.
- Tout autre état (`dirty`, `partial`, `absent`) → refusé ; résoudre
  d'abord par `apply` ou `rollback`.

**Procédure recommandée** :

```bash
# 1. Constater le drift
./scripts/patch-system verify

# 2. Aperçu des changements sans écrire
./scripts/patch-system refresh <id> --dry-run

# 3. Si OK, appliquer (passer --yes pour sauter la confirmation)
./scripts/patch-system refresh <id>
```

Chaque refresh écrit un événement dans
`patches/history/<order>-history.jsonl` avec l'ancien et le nouveau
SHA par target — audit trail utilisable par `describe`.

Détails des flags et exit codes :
[reference.md §1.9](./reference.md#19-refresh-j10).

---

## Comment ré-appliquer toute la série après un pull du submodule ?

Le cas canonique (ADR-0001 : vendor submodule pristine, état patched
régénéré à la demande). Depuis J13, `apply --all` itère tous les records
`active` par `order` croissant :

```bash
./scripts/patch-system apply --all
```

Pour arrêter au premier échec plutôt que de continuer :

```bash
./scripts/patch-system apply --all --stop-on-fail
```

Pour pré-voir ce qui s'appliquerait sans écrire :

```bash
./scripts/patch-system apply --all --dry-run
```

Le résumé de fin de run prend la forme :
```
apply --all: <N> applied, <M> skipped, <K> failed
```

Les records déjà dans l'état `patched` sont comptés dans `skipped`
(idempotence). Un unique `flock` est posé pour toute la run ; les
lectures (`list`, `status`, `verify`) restent utilisables en parallèle.

Détails : [reference.md §1.5](./reference.md#15-apply).

---

## Comment tout désappliquer ?

Depuis J13, `rollback --all` pop l'ensemble par ordre **décroissant** de
`order` :

```bash
./scripts/patch-system rollback --all
```

Les records dont `last_result != "patched"` sont skippés avec un message
explicite — cela protège contre un rollback sur un record qui n'a jamais
été appliqué (garde-fou `last_result`, déjà présent en J7, étendu à
`--all`).

Résumé de fin :
```
rollback --all: <N> reverted, <M> skipped, <K> failed
```

Pour interrompre au premier échec :
```bash
./scripts/patch-system rollback --all --stop-on-fail
```

---

## Comment arbitrer un conflit (mode interactif, `--force`, `--auto-3way`) ?

Lorsque `status` remonte un record en `dirty` ou `partial`, trois leviers
d'arbitrage sont disponibles depuis J12-J14 :

**Option 1 — tenter une fusion 3-way automatique** (J14, opt-in) :
```bash
./scripts/patch-system apply <id> --auto-3way
```
Tente `git apply --3way --index` avant d'escalader. Sur succès, continue
comme un apply normal. Sur échec, retombe sur la logique interactive ou
`--yes`.

**Option 2 — menu interactif à la `etc-update`** (J12) :
```bash
./scripts/patch-system apply <id> --interactive
```
Affiche pour chaque target le menu :
```
Patch <NNNN> target <path> is <state>.
   y  apply — force l'application (ecrase les modifs locales si conflit)
   n  skip  — laisse la cible telle quelle, status sera 'dirty'
   s  show  — affiche le diff 3-points (pristine | local | patched)
   d  diff  — affiche seulement le diff patch->local
   3  3way  — tente `git apply --3way` (merge automatique)
   r  refresh — met a jour baseline_sha256 depuis l'etat local courant
   q  quit  — arrete le run, les patches deja traites restent appliques
   ?  help  — re-affiche ce menu
Choice [y/n/s/d/3/r/q/?] (default n):
```
Entrée vide = `n` (skip, défaut conservateur). `q` interrompt la run
sans rollback des patches déjà traités.

**Option 3 — écrasement brut** (J14, batch non-interactif) :
```bash
./scripts/patch-system apply <id> --force
```
`--force` équivaut à `y` implicite sur tout état ambigu, sans prompt.
À utiliser en CI quand on sait que l'écrasement est acceptable.

**Interdits** : `--yes` et `--interactive` sont mutuellement exclusifs.
Tenter les deux ensemble imprime :
```
[<id>] invalid flags: --yes and --interactive are mutually exclusive.
```
et sort en exit `1`.

Sans aucun flag d'arbitrage, les états `dirty` / `partial` sont refusés
avec le message canonique §4.3 :
```
[<id>] <state> -> ambiguous state.
  ERROR: --yes mode forbids interactive arbitration.
  Rerun with --interactive to resolve, or --force to overwrite.
```

Détails du menu et exit codes :
[reference.md §1.5](./reference.md#15-apply).

---

## Comment appliquer un patch sur un fichier gitignored (override `runtime.json`) ?

Certains targets (ex. `vendor/obsidian-wiki/.env`) sont gitignored dans
le vendor repo. `git apply --index` les refuse avec
`error: <file>: does not exist in index`. Depuis J14, `patches/runtime.json`
permet de router un record spécifique vers `patch(1)`, qui n'a pas cette
contrainte.

**Étape 1** : créer ou éditer `patches/runtime.json` :

```json
{
  "schema_version": "1",
  "overrides": {
    "<record-id>": {
      "apply":    {"method": "patch", "args": ["-p1", "-N"]},
      "rollback": {"method": "patch", "args": ["-p1", "-R"]}
    }
  }
}
```

**Étape 2** : vérifier que `patch(1)` est disponible (`which patch`).
Son absence produit un échec explicite `patch(1) not available,
fallback impossible`, exit `1`.

**Étape 3** : appliquer normalement :
```bash
./scripts/patch-system apply <record-id>
```

Le dispatcher détecte l'override, invoque `patch -p1 -N` au lieu de
`git apply --index`. `patch -N` refuse un ré-apply idempotent (aligné
avec la sémantique d'idempotence du framework).

Le dépôt livre un exemple `patches/runtime.json` qui active ce routage
pour `b3-vendor-env-remove`. Schéma complet :
[reference.md §7](./reference.md#7-schéma-runtimejson-j14).
Guide mainteneur + discussion du trade-off : `patches/README.md`
(section « Contourner les fichiers gitignored »).
