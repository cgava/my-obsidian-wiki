# Explication — patch-system

Discussion conceptuelle des choix de design. Pour la procédure, lire
[how-to.md](./how-to.md) ; pour les flags, lire
[reference.md](./reference.md). Ce fichier répond à la question
**pourquoi** — il ne prescrit rien.

---

## §1. Le problème : vendor non-forkable

Le repo `my-obsidian-wiki` intègre `vendor/obsidian-wiki` comme submodule
git, tracké sur un remote upstream sur lequel nous **n'avons pas les droits
de push**. L'audit `docs/260418-dual-sensitivity-analysis.md` a identifié
des anomalies :

- 4 anomalies **bloquantes** (B1-B4) qui cassent le mode dual-zone.
- ~12 occurrences d'un wording **trompeur** `Read .env` (p2-read-dotenv).
- ~6 occurrences d'un pattern `_raw/ inside vault` trompeur
  (p2-raw-in-vault).

Le problème : comment maintenir ces corrections **locales** sans
- les perdre à chaque `git pull` upstream du submodule,
- les voir se mélanger avec l'historique upstream dans un `git log`,
- forker l'upstream (impossible — pas les droits),
- coller des rustines ad-hoc non documentées qu'un successeur ne saurait
  ré-appliquer.

**La décision structurante est l'ADR-0001** (citée verbatim) :

> **Nous retenons l'option (a) : submodule git + regeneration deterministe.**
>
> Concretement :
> - `vendor/obsidian-wiki` reste un `git submodule` classique, pointant vers
>   un commit de l'upstream. `git -C vendor/obsidian-wiki log` = historique
>   upstream pur, sans modifications locales.
> - Les patches locaux sont stockes dans le super-repo sous `patches/`
>   (`series.json` + `runtime.json` + `*.patch` avec header DEP-3 enrichi).
> - Les patches ne sont **jamais** commites dans le submodule. Apres un
>   `git submodule update`, le working tree du submodule est reset a
>   l'upstream ; `patch-system apply --all` regenere l'etat patched.
>
> Source : `docs/adr/ADR-0001-vendor-submodule-pristine.md` §Décision.

Autrement dit : le **working tree patched est un produit dérivé**, pas un
état persistant. Il se régénère à la demande à partir des sources de
vérité (submodule upstream pristine + `patches/`).

---

## §2. Les principes du design

Le design doc §1 les énonce. Cinq principes portent tout le reste :

### 2.1 Self-documenting

Chaque patch porte sa description complète (contexte, impact, référence
audit). Citation design §3.4 :

