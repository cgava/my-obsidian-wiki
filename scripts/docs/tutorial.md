# Tutoriel — prendre en main le patch-system en 15 minutes

Ce tutoriel vous guide à travers **un cycle complet** d'utilisation du
patch-system sur un vendor de démonstration (les fixtures `vendor-mini`). À la
fin, vous saurez :

- inventorier les patches (`list`)
- inspecter leur état courant (`status`, `describe`)
- lire le contenu d'un patch (`diff`)
- appliquer un patch (`apply`)
- vérifier l'idempotence (un deuxième `apply` ne refait rien)
- annuler (`rollback`)

> Ce tutoriel est délibérément mécanique : on suit une procédure qui marche.
> Les **pourquoi** sont dans [explanation.md](./explanation.md) ; les flags
> exhaustifs sont dans [reference.md](./reference.md). Résistez à l'envie de
> vous écarter du chemin — c'est un parcours d'apprentissage, pas une recette.

## Prérequis

- `python3` ≥ 3.10 (vérifiez avec `python3 --version`)
- `git` (le moteur de détection/apply délègue à `git apply`)
- Être dans le workspace `my-obsidian-wiki/` (le dispatcher
  `scripts/patch-system` y est exécutable)
- Un terminal Unix (les exemples utilisent bash)

## Étape 0 — Mise en place du bac à sable

