# Etat de l'art — patch management pour vendoring non-forkable

**Date** : 2026-04-20
**Session kiss-claw** : 20260420-104751
**Phase** : 1 — Etat de l'art
**Objet** : synthese comparative des approches de gestion de patches locaux + recommandation
d'architecture pour le patch-system ciblant `vendor/obsidian-wiki`.

---

## 1. Contexte

Le projet maintient un vendor `vendor/obsidian-wiki` (skills bash/markdown) tracke via un
remote Git upstream non-forkable (pas de droits de push). L'audit
`docs/260418-dual-sensitivity-analysis.md` a identifie 4 anomalies bloquantes (B1-B4), 12
occurrences d'un pattern trompeur `Read .env`, et 5-6 occurrences d'un pattern `_raw/ inside
vault` trompeur en mode dual-zone. Il faut un systeme de corrections locales qui :

- stocke chaque correction comme une entite nommee et auto-documentee,
- detecte pour chaque cible l'etat `clean | patched | partial | dirty`,
- s'applique de maniere idempotente et interactive,
- est reversible,
- survit aux `git pull` successifs du vendor (ou signale explicitement un drift).

Contrainte techno du projet : bash + Python stdlib + JSON par defaut ; paquet pip/apt
propre OK ; exotique = confirmation prealable. La recommandation finale doit donc rester
dans ce perimetre.

---

## 2. Survol des familles

### 2.1 Quilt + DEP-3 (Debian)

- **Principe** : pile de patches appliquee sequentiellement au-dessus d'un "pristine tree"
  (ici, le checkout vendor upstream). Quilt gere un index `series` qui liste les patches
  dans l'ordre, et un repertoire `patches/` qui contient les diffs unifies.
- **Format storage** : un fichier par patch (convention `NNNN-short-name.patch`) dans
  `debian/patches/` (ou un `patches/` arbitraire). Le fichier commence par un **header
  DEP-3** (champs RFC-822-like), suivi du diff unifie.
