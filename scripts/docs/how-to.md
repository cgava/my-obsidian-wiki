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

Étape 4 : décider. En jalon J8 actuel, trois options :

- Si le drift est **cosmétique** (blank-line upstream, re-indentation) : la
  détection composite aura déjà promu l'état en `clean` ou `patched` (voir
  [reference.md §3](./reference.md#3-états-de-détection)). Pas d'action
  requise.
- Si le drift est **sémantique** (hunk rejeté) et qu'un seul hunk est
  en cause : `--interactive` ou `--force` arbitreraient — **non encore
  implémentés** (jalons 12/14). En attendant, correction manuelle dans le
  working tree puis `refresh` (J10) quand disponible.
- Si vous voulez juste ignorer : laissez tel quel, le record reste `partial`
  au `status`, rien ne se cassera.

> Source : docs/260420-patch-system-design.md §4.2 (mode interactif à venir
> — J12) et §5.5 (escalade vs 3-way auto).

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
3. Si le conflit est sémantique : pas d'auto-résolution en J8. Options :
   - Éditer manuellement le fichier cible pour qu'il revienne à une baseline
     compatible, puis retry `apply`.
   - Régénérer le patch (`record`, J11) depuis l'état voulu (pas encore
     implémenté).
   - Attendre les jalons 12 (mode interactif, menu y/n/s/d/3/r/q/?) et 14
     (`--force` + fallback `patch(1)` + `--auto-3way`).
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