Les fixtures de test sont sous `tests/fixtures/`. Le patch-system attend le
layout canonique `patches/series.json` + `patches/*.patch` + `vendor/obsidian-wiki/`
(voir [reference.md §6](./reference.md#6-variables-denvironnement)). On va
assembler un workspace éphémère qui respecte ce layout :

```bash
TMPROOT=$(mktemp -d -t patch-doc-XXXX)
mkdir -p "$TMPROOT/patches" "$TMPROOT/vendor"
cp tests/fixtures/series.json "$TMPROOT/patches/"
cp tests/fixtures/patches/*.patch "$TMPROOT/patches/"
cp -r tests/fixtures/vendor-mini "$TMPROOT/vendor/obsidian-wiki"

# Le moteur apply/rollback délègue à `git apply --index` → le vendor
# doit être un dépôt git. On en crée un éphémère pour le tutoriel.
(cd "$TMPROOT/vendor/obsidian-wiki" \
  && git init -q \
  && git add -A \
  && git -c user.email=x -c user.name=x commit -q -m snap)

# Point d'entrée : PATCH_SYSTEM_ROOT. Toutes les commandes liront
# $PATCH_SYSTEM_ROOT/patches/series.json + $PATCH_SYSTEM_ROOT/vendor/obsidian-wiki/.
export PATCH_SYSTEM_ROOT="$TMPROOT"
```

**Observation** : `PATCH_SYSTEM_ROOT` est la variable d'environnement qui
indique au dispatcher où trouver `patches/` et `vendor/obsidian-wiki/`. En
production, cette variable pointe sur la racine du super-repo ; ici, elle
pointe sur notre bac à sable.

## Étape 1 — Inventorier les patches avec `list`

```bash
./scripts/patch-system list
```

Sortie observée :

```
   1  t0001-readme-add-section                  COSMETIQUE   active    - README — add local notes section
   2  t0002-cmd1-fix-typo                       COSMETIQUE   active    - cmd1 — expand cmd to command in output
   3  t0003-cmd2-drifted                        TROMPEUR     active    - cmd2 — reword echo line, vendor has cosmetic drift upstream
   4  t0004-cmd2-semantic-drift                 TROMPEUR     active    - cmd2 — semantic drift: one hunk rejected after upstream rename
```

**Observation** : `list` affiche **ce qui existe au registre** (`series.json`),
indépendamment de ce qui est appliqué. Les colonnes : `order` (clé
d'ordonnancement), `id` (clé stable), `severity` (BLOCKING / TROMPEUR /
COSMETIQUE / INFO), `status` (active / disabled / obsolete), `title`.

## Étape 2 — Vérifier l'état courant avec `status`

```bash
./scripts/patch-system status
```

Sortie observée :

```
ID                                 SEV        TARGETS   STATE      ORDER
t0001-readme-add-section           COSMETIQUE  1/1       clean      1
t0002-cmd1-fix-typo                COSMETIQUE  1/1       clean      2
t0003-cmd2-drifted                 TROMPEUR   1/1       clean      3
t0004-cmd2-semantic-drift          TROMPEUR   0/1       partial    4

Vendor baseline: not-recorded
Summary: 4 active / 3 clean / 1 partial
```

**Observation** : contrairement à `list`, `status` **inspecte le working tree**
et calcule l'état **réel** de chaque patch par la détection composite :

- `clean` : le patch n'est pas appliqué, il le serait sans conflit
- `partial` : une partie des hunks s'appliquerait, l'autre non
- `patched`, `dirty`, `absent` : voir [reference.md §3](./reference.md#3-états-de-détection)

Les fixtures sont conçues pour exhiber ces cas : t0004 est en `partial` parce
qu'un de ses hunks fait référence à une ligne upstream qui n'existe pas dans
le vendor.

## Étape 3 — Approfondir un record avec `describe`

```bash
./scripts/patch-system describe t0001-readme-add-section
```

Sortie observée :

```
id            : t0001-readme-add-section
order         : 1
status        : active
severity      : COSMETIQUE
title         : README — add local notes section
audit_ref     : tests/fixtures/README.md#0001
patch_file    : 0001-readme-add-section.patch
patch_sha256  : c5ddbe714e1e5a024c7025226525e995e1c6b617df2d6f0ecd3a84a36aacbd58
last_applied  : (never)
last_result   : (never)
current state : clean
can_auto_3way : False
targets :
  - path       : vendor/obsidian-wiki/README.md
    baseline   : 8dfa1bea1fad11f744c49a033b15d6523c4da143fa37ae5c99289b9c20cb930d
    patched    : 2d3f15457d3a07c545335d6ff73c1c8b1d8d65441120b94832eb944019d077c0
    observed   : 8dfa1bea1fad11f744c49a033b15d6523c4da143fa37ae5c99289b9c20cb930d
    state      : clean
history       : (no events — not yet externalised in this repo)
```

**Observation** : `describe` donne la fiche complète d'**un** record — toutes
les métadonnées du registre, plus l'état live par target. Les trois SHA par
target (`baseline`, `patched`, `observed`) pilotent la détection (§3 reference).
`last_applied` / `last_result` sont `(never)` tant que le patch n'a pas été
joué — ils seront mis à jour par `apply`.

## Étape 4 — Lire le patch lui-même avec `diff`

```bash
./scripts/patch-system diff t0001-readme-add-section --no-color
```

Sortie observée :

```
Description: README — add local notes section
 Add a "Local notes" section to the vendor README to document
 that the patch-system fixtures tree has been customised.
Origin: vendor
Author: test-fixture <test@example.invalid>
Forwarded: no
Last-Update: 2026-04-20
X-Audit-Ref: tests/fixtures/README.md#0001
X-Severity: COSMETIQUE
X-Baseline-Sha256: 8dfa1bea1fad11f744c49a033b15d6523c4da143fa37ae5c99289b9c20cb930d
X-Patched-Sha256: 2d3f15457d3a07c545335d6ff73c1c8b1d8d65441120b94832eb944019d077c0
---
--- a/README.md
+++ b/README.md
@@ -1,3 +1,7 @@
 # vendor-mini

 Minimal fixture simulating vendor/obsidian-wiki pristine.
+
+## Local notes
+
+Patched by patch-system 0001.
```

**Observation** : le fichier `.patch` est auto-suffisant. Il contient un
**header DEP-3** (lignes `Description:`, `Origin:`, `Forwarded:`, etc.) enrichi
de champs `X-*` (audit, sévérité, SHA baseline/patched), séparé du diff unifié
par `---`. Ce format est lisible par un humain, parseable par `git apply`, et
forwardable dans un tracker upstream tel quel.

## Étape 5 — Appliquer le patch avec `apply`

D'abord un coup d'essai à blanc (sans écrire sur disque) :

```bash
./scripts/patch-system apply t0001-readme-add-section --dry-run
```

Sortie observée :

```
[t0001-readme-add-section] clean -> would apply 0001-readme-add-section.patch
  [dry-run] git apply --check --index 0001-readme-add-section.patch  OK
  [dry-run] no write performed
```

**Observation** : le `--dry-run` invoque `git apply --check`. Rien n'est
modifié, ni le working tree ni le registre.

Maintenant le vrai apply :

```bash
./scripts/patch-system apply t0001-readme-add-section
```

Sortie observée :

```
[t0001-readme-add-section] clean -> applying...
  target(s) patched -> state=patched
  registry updated: last_result=patched last_applied=2026-04-20T14:33:18Z
```

**Observation** : la transition d'état est explicite (`clean -> applying... ->
state=patched`). Le registre `patches/series.json` est mis à jour en place
(`last_result=patched`, `last_applied=<ISO-UTC>`). Le working tree du vendor
est modifié mais **pas committé** — c'est un choix de design (voir
[explanation.md §6](./explanation.md#6-trade-offs-assumés)).

## Étape 6 — Vérifier l'effet avec un nouveau `status`

```bash
./scripts/patch-system status
```

Sortie observée (extrait) :

```
ID                                 SEV        TARGETS   STATE      ORDER
t0001-readme-add-section           COSMETIQUE  1/1       patched    1
...
Summary: 4 active / 1 patched / 2 clean / 1 partial
```

**Observation** : t0001 est passé de `clean` à `patched`. Les autres records
n'ont pas bougé. La colonne `TARGETS` indique `1/1` — 1 target sur 1 est dans
l'état `patched`.

## Étape 7 — Constater l'idempotence

Relançons `apply` sur le même record :

```bash
./scripts/patch-system apply t0001-readme-add-section
```

Sortie observée :

```
[t0001-readme-add-section] patched -> skip (already applied)
```

**Observation** : le moteur **détecte** que le patch est déjà appliqué et
n'appelle pas `git apply`. C'est le principe d'idempotence (design §5 detect
composite). Vous pouvez relancer `apply` autant de fois que vous voulez — il
ne refera rien.

## Étape 8 — Annuler avec `rollback`

```bash
./scripts/patch-system rollback t0001-readme-add-section
```

Sortie observée :

```
[t0001-readme-add-section] patched -> reversing...
  target(s) reverted -> state=clean
  registry updated: last_result=clean last_applied=2026-04-20T14:34:45Z
```

**Observation** : `rollback` invoque `git apply --reverse --index`, met à jour
le registre (`last_result=clean`), et revient à l'état pré-apply.

## Étape 9 — Le garde-fou du rollback

Si on essaie de `rollback` une seconde fois :

```bash
./scripts/patch-system rollback t0001-readme-add-section
```

Sortie observée :

```
[t0001-readme-add-section] refuse to rollback : last_result='clean' (expected 'patched').
  If you know what you're doing, rerun with --force (jalon 14, not yet implemented).
```

Exit code : `1`.

**Observation** : `rollback` refuse si `last_result != "patched"`. Ce garde-fou
protège contre un rollback accidentel d'un patch qui n'est pas dans l'état
supposé. Le flag `--force` (design §4.1) permettra un jour d'outrepasser, mais
il n'est pas encore implémenté (jalon 14).

## Étape 10 — Régénérer toute la série avec `apply --all`

Jusqu'ici vous avez joué avec **un record**. En production, le cas
canonique est différent : après un `git submodule update`, le vendor est
reset à l'upstream pristine, et **tous** les patches locaux doivent être
ré-appliqués. D'où :

```bash
./scripts/patch-system apply --all
```

Sortie typique sur notre fixture (après avoir rollback t0001 à l'étape 8,
les autres records sont toujours `clean`) :

```
[t0001-readme-add-section] clean -> applying...
  target(s) patched -> state=patched
  registry updated: last_result=patched last_applied=2026-04-20T14:36:02Z
[t0002-cmd1-fix-typo] clean -> applying...
  target(s) patched -> state=patched
  registry updated: last_result=patched last_applied=2026-04-20T14:36:02Z
[t0003-cmd2-drifted] clean -> applying...
  target(s) patched -> state=patched
  registry updated: last_result=patched last_applied=2026-04-20T14:36:02Z
[t0004-cmd2-semantic-drift] partial -> ambiguous state.
  ERROR: --yes mode forbids interactive arbitration.
  Rerun with --interactive to resolve, or --force to overwrite.
apply --all: 3 applied, 0 skipped, 1 failed
```

**Observation** : les records sont joués par `order` croissant. Un unique
`flock` couvre toute la run. Sans `--stop-on-fail`, la boucle continue et
cumule les erreurs ; le résumé final distingue `applied` / `skipped`
(idempotence) / `failed`. L'exit code est `1` parce que `t0004` a échoué.
Voir [reference.md §1.5](./reference.md#15-apply) pour tous les flags.

En symétrique, `rollback --all` pop la pile par ordre décroissant :

```bash
./scripts/patch-system rollback --all
```

Les records dont `last_result != "patched"` sont silencieusement skippés
dans ce mode batch (protection équivalente au garde-fou simple de
l'étape 9).

## Conclusion

Vous savez maintenant :

- inventorier le registre avec `list`
- lire l'état courant avec `status` et `describe`
- inspecter un patch avec `diff`
- appliquer un patch (avec et sans `--dry-run`)
- vérifier l'idempotence d'un deuxième `apply`
- annuler avec `rollback`, et comprendre le garde-fou `last_result`
- régénérer toute la série avec `apply --all` (et désempiler avec
  `rollback --all`)

Prochaines étapes :

- Besoin d'une procédure précise ? → [how-to.md](./how-to.md)
- Besoin d'un flag, d'un exit code, d'un détail du schéma ? → [reference.md](./reference.md)
- Envie de comprendre **pourquoi** l'outil est conçu comme ça ? → [explanation.md](./explanation.md)

## Nettoyage

```bash
rm -rf "$TMPROOT"
unset PATCH_SYSTEM_ROOT
```