- **Metadonnees DEP-3** (normalisees par <https://dep-team.pages.debian.net/deps/dep3/>) :
  - `Description` : titre + corps (pourquoi on patche)
  - `Origin` : `upstream, <commit>` | `backport, <url>` | `vendor` | `other, <source>`
  - `Author` / `From`
  - `Forwarded` : `yes`, `no`, `not-needed`, ou URL du ticket upstream
  - `Applied-Upstream` : version ou commit upstream qui rend le patch caduc
  - `Last-Update` : date ISO
  - `Bug` / `Bug-Debian` / `Bug-Upstream` : references bugtrackers
- **Commandes cles** (Quilt 0.67) :
  - `quilt new <name>` — cree un patch vide en tete de pile, l'empile
  - `quilt add <file>` — declare les fichiers qu'on va modifier (snapshot pour diff)
  - `quilt refresh` — met a jour le patch depuis les modifs du working tree
  - `quilt push` / `quilt pop` — applique / desapplique un patch
  - `quilt push -a` / `pop -a` — toute la pile
  - `quilt applied` / `quilt unapplied` — etat courant
  - `quilt top` — nom du patch actif
  - `quilt header -e <patch>` — edition des metadonnees DEP-3
- **Detection d'etat** : Quilt tient un registre `.pc/` (pristine copies) qui lui permet
  de savoir exactement ce qui est applique, et reagit mal a des modifications hors de son
  controle (conflit "file has been modified"). Quilt ne detecte pas la notion "deja
  applique par une autre source" — il suppose un workflow lineaire.
- **Applicabilite a notre cas** : Quilt est exactement conçu pour notre probleme
  (corrections locales sur tarball upstream), mais :
  - il presuppose que le vendor soit un tarball extrait, pas un submodule git avec son
    propre historique,
  - il n'expose pas de mode "skip si deja applique, marque patched" ; il echoue si la
    cible a deja ete modifiee,
  - l'UX est tres shell, pas interactive (pas de mode merge interactif a la etc-update).
  - **Forte valeur** a **reutiliser** : le format DEP-3 (metadonnees standardisees) et
    la convention `patches/ + series`.

### 2.2 Debian source format 3.0 (quilt)

- **Role** : format de package source Debian, declare dans `debian/source/format`
  (une ligne : `3.0 (quilt)`). Documente dans `dpkg-source(1)`.
- **Ce que le format fait** : lors du build, `dpkg-source -x` decompresse le tarball
  upstream **pristine**, puis applique automatiquement la serie `debian/patches/series`
  (meme mecanisme que Quilt). Au `dpkg-source -b`, tout changement non commit dans un
  patch de la serie est bloque — cela force le mainteneur a creer un patch explicitement
  nomme.
- **Difference avec `1.0`** :
  - `1.0` : tout est fusionne dans un unique `.diff.gz` monolithique (difficile a
    maintenir, pas de granularite par correction).
  - `3.0 (quilt)` : un patch = une correction atomique, avec en-tete DEP-3, rebase
    propre possible.
  - `3.0 (quilt)` supporte plusieurs tarballs upstream additionnels et la compression
    xz/bzip2.
- **Lecon applicable** : le pattern "pristine tarball + serie de patches + regeneration
  deterministe a la build" est le modele le plus mature pour "vendoring corrige". On
  peut transposer : `vendor/obsidian-wiki@HEAD` = pristine, notre `patches/series` = la
  serie, un script `apply-patches` = regeneration deterministe.

### 2.3 etc-update / dispatch-conf (Gentoo)

- **Principe** : apres un `emerge` qui reinstalle un paquet, Gentoo laisse les nouveaux
  fichiers config a cote des existants sous forme `._cfg0000_foo.conf`. Les deux outils
  proposent a l'utilisateur de resoudre les differences.
- **`etc-update`** (script shell) — modes interactifs listes dans son prompt :
  1. Replace original with update (remplace)
  2. Delete update, keeping original as is (garde local)
  3. Interactively merge original with update (merge via `sdiff` ou outil configure)
  4. Show differences again
  5. Show differences between merge and update
  6. Quit
  + modes auto : `-1` interactive; `-3` auto-use-new; `-5` auto-use-current-merging;
  `-9` auto-replace (dangerous).
- **`dispatch-conf`** (Python) — memes modes + historisation RCS/Git des decisions
  (on retrouve l'historique de chaque arbitrage).
- **Detection de drift** : compare le hash du fichier *installe* (config) au hash de la
  version *pristine* connue par portage (dans le manifeste du paquet). Si le fichier a
  ete modifie localement ET que la nouvelle version upstream est differente, conflit a
  arbitrer. C'est une detection a trois points : `baseline | local | upstream`.
- **UX** : tres bien calibree pour "j'ai N conflits, laissez-moi les trier un par un avec
  un fallback auto". C'est l'UX la plus proche de ce qu'on veut pour un flow
  `patch-system apply --interactive`.
- **Applicabilite** : le modele 3 points (baseline / local modifie / nouvelle upstream)
  et l'UX menu-par-conflit sont **la bonne reference** pour notre "after `git pull`
  upstream, reconcilier chaque patch". Les modes 1-6 sont a reprendre quasi tels quels.

### 2.4 Nixpkgs / Arch PKGBUILD / RPM %patch

Trois variantes du meme pattern declaratif :

| Systeme | Declaration | Exemple | Application |
|---|---|---|---|
| **Nixpkgs** | champ `patches = [ ... ]` dans la derivation | `patches = [ ./fix-build.patch (fetchpatch { url = ...; sha256 = ...; }) ];` | applique par `patchPhase` (script stdenv) via `patch -p1 < $patch`. Les fetchpatch integrent un hash. |
| **Arch PKGBUILD** | tableau `source=(... patch.diff)` + `sha256sums` + fonction `prepare()` | `prepare() { cd "$srcdir/pkg"; patch -p1 < "$srcdir"/0001-fix.patch; }` | exclusivement imperatif : c'est l'auteur qui appelle `patch` dans `prepare()`. |
| **RPM spec** | `Patch0: fix.diff`, `Patch1: ...` puis `%patch0 -p1` dans `%prep` | idem | tags `Patch` indexes + application imperative dans `%prep`. RPM modernes : `%autopatch` qui automatise la boucle. |

- **Ordre d'application** : toujours declaratif (ordre du tableau Nix, du tableau source
  Arch, numerotation des `PatchN` RPM).
- **Granularite** : un patch = une correction atomique, idealement forwardable upstream
  (meme philosophie que DEP-3).
- **Integrity** : Nix et Arch incluent **systematiquement** un hash du patch (sha256),
  ce qui permet de detecter une corruption ou une substitution malveillante. DEP-3 ne
  l'exige pas.
- **Applicabilite** : on retient
  - **le hash par patch** (safety + detection de drift interne),
  - **la declaration en tableau ordonne** (notre `series` peut etre un YAML/JSON liste
    plutot qu'un fichier texte a lignes, ce qui permet d'y ajouter les hashes).

### 2.5 Git-native workflows

- **`git format-patch <range>`** : produit des `.patch` a l'unite avec en-tete "mbox"
  (`From <sha>`, `Subject:`, `Date:`, `---` puis le diff) — format universel que `git am`
  sait rejouer.
- **`git am <patches>`** : applique la serie, cree un commit par patch avec preservation
  auteur/date. Supporte `--3way` (fusion automatique si les blobs de base existent),
  `--abort`, `--skip`, `--continue`. Tres bon pour un rebase trunk-based.
- **`git apply`** (inverse : applique *sans* commit, utile pour un rebase script) :
  - `--check` : teste sans appliquer — **equivalent de `patch --dry-run`, en mieux**
    (git comprend le contexte renames/modes/binary).
  - `--3way` : tente la fusion si conflit.
  - `--reverse` : desapplique.
  - `--reject` : ecrit les hunks qui echouent dans `.rej` — permet un mode partial.
- **Stacked patches tooling** : outils tiers pour gerer une **pile** de patches comme
  entites editables :
  - `stgit` (Stacked Git) — le plus proche de Quilt mais natif git (commits comme
    patches, `stg push/pop/refresh/sink/float`). Packaging Debian/Ubuntu disponible.
  - `git-revise` — reecrit l'historique proprement (comme `rebase -i` mais plus sur).
  - `git-branchless` — graphe de branches "stacked", plus oriente workflow.
- **Vendoring :**
  - **Submodule** : pointeur vers un commit upstream. Les modifications locales dans le
    submodule ne sont **pas** trackees par le super-repo — dangereux pour notre cas (le
    patch se perd au prochain submodule update).
  - **Subtree** : import complet de l'arbre upstream dans le super-repo, merges
    periodiques avec `git subtree pull`. Les modifications locales apparaissent comme
    des commits normaux du super-repo ; elles sont preservees a travers les merges,
    **mais** elles sont melees au contenu upstream (pas de separation visible entre
    "patch local" et "import upstream").
  - **`git-vendor`** (Brett Langdon) et **vendir** (Carvel) : scripts specialises pour
    materialiser un `vendor/` depuis un remote, sans l'intrusion submodule/subtree.
- **Applicabilite** :
  - `git apply --check` remplace largement `patch --dry-run` dans notre contexte (le
    vendor est un checkout git).
  - `git format-patch` est peut-etre exagere si on ne veut pas manipuler un repo de
    commits upstream — mais le **format mbox** produit est utilisable directement par
    `patch(1)` comme par `git apply`.
  - `stgit` est la reference si on voulait une pile editable complete, mais c'est
    surkill pour notre volume (une douzaine de patches stables).

### 2.6 Idempotence — patterns Ansible / Puppet

- **Ansible** :
  - Chaque module definit un **etat desire** (`state: present`, `lineinfile`, `copy`
    avec checksum, etc.). Le module calcule l'etat actuel, compare, agit **uniquement
    si necessaire**, et retourne `changed: true/false`.
  - **`check_mode`** (`ansible-playbook --check`) : dry-run natif — chaque module doit
    supporter `check_mode` et rapporter ce qu'il *aurait* fait, sans ecriture.
  - **`diff` mode** (`--diff`) : montre les diffs de contenu qu'il appliquerait.
  - Le couple `check + diff` est precisement l'UX qu'on veut pour un `patch-system
    status` / `apply --dry-run`.
- **Puppet** :
  - Modele **declaratif pur** : l'utilisateur decrit l'etat desire via des "ressources"
    (`file { ... }`, `package { ... }`). Le catalog compiler calcule un plan, l'agent
    converge vers l'etat desire.
  - Idempotence = propriete du type de ressource (le mainteneur du type garantit qu'une
    deuxieme application ne fait rien).
- **Pattern clef a retenir** : **separation explicite entre `detect` et `apply`**. Un
  patch ne devrait jamais "tenter puis recuperer" — il devrait d'abord **verifier son
  etat** puis decider d'agir (ou non).
  - Etats d'une ressource idempotente : `ok` (deja conforme), `changed` (applique),
    `skipped` (non applicable ici), `failed`.
  - Transpose dans notre contexte : `clean` (pristine, patch non applique), `patched`
    (applique proprement), `partial` (applique en partie — drift), `dirty`
    (modifications non tracees par aucun patch connu), `absent` (fichier cible
    introuvable).

### 2.7 Detection d'etat

Trois familles de techniques, souvent combinees :

| Technique | Mecanisme | Forces | Limites |
|---|---|---|---|
| **Checksum baseline** | sha256 du fichier vendor a l'etat pristine + du fichier patched attendu. Comparaison exacte. | tres fiable, zero faux-positif | sensible a la moindre difference (espaces, LF/CRLF) ; se casse au `git pull` meme si le fichier n'est pas touche |
| **Content-match (grep signature)** | regex/substring qui caracterise le patch (ex. `grep -qF 'RAW_DIR=' file`) | souple, resiste aux refactos voisins | peut generer des faux-positifs (autre intervenant a ecrit la meme ligne) ; maintenance des signatures |
| **`patch --dry-run` / `patch -R --dry-run`** | tente l'application / le retrait sans ecrire. `-N` detecte "deja applique". | aligne avec l'outil d'application, pas de duplication de logique | depend fortement de la qualite du contexte dans le diff ; confus en cas de drift partiel |
| **`git apply --check`** | idem mais via git (preserve meta : renames, modes, binaire) | plus intelligent que `patch` sur un checkout git | necessite un checkout git (OK pour nous) |
| **Diff recalcule** | genere le diff vendor@HEAD -> fichier actuel, compare a la baseline des patches attendus | detecte exactement l'etat semantique | plus complexe a implementer |

**Trade-offs a arbitrer pour notre architecture** :

- **Faux positifs** : le content-match seul genere des faux positifs ("la signature est
  la mais le reste du patch est absent"). Le combiner avec sha256 de la forme "patched"
  attendue elimine ce risque.
- **Gestion partielle** : `patch --dry-run` avec `--reject` ecrit les hunks qui
  echouent dans un `.rej` qu'on peut compter pour distinguer `partial` (au moins un
  hunk OK, au moins un qui echoue) de `dirty` (aucun hunk applicable).
- **Upstream drift** : apres un `git pull` upstream, la sha256 baseline change. Pour
  que le patch survive, il faut soit (a) regenerer la baseline sur HEAD et rejouer le
  patch via `git apply --3way`, soit (b) detecter le drift et forcer un refresh manuel.
  Gentoo l'arbitre via `dispatch-conf` : on a valide que c'est la bonne UX.

**Strategie composite recommandee** (voir §4) :

1. **sha256** de la cible vs baseline connue → `clean`/`dirty`/`unknown`.
2. Si `unknown`, tenter **`git apply --check --reverse`** sur le patch → si OK, etat
   `patched`.
3. Si ni l'un ni l'autre, essayer **`git apply --check`** direct : si OK, `clean`
   (la cible a drifte mais le patch reste applicable) ; si KO, essayer avec `--3way`
   pour distinguer `partial` vs `dirty`.

### 2.8 Outils Python pertinents

| Librairie | Canal | Ce que ca fait | Pertinence |
|---|---|---|---|
| **`unidiff`** | PyPI (`pip install unidiff`) | Parser unified diff → AST (hunks, files, lignes ajoutees/retirees). Tres stable (~10 ans, maintenue par Matias Bordese). Pas d'application, **parsing seul**. | **eleve** : permet de lire les metadonnees du patch (liste des fichiers cibles, ratio add/del) sans forker `patch(1)`. |
| **`whatthepatch`** | PyPI | Parser multi-format : unified, context, git. Plus permissif, utilise par Black et pre-commit. | moyen : redondant avec `unidiff` sauf si on veut supporter des patches de format variable. |
| **`patch-ng`** / **`python-patch-ng`** | PyPI (fork maintenu de `python-patch`) | Parser **et applier** pur Python. Evite la dependance au binaire `patch(1)` du systeme. | moyen : interessant pour la portabilite (Windows), mais nous sommes Linux-only ; et l'applier natif est moins robuste que GNU patch sur les cas limites. |
| **`difflib`** (stdlib) | stdlib | Generation de diffs unifies (`difflib.unified_diff`), et algorithmes de plus longue sous-sequence commune. | **eleve** pour la generation ; surtout pour *construire* un diff depuis deux etats de fichier (notre flow `patch-system record`). |
| **`subprocess`** (stdlib) | stdlib | Appeler `patch`, `git apply`, `quilt` avec capture stdout/stderr. | **indispensable** : c'est le pont vers les outils eprouves. |
| **`hashlib`** (stdlib) | stdlib | sha256 de fichiers | **indispensable** pour la detection checksum. |
| **`pathlib`, `tomllib` (3.11+), `json`** | stdlib | parsing config | **indispensable**. |

**Verdict outillage** : stdlib + `subprocess` couvrent 90% du besoin. Ajouter `unidiff`
apporte un parser robuste du format unified diff sans faire de parsing custom. Le
binaire `patch(1)` (GNU patch 2.7.6 installe, verifie sur la machine cible) et `git`
(present) couvrent l'application.

### 2.9 Autres references rencontrees

- **`etckeeper`** (Debian) : wraps `/etc` dans un repo git (ou bzr/hg/darcs) et commit
  automatiquement les modifications lors des `apt install/upgrade`. Utile pour **avoir
  un historique** des changements locaux — l'equivalent pour nous serait de
  **commiter chaque application de patch** dans le super-repo, pour tracer qui a
  applique quoi quand.
- **`needrestart`** : detecte apres `apt upgrade` quels services/daemons/kernel
  necessitent un redemarrage. Pattern **detect-and-act** = "scanner l'etat reel du
  systeme + proposer des actions ciblees". Transpose : apres `git pull vendor`,
  detecter quelles patches sont potentiellement drift et proposer de les refresh.
- **`vendir`** (Carvel) : outil YAML-declaratif pour materialiser un repertoire
  `vendor/` depuis des remotes git/imgpkg/image/manual. Conceptuellement proche de ce
  qu'on veut mais avec un runtime Go ; pas dans notre perimetre techno.
- **`copybara`** (Google) : outil Java/Starlark pour transformer/synchroniser du code
  entre repos (typiquement "depot interne <-> public github"). Expressive mais
  lourd ; hors perimetre.
- **`debmake` / `dh-make`** : generateurs de squelette Debian ; juste pour memoire.
- **`patchelf` / `patch-package` (npm)** : cousins, mais pour du binaire ELF et des
  node_modules respectivement ; hors scope.

---

## 3. Comparaison synthetique

Legende colonnes : **Storage** = format de stockage natif ; **Meta** = support metadonnees
standardisees ; **UX inter.** = interactif natif ; **Detect** = detection d'etat ;
**Rollback** = support du retrait d'un patch ; **Idemp.** = idempotent natif ;
**Deps** = dependances d'execution ; **Cplxite** = complexite operationnelle pour notre
volume (~25 anomalies).

| Approche | Storage | Meta | UX inter. | Detect | Rollback | Idemp. | Deps | Cplxite |
|---|---|---|---|---|---|---|---|---|
| **Quilt** | `patches/*.patch` + `series` | DEP-3 (excellent) | partielle (TTY) | stacked state dans `.pc/` | `quilt pop` | quasi (echec si drift) | binaire `quilt` | moyenne |
| **Debian 3.0 (quilt)** | idem + `debian/source/format` | DEP-3 | non | via dpkg-source | `dpkg-source -x` | oui (regeneration) | dpkg-dev | haute |
| **etc-update / dispatch-conf** | `._cfg0000_*` sidecar files | aucune | **excellente (menu)** | hash 3-points | N/A (merge decisionnel) | oui | portage | haute (gentoo-only) |
| **Nixpkgs patches** | `patches = [ ]` + `*.patch` | header libre + sha256 | non | hash explicite | re-derivation | oui | Nix | haute |
| **Arch PKGBUILD** | `source=()` + `prepare()` | sha256sums | non | sha256 source | N/A | faible (impotent ecrit) | makepkg | moyenne |
| **RPM %patch** | `PatchN:` + `%patch` | tag libre | non | aucune native | N/A | faible | rpm-build | haute |
| **git format-patch + am** | mbox `.patch` | en-tete mbox | partielle (`--interactive`) | `git apply --check` | `git revert` / `apply -R` | oui | git | faible |
| **stgit** | stacked commits | commit messages | partielle | stg etat interne | `stg pop` | oui | stgit | moyenne |
| **Ansible check_mode** | YAML playbook | tasks structurees | non (mais diff/check) | modulaire | `state: absent` | **oui (modele)** | ansible | haute |
| **Puppet** | DSL | types | non | converge | ressources inverse | **oui (modele)** | puppet | tres haute |

**Lectures de ce tableau** :

- Aucune famille n'offre a la fois (a) UX interactive fine, (b) idempotence stricte,
  (c) metadonnees riches, (d) detection d'etat tri-valuee, (e) zero dep exotique.
  → **le systeme cible doit etre un assemblage emprunte a plusieurs familles**.
- **DEP-3** gagne pour les metadonnees.
- **etc-update** gagne pour l'UX interactive.
- **Ansible check_mode** gagne pour le modele d'idempotence + dry-run.
- **`git apply --check` + sha256** gagne pour la detection d'etat (vendor est un checkout
  git, autant l'exploiter).
- **Quilt** gagne conceptuellement pour la structure `patches/ + series`, mais le
  **binaire** `quilt` n'est pas necessaire : la convention peut etre imitee en ~300
  lignes de Python.

---

## 4. Recommandation architecture

### 4.1 Format de stockage

**Recommandation : quilt-like file-per-patch + registre JSON complementaire.**

Structure proposee dans le super-repo (pas dans le vendor) :

```
patches/
  series.json                          # registre ordonne : liste d'anomaly records
  0001-remove-vendor-env.patch         # fichier diff unifie, un par patch
  0002-wiki-ingest-raw-fallback.patch
  0003-wiki-ingest-security-check.patch
  0004-read-dotenv-wording.patch
  ...
```

Chaque `.patch` suit le format **diff unifie + header DEP-3 enrichi** :

```
Description: wiki-ingest — replace _raw/ fallback by OBSIDIAN_RAW_DIR
 In dual-zone mode, _raw/ lives outside the vault. The original fallback
 `$OBSIDIAN_VAULT_PATH/_raw/ (or OBSIDIAN_RAW_DIR)` would point to a
 non-existent directory. Fallback order inverted.
Audit-Ref: docs/260418-dual-sensitivity-analysis.md#b1
Severity: BLOCKING
Author: <opérateur> <email>
Origin: vendor
Forwarded: no
Last-Update: 2026-04-20
Baseline-Sha256: 3f4a...c8                # sha256 de la cible pristine
Patched-Sha256: 9bd1...ee                 # sha256 de la cible apres patch
---
--- a/.skills/wiki-ingest/SKILL.md
+++ b/.skills/wiki-ingest/SKILL.md
@@ -58,7 +58,7 @@
 ...
```

**Pourquoi file-per-patch + JSON et pas YAML unique monolithique** :

- **Diff review-friendly** : un patch = un fichier. Review ligne a ligne dans git.
- **Naming discover-friendly** : `ls patches/` donne l'inventaire.
- **DEP-3 est un standard** : embarquer les metadonnees dans l'en-tete du patch plutot
  que dans un registre externe rend le fichier auto-suffisant — on peut le copier, le
  partager, le forwarder upstream sans accompagnement.
- **`series.json`** joue deux roles : (a) ordre d'application explicite, (b) registre
  d'etat machine-lisible (derniere application, sha des patches, decisions
  d'arbitrage). Le JSON est choisi plutot que YAML par la contrainte projet (stdlib
  Python parse JSON, pas YAML).