> Le `.patch` conserve un header DEP-3 + champs `X-*` pour les extensions
> (voir §5.4 pour l'arbitrage strict vs enrichi).
>
> Source : `docs/260420-patch-system-design.md §3.4`.

Concrètement, le fichier `.patch` contient un header DEP-3 (`Description`,
`Origin`, `Forwarded`, `Last-Update`, etc.) + des champs `X-*` spécifiques
(`X-Audit-Ref`, `X-Severity`, `X-Baseline-Sha256`, `X-Patched-Sha256`),
suivi d'un `---` séparateur, puis du diff unifié. Le fichier est
auto-suffisant : copier-coller dans un bug tracker suffit à communiquer
l'anomalie et sa correction.

### 2.2 Idempotent

Un `apply` sur un patch déjà appliqué est un no-op explicite (voir
design §4.3 cité verbatim) :

> **Detection deja applique** (idempotence) :
> ```
> [b1-wiki-ingest-raw-fallback] patched -> skip (already applied)
> ```
>
> Source : `docs/260420-patch-system-design.md §4.3`.

C'est vital : le patch-system est destiné à être **rejoué fréquemment**
(après chaque `git submodule update`, après chaque clone, en CI). Chaque
invocation doit converger vers l'état souhaité sans effet de bord.

### 2.3 Interactif par défaut, automatisable en opt-in

Cité design §5.5 :

> **Decision** : **escalade a l'utilisateur par defaut** quand `git apply
> --check` echoue. Le 3-way n'est jamais silencieux. Un dial `--auto-3way`
> (opt-in explicite) permet de le tenter et d'accepter son resultat sans
> prompt — destine aux environnements CI ou le prompt n'a pas de sens.
>
> Source : `docs/260420-patch-system-design.md §5.5`.

Le principe est celui de la **surprise minimale** : un outil qui patche
du code ne devrait pas modifier silencieusement la sémantique de la
correction. Le mode interactif (J12) + `--force` / `--auto-3way` (J14)
donnent à l'opérateur le contrôle explicite de chaque arbitrage.

### 2.4 Versatile

Ajouter une anomalie à corriger = éditer le registre, pas le moteur.
Chaque record est une donnée dans `series.json`, pas un hook de code. Le
moteur est générique : il applique via `git apply --index`, détecte via
sha256 + `git apply --check`, invariant vis-à-vis du contenu sémantique
de chaque patch.

### 2.5 Réversible

Chaque patch peut être rollback via `git apply --reverse --index`. Le
garde-fou `last_result == "patched"` protège d'un rollback
accidentel d'un patch jamais appliqué (ou appliqué hors du registre).

---

## §3. Le modèle de détection composite

Pourquoi pas juste sha256 ? Pourquoi pas juste `git apply --check` ?
**Parce que les deux ratent des cas pratiques**.

### 3.1 sha256 seul ne suffit pas

Un `git pull` upstream qui n'ajoute qu'une ligne blanche en tête de
fichier casse le sha256 — mais le patch s'appliquerait toujours sans
conflit. Classer ce cas comme `dirty` demanderait une intervention
humaine pour un changement cosmétique trivial.

### 3.2 `git apply --check` seul ne suffit pas

Sur un working tree déjà patché, `git apply --check` (forward) échoue
— comme sur un working tree dirty. Les deux cas sont pourtant
diamétralement opposés (l'un a déjà fait le travail, l'autre doit
l'encore faire).

### 3.3 La combinaison — cité verbatim design §5 (via
`scripts/patch_system/detect.py` docstring, aligné §5.5)

> Composite state rules (jalon 5) :
>
> - sha-agg is ``clean``/``patched``/``absent`` → return as-is, no git call.
> - sha-agg is ``partial`` → return as-is (sha-based mix is authoritative).
> - sha-agg is ``dirty`` → call git:
>     - ``git apply --check`` (forward) succeeds → clean + drift_hint="cosmetic"
>       (the patch would still apply forward → the file is pre-patch with
>       cosmetic drift on baseline; lifecycle = clean).
>     - ``--reverse --check`` succeeds → patched + drift_hint="cosmetic"
>       (the patch could still be reverted → the file is post-patch with
>       cosmetic drift on patched; lifecycle = patched).
>     - Both fail, per-hunk split shows some hunks applyable → partial
>       + drift_hint="semantic".
>     - All hunks fail → dirty + drift_hint="semantic".

Autrement dit : sha256 donne la certitude (match exact) ; `git apply
--check` donne la compatibilité (pattern s'adapte encore) ; le split
per-hunk donne le diagnostic fin (`partial` vs `dirty`).

Tableau synthétique (aligné design §5) :

| sha-agg | git apply forward | git apply reverse | per-hunk | état final | drift_hint |
|---|---|---|---|---|---|
| clean | — | — | — | clean | null |
| patched | — | — | — | patched | null |
| partial | — | — | — | partial | null |
| absent | — | — | — | absent | null |
| dirty | ✓ | — | — | clean | cosmetic |
| dirty | ✗ | ✓ | — | patched | cosmetic |
| dirty | ✗ | ✗ | some hunks apply | partial | semantic |
| dirty | ✗ | ✗ | none | dirty | semantic |

> Source : `docs/260420-patch-system-design.md §5` (detect composite), via
> le docstring `scripts/patch_system/detect.py` qui en reproduit les
> règles.

---

## §4. Séparation `series.json` (vérité de conception) et `runtime.json` (état d'exécution)

**ADR-0002** formalise la décision. Citation verbatim :

> **Nous retenons la separation en deux fichiers : `patches/series.json`
> (registre logique) et `patches/runtime.json` (config execution).**
>
> Concretement :
>
> - `patches/series.json` — **registre logique** :
>   - Contient la liste des patches avec, pour chaque entree : `id`,
>     `order`, `title`, `severity`, `audit_ref`, `status` derive,
>     `targets` (fichiers touches avec shas), pointeurs vers les fichiers
>     (`patch_file`, `record_file`).
>   - Contient aussi le champ global `vendor_baseline_sha` (cf. ADR-0001).
>   - **Ne contient aucun parametre d'execution** (pas de
>     `detection.strategy`, pas de `apply.method`, etc.).
>
> - `patches/runtime.json` — **config d'execution** :
>   - Structure `defaults` + `overrides[id]`.
>   - `defaults` decrit les parametres par defaut utilises par tous les
>     patches : `detection.strategy = checksum`, `apply.method =
>     git-apply`, `apply.args = []`, `rollback.cmd = git-apply-reverse`,
>     etc.
>   - `overrides[id]` permet a un patch specifique (cas atypique, hook
>     custom) de surcharger localement un parametre, sans toucher le
>     registre.
>   - 99 % des patches n'apparaissent pas dans `overrides` — ils
>     utilisent les defauts.
>
> Source : `docs/adr/ADR-0002-registre-runtime-separation.md §Décision`.

Cette séparation permet de :

- **Ne pas polluer les diffs review** du registre (ajout d'un patch
  ≠ changement de stratégie d'exécution).
- **Changer la stratégie globalement** (passer de `git-apply` à
  `patch -p1 --merge` en cas d'incident) sans pseudo-commit « update
  method » par patch.
- **Testabilité** : les tests peuvent injecter une `runtime.json` mockée
  sans toucher le registre réel.

Voir [§7 (reference.md)](./reference.md#7-schéma-runtimejson-j14) pour le
schéma consommé depuis J14 et [§7 ci-dessous](#7-exécution-dynamique-via-runtimejson-j14)
pour la discussion.

---

## §5. Héritage : quilt, DEP-3, Gentoo etc-update

Le patch-system n'est pas une invention gratuite. Il **emprunte** à trois
traditions documentées, recensées dans l'état de l'art
(`docs/260420-patch-system-soa.md` §4.3, cité verbatim) :

> **Tools a reutiliser (conceptuellement + formats)** :
>
> - **Format `patches/ + series` de Quilt** : bien etabli, lisible, connu.
> - **Header DEP-3** : reutiliser mot pour mot le vocabulaire Debian
>   (`Description`, `Origin`, `Forwarded`, `Last-Update`). Apporte de la
>   credibilite et de la familiarite a tout contributeur ayant touche a
>   Debian.
> - **`git apply --check` + sha256** comme mecanique de detection d'etat.
> - **Prompt interactif "etc-update-like"** (menu de lettres : y/n/s/d/?)
>   pour l'arbitrage des conflits.
> - **Modele d'idempotence Ansible** (separation `check_mode` +
>   `--diff` + `--limit`) comme reference conceptuelle de l'interface
>   operateur.
>
> Source : `docs/260420-patch-system-soa.md §4.3`.

### 5.1 quilt — `patches/ + series`

Le layout `patches/series + patches/*.patch` vient tout droit de
quilt (Debian, depuis 2001). La différence : nous n'utilisons pas le
binaire `quilt` (trop d'hypothèses sur le workflow shell linéaire + pas
de notion « déjà appliqué par une autre source »), seulement **la
convention de layout**.

### 5.2 DEP-3

Le header des fichiers `.patch` est au format **DEP-3** (Debian
Enhancement Proposal 3) :
<https://dep-team.pages.debian.net/deps/dep3/>. Champs standards réutilisés
verbatim : `Description`, `Origin`, `Author`, `Forwarded`, `Last-Update`,
`Applied-Upstream`. Champs locaux préfixés `X-*` (design §5.4) pour
signaler l'extension : `X-Audit-Ref`, `X-Severity`,
`X-Baseline-Sha256`, `X-Patched-Sha256`.

### 5.3 Gentoo etc-update

Le mode interactif prévu jalon 12 copie l'UX de Gentoo `etc-update`
/ `dispatch-conf` (menu y/n/s/d/? + défaut conservateur `n`). Design §4.2
cite ce choix :

> Les lettres sont choisies pour accrocher `git add -p` (y/n/s/d/?) +
> extensions locales.
>
> Source : `docs/260420-patch-system-design.md §4.2`.

### 5.4 Ansible `check_mode` + `--diff`

Le couple `--dry-run` (simulation sans écriture) + `--yes`
(non-interactif strict) s'inspire directement du `check_mode` d'Ansible
(SOA §2.6). Même philosophie : un opérateur teste en simulation avant
d'exécuter pour de vrai.

---

## §6. Trade-offs assumés

Certains choix sont des compromis explicites, documentés comme tels dans
le design pour qu'un futur contributeur comprenne pourquoi le système
**ne fait pas** certaines choses qu'on pourrait attendre.

### 6.1 Pas d'auto-commit après `apply`

Cité verbatim design §5.2 :

> **Decision** : **pas d'auto-commit** dans le vendor submodule (ou le
> super-repo). Chaque `apply` laisse le working tree modifie.
> L'utilisateur decide ensuite du commit.
>
> **Motivation** :
> - **Principe de surprise minimale** : un outil de patch ne devrait pas
>   ecrire dans le graphe git sans demande explicite.
> - **Coherent avec la strategie vendor retenue (§5.3, option c)** : les
>   patches ne sont **jamais** commites dans le submodule. L'etat patched
>   est re-genere a la demande.
>
> Source : `docs/260420-patch-system-design.md §5.2`.

Conséquence pratique : après un `apply`, un `git status` dans le vendor
montre le working tree sale. C'est délibéré. `git add -p` + `git commit`
(ou `git stash`, ou rien du tout si on va re-régénérer) sont de la
responsabilité de l'appelant.

### 6.2 Mono-vendor

Le patch-system cible exclusivement `vendor/obsidian-wiki`. Il n'y a pas
de support multi-vendor (patches/vendor-A/*, patches/vendor-B/*).
Ajouter un second vendor demanderait une évolution du schéma (clé
`vendor` par record ou préfixe par-vendor de `series.json`). Hors scope
Phase 3.

### 6.3 Python 3.10+ stdlib only

Cité verbatim design §6.2 :

> **Decision design** : **Python 3.10+ minimum**. `tomllib` (stdlib a
> partir de 3.11) **n'est pas utilise** ; la config runtime et le
> registre sont en JSON (§3.2, §3.3). Donc pas de besoin de bumper a
> 3.11+.
>
> **Justification** :
> - Cible deploiement : Debian 12 (`python3` = 3.11), Debian 11
>   (`python3` = 3.9 — non cible), Ubuntu 22.04 (3.10). 3.10+ couvre
>   tous les environnements de dev/prod raisonnables.
>
> Source : `docs/260420-patch-system-design.md §6.2`.

Pas de dépendance pip requise. Le package `scripts/patch_system/` se
contente de la stdlib — pas de `PyYAML`, pas de `unidiff`, pas de
`pytest`. La suite de tests est en `unittest` stdlib (design §5.6).

### 6.4 Granularité : 1 patch = 1 thème, pas 1 fichier

Cité design §5.1 :

> **Decision** : **1 patch = 1 theme**, un fichier `.patch` peut contenir
> plusieurs hunks sur plusieurs fichiers si ils traitent la meme
> anomalie. Ex. `p2-read-dotenv-wording` = **1 patch, 12 targets**, pas
> 12 patches.
>
> Source : `docs/260420-patch-system-design.md §5.1`.

Un record est une **unité sémantique** (« le wording `Read .env` est
trompeur »). Rollbacker ce wording n'a de sens qu'en bloc. 12 records
pour 12 identiques diffs serait bruyant à reviewer et à orchestrer.

---

## §7. Exécution dynamique via `runtime.json` (J14)

Le principe posé par ADR-0002 (§4 ci-dessus) — « la stratégie d'exécution
ne doit pas polluer le registre logique » — est concrétisé au jalon J14.
`patches/runtime.json` est désormais **consommé** par les commandes
`apply` et `rollback` via `scripts/patch_system/runtime.py`.

### 7.1 Pourquoi un second fichier, plutôt qu'un champ par record ?

Trois raisons, toutes pratiques :

- **Review propre** : ajouter un patch (édition `series.json`) ≠ changer
  la stratégie d'exécution (édition `runtime.json`). Deux diffs
  distincts, deux revues distinctes.
- **Changement global sans pseudo-commits** : passer toute la série de
  `git-apply` à `patch(1)` en cas d'incident, c'est un seul diff sur
  `runtime.json`, pas N pseudo-commits « update method » par record.
- **Testabilité** : les tests peuvent injecter un `runtime.json` mocké
  sans toucher au registre.

### 7.2 La méthode `patch` comme fallback

Le fallback `patch(1)` répond à un cas d'usage précis : les targets
gitignored dans le vendor repo. `git apply --index` refuse ces fichiers
(« does not exist in index »). `patch(1)`, qui opère directement sur le
working tree sans passer par l'index, n'a pas cette contrainte. Le record
pilote `b3-vendor-env-remove` (target `vendor/obsidian-wiki/.env`)
exploite précisément cet override.

Le choix d'une méthode externe (plutôt que `git apply --no-index`) tient
à la sémantique : `patch(1) -N` détecte nativement un patch déjà appliqué
et refuse — préservant l'idempotence du framework. `git apply --no-index`
n'a pas cet équivalent.

### 7.3 Override par section, pas par clé

`overrides[id]` remplace des **sections entières** (`apply`, `rollback`,
`detection`, `drift`), pas des clés individuelles. Conséquence : si un
override définit `{"apply": {"method": "patch", "args": ["-p1", "-N"]}}`,
la section `apply` du défaut est complètement ignorée pour ce record. Cela
évite les semi-configurations difficiles à raisonner (méthode changée mais
args hérités sans sens).

### 7.4 `runtime.json` absent = defaults hardcodés

Le fichier est **optionnel**. Son absence est traitée silencieusement par
`runtime_mod.load_runtime` : les defauts codés en dur sont retournés, et
tous les records utilisent `git apply --index` / `git apply --reverse --index`.
En J8, aucune commande ne consommait `runtime.json` — l'absence et la
présence avaient le même effet. En J14+, l'absence reste valide et reste
le cas par défaut. Seuls les records explicitement listés dans
`overrides` changent de stratégie.

---

## §8. Vérification et rafraîchissement : gérer le drift (J9-J10)

Un vendor non-forkable dérive, nécessairement, dès que l'upstream
avance. La stratégie `submodule pristine + régénération déterministe`
(ADR-0001) règle la question du **stockage** de l'état patché — mais pas
celle du **diagnostic** (« mes SHAs de baseline sont-ils toujours
d'actualité ? ») ni celle de la **réconciliation** (« quelle est la
nouvelle baseline après `git submodule update` ? »). Les jalons J9 et J10
répondent à ces deux questions, dans cet ordre.

### 8.1 `verify` — diagnostic, pas mutation

`verify` est **read-only**. Il exécute trois contrôles complémentaires :

- **Intégrité** : le fichier `.patch` sur disque correspond-il toujours à
  son `patch_sha256` enregistré ? Une non-correspondance signale que
  quelqu'un a édité le `.patch` manuellement sans passer par `record`.
- **Drift vendor** : le HEAD du submodule correspond-il au
  `vendor_baseline_sha` enregistré à la racine du registre, et chaque
  target matche-t-il encore `baseline_sha256` ou `patched_sha256` ?
- **Cohérence des targets** : un record `active` référence-t-il des
  targets qui existent toujours sous `vendor_root` ?

Le design §5.5 (« escalade drift ») exige qu'un drift ne soit **jamais
silencieux**. `verify` en mode normal le remonte en texte mais reste en
exit `0` ; `--strict` le promeut en failure. Ce double mode permet à la
même commande de servir deux publics : l'opérateur qui inspecte
manuellement (non-strict) et la CI qui veut un signal dur (strict).

### 8.2 `refresh` — mutation conservatrice

`refresh` est la seule opération qui écrit dans `series.json` sans passer
par `apply` / `rollback`. Sa portée est volontairement étroite :

- Il ne touche **qu'un seul champ par target** : `baseline_sha256` si
  l'état est `clean`, `patched_sha256` si l'état est `patched`.
- Il **refuse** les états ambigus (`dirty`, `partial`, `absent`,
  `unknown`). La justification : refresh sur un état ambigu
  enregistrerait comme « baseline » ou « patched » un SHA qui n'a de
  sens pour aucune des deux lanes. Mieux vaut exiger que l'opérateur
  réconcilie d'abord (apply ou rollback) avant de capturer le nouveau
  SHA.
- Il **n'essaie jamais** de recalculer les deux SHAs en même temps. La
  raison : sur un working tree donné, un seul des deux est observable.
  Connaître `patched_sha256` après un refresh `clean` demanderait de
  vraiment appliquer le patch — ce que le framework laisse au prochain
  `apply`.

Chaque refresh externalise un événement dans
`patches/history/<order>-history.jsonl` (§3.2 design) avec l'ancien et le
nouveau SHA — ce qui rend la trajectoire du registre auditable dans le
temps sans gonfler `series.json`.

---

## §9. Opérations batch `--all` (J13)

Le mode opératoire canonique — régénérer l'état patched à partir du
submodule pristine — n'a pas de sens « un record à la fois » : après un
`git submodule update`, on veut re-rejouer **toute la série**. D'où
`apply --all` et `rollback --all`, ajoutés au jalon J13.

### 9.1 Ordre ascendant (apply) vs descendant (rollback)

`apply --all` itère par `order` croissant ; `rollback --all` par `order`
décroissant. C'est la structure naturelle d'une pile : on empile dans
l'ordre 1, 2, 3, et on dépile 3, 2, 1. Un patch dont l'effet dépend d'un
patch précédent (cas des records composés `b1` → `b2` où `b2.baseline`
== `b1.patched`) s'applique correctement dans l'ordre d'empilement — et
rollback correctement dans l'ordre inverse.

### 9.2 Un seul `flock` pour toute la run

Les opérations mutantes prennent toujours un `flock` sur `patches/.lock`
(§4 reference). Pour `--all`, le dispatcher pose **une seule fois** le
lock au démarrage et le relâche en fin de run. Pas un lock par record.
Cela évite d'ouvrir une fenêtre entre deux records pendant laquelle un
autre process pourrait s'intercaler.

Les read-only (`list`, `status`, `describe`, `diff`, `verify`) ne prennent
pas le lock et restent utilisables pendant une run `--all` — utile pour
monitorer la progression depuis un second terminal.

### 9.3 Quitter proprement (`q`) ≠ échouer

Dans un apply `--all --interactive`, l'utilisateur peut presser `q` dans
le menu pour interrompre la run. Ce n'est pas un échec : les patches déjà
appliqués **restent appliqués** (pas de rollback), et le run retourne
exit `0` avec un résumé annoté `(user quit)`. C'est délibéré — un `q`
après 7 records réussis sur 10 ne doit pas masquer les 7 succès en les
étiquetant « failed ».

À l'inverse, `--stop-on-fail` (opt-in explicite) break à la première
failure **réelle**. Sans ce flag, la run continue et cumule les erreurs,
puis sort en `1` si au moins un record a échoué.

### 9.4 `rollback --all` : skip des records non-appliqués

Le garde-fou `last_result == "patched"` (déjà présent en J7 pour
`rollback` simple) s'applique aussi à `rollback --all`, mais avec un
comportement différent : au lieu de refuser avec exit `1`, le record est
**silencieusement skippé** et compté dans la ligne `M skipped` du résumé.
Cela permet de rollback sainement une série partiellement appliquée sans
avoir à identifier manuellement les records concernés.

---

## §10. Lectures complémentaires

- Design complet : [`../../../../docs/260420-patch-system-design.md`](../../../../docs/260420-patch-system-design.md)
- État de l'art : [`../../../../docs/260420-patch-system-soa.md`](../../../../docs/260420-patch-system-soa.md)
- ADR-0001 (vendor strategy) : [`../../../../docs/adr/ADR-0001-vendor-submodule-pristine.md`](../../../../docs/adr/ADR-0001-vendor-submodule-pristine.md)
- ADR-0002 (series/runtime split) : [`../../../../docs/adr/ADR-0002-registre-runtime-separation.md`](../../../../docs/adr/ADR-0002-registre-runtime-separation.md)
- Audit d'origine : `../../../../docs/260418-dual-sensitivity-analysis.md` (B1-B4, p2-*)