**Pourquoi pas uniquement un registre unique JSON avec patches inline** :

- Les diffs unifies contiennent des `---` et `+++` qui posent des problemes d'echappement
  en JSON embarque (literal strings escaping heredoc).
- Perte du benefice "patch forwardable upstream sans extraction".

**Pourquoi pas YAML** : dependance pip (`PyYAML`) qui, bien que standard, n'est **pas**
dans la stdlib. JSON est deja suffisamment expressif pour notre registre, et la
lisibilite humaine du registre est secondaire — l'humain lit les `.patch`, la machine
lit `series.json`.

### 4.2 Langage + dependances

**Recommandation : bash pour les entry points + Python stdlib pour la logique, aucune
dep pip bloquante au demarrage ; `unidiff` en dep optionnelle pour le parsing avance.**

Decoupage :

- **`scripts/patch-system`** (bash) — dispatcher qui parse le premier argument
  (`status`, `apply`, `revert`, `refresh`, `record`, `show`) et delegue a un module
  Python. 30-50 lignes. Utile pour l'intentionnalite "outil shell" (on reste dans la
  culture des scripts du projet).
- **`scripts/patch_system/` (Python 3.10+, stdlib seul)** — paquetage Python :
  - `core.py` : load/save de `series.json`, resolution des chemins, types `AnomalyRecord`.
  - `detect.py` : strategie composite sha256 + `git apply --check` + optionnel unidiff
    pour analyse hunks.
  - `apply.py` : `subprocess` vers `git apply` (ou `patch` en fallback), gestion des
    rejects, historisation.
  - `ui.py` : boucle interactive style etc-update (prompts 1-6 par conflit).
  - `cli.py` : entry point `python3 -m patch_system ...`.
- **Deps pip optionnelles** : `unidiff` pour un parsing plus propre des hunks (detection
  `partial`). A installer via `pip install --user unidiff` ; le code detecte l'absence
  et degrade vers parsing regex minimal.
- **Deps systeme** : `git`, `patch`, `python3>=3.10`, `bash>=4`. **Tous deja presents**
  (verifie sur la machine de dev). Pas de `quilt` requis.
- **Justification vs contrainte projet** : bash + Python stdlib + JSON = coeur du
  perimetre "par defaut". Pas de demande de validation pour `unidiff` car il est
  optionnel. Pas d'apt install pour `quilt` car evite (imitation du pattern, pas usage
  de l'outil) — decision **economise une dep systeme** au prix de ~200 lignes de code.

### 4.3 Tooling externe — arbitrage

| Outil | Installer ? | Justification |
|---|---|---|
| **`quilt`** (apt) | **non** | On imite le layout et les commandes, mais on ne l'utilise pas. Quilt impose un `.pc/` state qu'on ne veut pas gerer. L'economie de ~200 lignes ne compense pas une dep systeme et une surface de compatibilite (quilt versions). |
| **`git`** | **deja present** | utilise pour `apply --check`, `apply --3way`, eventuellement `format-patch` pour generer les patches initiaux. |
| **`patch`** (GNU patch 2.7.6) | **deja present** | fallback d'application si `git apply` echoue (cas rare ou `git apply` est plus strict que `patch`). |
| **`unidiff`** (pip, optionnel) | **recommande** | eclaircit le code de detection `partial`. Pas bloquant a l'absence. |
| **`stgit`** | **non** | surkill pour ~25 patches stables ; ajoute une dep systeme majeure. |
| **`PyYAML`** | **non** | registre en JSON. |
| **`etckeeper`** | **non** | l'equivalent est assure par des commits propres dans le super-repo apres chaque `apply`. |

### 4.4 Structure d'un "anomaly record"

Champs proposes pour chaque entree de `series.json` (l'en-tete DEP-3 du `.patch`
associe dupliquera les meta humaines ; le JSON est la verite machine) :

```json
{
  "id": "b1-wiki-ingest-raw-fallback",
  "title": "wiki-ingest — replace _raw/ fallback by OBSIDIAN_RAW_DIR",
  "description": "In dual-zone mode, _raw/ lives outside the vault...",
  "audit_ref": "docs/260418-dual-sensitivity-analysis.md#b1",
  "severity": "BLOCKING",
  "status": "active",
  "patch_file": "patches/0001-wiki-ingest-raw-fallback.patch",
  "patch_sha256": "a3f2...1c",
  "order": 1,
  "targets": [
    {
      "path": "vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md",
      "baseline_sha256": "3f4a...c8",
      "patched_sha256": "9bd1...ee"
    }
  ],
  "detection": {
    "strategy": "composite",
    "signals": ["checksum", "git-apply-reverse-check"]
  },
  "apply": {
    "method": "git-apply",
    "args": ["--index", "--whitespace=nowarn"]
  },
  "rollback": {
    "method": "git-apply",
    "args": ["--reverse", "--index"]
  },
  "last_applied": "2026-04-20T10:52:13Z",
  "last_result": "patched",
  "history": [
    {"date": "2026-04-20T10:52:13Z", "action": "apply", "result": "patched"}
  ]
}
```

Champs **obligatoires** : `id`, `title`, `patch_file`, `severity`, `order`, `targets[]`.
Champs **optionnels** : `history` (peut etre externalise dans un log separe pour ne pas
bloater le registre), `detection.signals` (defaut = `["checksum"]`).

Statuts possibles d'un record (distincts de l'etat d'une *target*) :

- `active` — patch attendu applique.
- `disabled` — patch temporairement desactive (dans series.json mais pas applique).
- `obsolete` — upstream a corrige, patch caduc a archiver.

Etats possibles d'une *target* (renvoyes par `status`) :

- `clean` — pristine, patch non applique (normal avant `apply`).
- `patched` — applique proprement (sha256 == patched_sha256).
- `partial` — certains hunks appliques, d'autres non (drift).
- `dirty` — ni pristine ni patched (modif exterieure non tracee).
- `absent` — fichier cible introuvable.
- `unknown` — aucun signal ne permet de statuer.

### 4.5 UX CLI proposee

Style inspire de `ansible-playbook --check --diff` + `etc-update`.

```
patch-system status                    # inventaire : par patch, etat de chaque target
patch-system status <id>               # zoom sur un record (targets, sha, history)
patch-system show <id>                 # cat du .patch + meta DEP-3
patch-system apply                     # applique toute la serie, skip ce qui est deja patched
patch-system apply <id>                # applique un patch
patch-system apply --dry-run           # n'ecrit rien, sort la liste des actions prevues
patch-system apply --interactive       # mode etc-update : prompt par target en conflit
patch-system revert <id>               # rollback d'un patch (git apply --reverse)
patch-system revert --all              # pop toute la pile
patch-system refresh <id>              # met a jour patched_sha256 baseline apres un pull vendor
patch-system record <id> --from <path> # cree un nouveau patch depuis le diff actuel
patch-system verify                    # recalcule les sha256 de tous les .patch + detecte drift
```

Modes interactifs inspires etc-update lors d'un conflit :

```
Patch 0002 target vendor/.../wiki-ingest/SKILL.md is partial.
  [1] Force apply (overwrite local)
  [2] Skip (keep local, mark target as dirty)
  [3] Show 3-way diff (pristine | local | patched)
  [4] Attempt 3-way merge (git apply --3way)
  [5] Refresh baseline from current (auto-bump baseline_sha256)
  [6] Quit
Choice [1-6]:
```

Sortie `status` (format compact machine + TTY) :

```
ID                                SEV       TARGETS   STATE
b1-wiki-ingest-raw-fallback       BLOCKING  1/1       patched
b2-wiki-ingest-security-check     BLOCKING  1/1       patched
b3-vendor-env-remove              BLOCKING  1/1       clean         <- pas encore applique
b4-vendor-env-subsumed            BLOCKING  0/1       absent        <- cible supprimee : OK
p2-read-dotenv-wording            TROMPEUR  12/12     partial       <- drift sur 3 fichiers
p2-raw-in-vault-wording           TROMPEUR  6/6       patched

Summary: 4/6 active, 1 partial, 1 clean
```

### 4.6 Points a trancher en Phase 2 Design

1. **Granularite des patches multi-cibles** : un `p2-read-dotenv-wording` touche 12
   fichiers. Un seul `.patch` multi-fichier ou 12 patches separes ? Impact sur la
   review et sur la granularite de rollback.
2. **Integration git des patches appliques** : est-ce que `patch-system apply` doit
   **commiter** le resultat dans le super-repo (audit trail clair) ou **rester en
   working tree** (flexibilite, mais risque d'oubli) ? Recommandation initiale : option
   `--commit` desactivee par defaut en Phase 1, activee par defaut ensuite.
3. **Gestion du vendor submodule** : le vendor est actuellement un submodule git. Les
   patches s'appliquent **dans** le submodule → ils ne sont pas commites dans le
   super-repo automatiquement. Il faut decider : (a) appliquer dans le submodule et
   commit dans le super-repo le nouveau sha du submodule (lourd, pollue l'historique
   submodule) ; (b) transformer `vendor/obsidian-wiki` en subtree import (plus de
   submodule, patches integres au super-repo comme des commits) ; (c) garder submodule
   et ne jamais commiter dedans, regenerer l'etat patched a chaque checkout via
   `patch-system apply`. **Option (c) est la plus alignee avec le principe
   "regeneration deterministe" du format Debian 3.0 quilt.**
4. **Format DEP-3 strict vs enrichi** : ajouter les champs `Baseline-Sha256` et
   `Patched-Sha256` enrichit DEP-3 non-standardement. Documenter dans un README
   explicite.
5. **Upstream tracking** : quand `git pull` ramene un upstream ou la ligne patchee a
   bouge, comment distinguer (a) drift cosmetique a refresh automatique vs (b)
   conflit semantique a arbitrer manuellement ? Heuristique envisagee : si `git apply
   --3way` reussit sans rejects, auto-refresh ; sinon, mode interactif.
6. **Tests** : la phase 3 (implementation) devra inclure des fixtures vendor fausses
   (arbre minimal + patches de test) pour valider les 5 etats (`clean`/`patched`/
   `partial`/`dirty`/`absent`). Probablement via `pytest` + `tmp_path`. Pytest est OK
   (pip standard), sinon `unittest` stdlib suffit.
7. **Concurrence / lock** : `apply` peut-il etre concurrent ? Deux agents qui
   l'invoquent en parallele corrompraient series.json. Verrou simple via `flock` sur
   `patches/.lock` a prevoir.

---

## 5. References

### Documentation officielle / specs

- Debian DEP-3 specification — <https://dep-team.pages.debian.net/deps/dep3/>
- `dpkg-source(1)` man page + section "Source package formats" — <https://manpages.debian.org/bookworm/dpkg-dev/dpkg-source.1.en.html>
- Quilt home + docs — <https://savannah.nongnu.org/projects/quilt/>, `quilt(1)` man page
- Gentoo Handbook, section `etc-update` — <https://wiki.gentoo.org/wiki/Etc-update>
- Gentoo `dispatch-conf` — <https://wiki.gentoo.org/wiki/Dispatch-conf>
- Nixpkgs contributors guide, section `patches` — <https://nixos.org/manual/nixpkgs/stable/#chap-overrides>
  (attribut `patches` et fonction `fetchpatch`)
- Arch Wiki, PKGBUILD — <https://wiki.archlinux.org/title/PKGBUILD> (section `prepare()`)
- Fedora RPM Packaging Guide, section "Patches" — <https://docs.fedoraproject.org/en-US/packaging-guidelines/#_patches>
- Git docs : `git-format-patch(1)`, `git-am(1)`, `git-apply(1)` — locales dans `man git-...`
- Ansible documentation : check_mode — <https://docs.ansible.com/ansible/latest/user_guide/playbooks_checkmode.html>
- Ansible "diff mode" — <https://docs.ansible.com/ansible/latest/user_guide/playbooks_checkmode.html#enabling-or-disabling-check-mode-for-tasks>
- Puppet type system — <https://puppet.com/docs/puppet/latest/lang_resources.html>

### Outils Python

- `unidiff` — <https://pypi.org/project/unidiff/> (GitHub: matiasb/python-unidiff)
- `whatthepatch` — <https://pypi.org/project/whatthepatch/>
- `patch-ng` — <https://pypi.org/project/patch-ng/>
- Python stdlib `difflib` — <https://docs.python.org/3/library/difflib.html>

### Outils peripheriques

- `stgit` — <https://stacked-git.github.io/>
- `git-subtree` — <https://github.com/git/git/blob/master/contrib/subtree/git-subtree.txt>
- `etckeeper` — <https://etckeeper.branchable.com/>
- `needrestart` — <https://github.com/liske/needrestart>
- `vendir` (Carvel) — <https://carvel.dev/vendir/>
- `copybara` — <https://github.com/google/copybara>

### Projet (contexte interne)

- `docs/260418-dual-sensitivity-analysis.md` — audit dual-zone, anomalies cibles
- `docs/400-tp/401-mission/besoin.md` — expression initiale du besoin
- `CLAUDE.md` et `AGENTS.md` vendor — contexte vault/skills
