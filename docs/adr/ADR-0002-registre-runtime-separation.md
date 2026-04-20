# ADR-0002 — Separation registre logique et runtime config

- Date : 2026-04-20
- Statut : Accepted
- Session kiss-claw : 20260420-104751
- Phase : 2 — Design architecture
- Documents amont : `docs/260420-patch-system-soa.md` §4.4, `docs/260420-patch-system-design.md` §3.1 / §3.2 / §3.3 / §5.8, `docs/adr/ADR-0001-vendor-submodule-pristine.md`

## Contexte

Le SOA Phase 1 §4.4 proposait un schema initial d'`series.json` comme
fichier unique listant l'ensemble des patches, melangeant dans chaque
entree :
- L'**identite logique** du patch : `id`, `order`, `title`, `severity`,
  `audit_ref`, `status` derive, pointeurs vers les fichiers (`*.patch`,
  `.record.json`).
- Les **parametres d'execution** : `detection.strategy`
  (checksum / apply-check / marker), `apply.method` (`git-apply` /
  `patch`), `apply.args`, `rollback.cmd`, options specifiques a un hook
  custom.

La revue verificator REV-0001 a liste cette confusion de responsabilites
comme **huitieme question ouverte** (separation registre logique vs runtime
config). Le design doc §5.8 a tranche pour la separation en deux fichiers
(`series.json` + `runtime.json`). La revue verificator REV-0003
(approved-with-notes, note methodo #5) a recommande de formaliser cette
decision dans un ADR propre — c'est l'objet du present document.

Le choix impacte :
1. **Clarte de schema** — un contributeur qui ouvre `series.json` voit-il
   immediatement **ce qui est patche** sans se noyer dans des details
   `detection/apply/rollback` par entree ?
2. **Evolution differentielle** — changer une strategie d'apply (ex. migrer
   de `git-apply` vers `patch -p1 --merge`) doit-il toucher le registre
   logique ?
3. **Testabilite** — peut-on injecter une `runtime.json` mockee dans les
   tests du moteur sans toucher le registre reel ?
4. **Lisibilite des diffs** — un changement de default d'execution doit-il
   produire un diff bruyant (N lignes, une par patch) ou localise (1 ligne
   dans `defaults`) ?
5. **Versionnage** — peut-on versionner `series.json` et `runtime.json` a
   des rythmes differents sans couplage artificiel ?

## Decision

**Nous retenons la separation en deux fichiers : `patches/series.json`
(registre logique) et `patches/runtime.json` (config execution).**

Concretement :

- `patches/series.json` — **registre logique** :
  - Contient la liste des patches avec, pour chaque entree : `id`, `order`,
    `title`, `severity`, `audit_ref`, `status` derive, `targets` (fichiers
    touches avec shas), pointeurs vers les fichiers (`patch_file`,
    `record_file`).
  - Contient aussi le champ global `vendor_baseline_sha` (cf. ADR-0001).
  - **Ne contient aucun parametre d'execution** (pas de `detection.strategy`,
    pas de `apply.method`, etc.).

- `patches/runtime.json` — **config d'execution** :
  - Structure `defaults` + `overrides[id]`.
  - `defaults` decrit les parametres par defaut utilises par tous les
    patches : `detection.strategy = checksum`, `apply.method = git-apply`,
    `apply.args = []`, `rollback.cmd = git-apply-reverse`, etc.
  - `overrides[id]` permet a un patch specifique (cas atypique, hook custom)
    de surcharger localement un parametre, sans toucher le registre.
  - 99 % des patches n'apparaissent pas dans `overrides` — ils utilisent
    les defauts.

- `patches/NNNN-*.patch` — **records individuels** :
  - Chaque fichier conserve son header DEP-3 enrichi (`Description`,
    `X-Audit-Ref`, `X-Severity`, `X-Baseline-Sha256`, `X-Patched-Sha256`),
    self-documenting au niveau fichier.
  - Le header DEP-3 reste le canal "pourquoi ce patch existe", independant
    du registre et de la config runtime.

Le moteur charge les deux fichiers au demarrage, merge `defaults` +
`overrides` pour chaque id, et execute. Les trois sources (registre,
runtime, header DEP-3) sont autoritatives sur leur perimetre respectif :
`series.json` fait foi sur `status/order/targets`, `runtime.json` fait foi
sur `strategy/method/args`, le header DEP-3 fait foi sur la motivation
humaine.

## Consequences

### Positives

- **Responsabilites separees** : un lecteur qui ouvre `series.json` voit
  immediatement le **quoi** (quels patches, dans quel ordre, quelle
  severite, quelle anomalie auditee). Un lecteur qui ouvre `runtime.json`
  voit le **comment** (quelle strategie, quelle methode d'apply, quel
  rollback). Les deux questions sont desormais reponses en deux lectures
  courtes plutot qu'en une lecture longue et melangee.
- **Evolution differentielle** : changer un default d'execution (ex.
  migration `git-apply` -> `patch -p1 --merge` pour etre plus tolerant)
  modifie une seule ligne dans `runtime.json`, sans toucher le registre.
  Pas de pseudo-commit "update apply method" qui pollue les diffs review.
- **Defaults + overrides explicites** : la structure `defaults` +
  `overrides[id]` rend visible en un coup d'oeil le nombre d'exceptions.
  Si les overrides gonflent, c'est un signal : il faut peut-etre changer
  le default lui-meme.
- **Testabilite** : les tests unitaires du moteur peuvent injecter une
  `runtime.json` mockee (ex. `apply.method = dry-run`) sans toucher le
  registre reel. Le registre reste la source de verite sur *quels*
  patches existent, independamment de *comment* on teste leur
  application.
- **Diffs plus lisibles** : un changement de default donne un diff
  localise (1 ligne), pas N lignes dupliquees entre records.
- **Versionnage differencie** : `series.json` evolue quand on ajoute ou
  retire un patch (rythme lent, par anomalie auditee) ; `runtime.json`
  evolue quand on ajuste une strategie (rythme tres lent, par retour
  d'experience). Les deux rythmes different naturellement — la separation
  rend ca explicite.
- **Coherent avec l'ADR-0001** : la regeneration deterministe post-submodule
  update necessite un moteur idempotent ; separer le *quoi* (stable, revu
  par humain) du *comment* (plus volatile, tunable) facilite cette
  idempotence et clarifie les surfaces a tester.

### Negatives

- **Fichier supplementaire a charger au demarrage** : le moteur lit deux
  fichiers au lieu d'un. Surcout negligeable en JSON stdlib, mais deux
  points de failure potentiels (fichier manquant, JSON malforme) au lieu
  d'un. Mitigation : le moteur valide les deux au demarrage ; un
  `runtime.json` manquant est traite comme `{"defaults": {...stdlib defaults
  inline...}, "overrides": {}}` (dégradation gracieuse).
- **Risque de desynchronisation `overrides[id]` vs `series.json[id]`** :
  si un patch est retire de `series.json` mais son override reste dans
  `runtime.json`, l'override devient du code mort. Mitigation : la commande
  `patch-system verify` detecte les overrides orphelins et emet un warning.
- **Plus de surface documentaire** : il faut documenter deux schemas JSON
  au lieu d'un (design §3.2 + §3.3). Le README utilisateur doit expliquer
  quand editer quel fichier. Mitigation : le design §3.1-§3.3 fait
  explicitement ce travail et fournit des exemples.

### Neutres

- **Duplication potentielle de certaines donnees** : l'id d'un patch
  apparait dans `series.json` et potentiellement dans `runtime.overrides`.
  Ce n'est pas une duplication fonctionnelle (les deux entrees decrivent
  des facettes differentes du meme patch), mais il faut maintenir la
  coherence des cles. Accepte et supervise par `verify`.
- **Toujours dans `patches/`** : les deux fichiers restent cote a cote
  dans `patches/`, pas dans des repertoires distincts. Simplicite de
  layout.
- **Pas d'impact sur le header DEP-3** : les records `.patch` restent
  auto-suffisants au niveau fichier (decisif pour la forwardabilite
  upstream — cf. Design §5.4). La separation registre/runtime
  n'intervient qu'au niveau super-repo.

## Alternatives rejetees

### Alternative A — Fichier unique `series.json` melangeant registre et runtime

**Principe** : proposition initiale du SOA §4.4 — un seul fichier
`series.json` dont chaque entree de la liste `patches[]` contient a la
fois l'identite (`id`, `order`, `title`, `severity`, `audit_ref`,
`targets`) et les parametres d'execution (`detection`, `apply`, `rollback`).

**Avantages** :
- Une seule source a lire/ecrire, cognitive cost reduit au demarrage du
  projet.
- Pas de risque de desynchronisation entre deux fichiers.

**Raisons du rejet** :
- **Confusion de responsabilites** : chaque entree melange "ce qui doit
  etre patche" et "comment le patcher". Difficile a reviewer (quelqu'un
  qui veut auditer le perimetre des patches est noye par les champs
  techniques d'execution).
- **Evolution schema plus risquee** : ajouter un champ d'execution
  (ex. `apply.timeout_sec`) force a toucher chaque record, meme si aucun
  patch n'a besoin du nouveau parametre. Risque de diffs bruyants a
  chaque iteration du design runtime.
- **Duplication** : chaque patch qui utilise les defauts duplique
  `detection.strategy: "checksum"`, `apply.method: "git-apply"`, etc.
  Pour N patches, N-1 duplications inutiles.
- **Diffs bruyants lors de changement de defaults** : changer le default
  global "checksum -> apply-check" necessite de toucher N lignes
  (une par patch), rendant le diff review quasi-illisible.

### Alternative B — Inlining des parametres runtime dans chaque header DEP-3 du `.patch`

**Principe** : pas de `series.json` ni de `runtime.json`. Chaque fichier
`.patch` contient, en plus de son header DEP-3 standard, des champs
`X-Apply-Method`, `X-Detection-Strategy`, `X-Rollback-Cmd`, etc. Le
moteur lit tous les `.patch` au demarrage et construit son registre +
sa config en memoire.

**Avantages** :
- Self-containment extreme : un seul `.patch` porte toute sa
  configuration, transportable tel quel.
- Pas de fichier index a maintenir.

**Raisons du rejet** :
- **Pas de defaults partages** : chaque patch doit repeter integralement
  sa config d'execution dans son header, meme si 99 % des patches
  utilisent les memes parametres. Duplication maximale.
- **Pas de vue d'ensemble** : pour savoir "combien de patches utilisent
  `apply-check` au lieu de `checksum` ?", il faudrait parser tous les
  fichiers `.patch`. Avec la decision retenue, un `cat overrides` dans
  `runtime.json` repond en une seconde.
- **Pollution du header DEP-3** : DEP-3 est concu pour decrire "pourquoi
  ce patch existe", pas "comment l'appliquer". Ajouter des champs
  d'execution melangeant les deux preoccupations nuit a la lisibilite
  humaine du header.
- **Forwardabilite degradee** : les champs `X-Apply-*` specifiques a
  notre moteur n'ont aucun sens cote upstream. Les retirer au moment
  du forwarding ajoute une etape de transformation, contrairement a
  l'approche retenue ou le `.patch` reste directement forwardable.
- **Ordering implicite** : sans registre central, l'ordre d'application
  devrait etre encode dans le nom du fichier (`0001-*.patch`,
  `0002-*.patch`, etc.). Changer l'ordre = renommer des fichiers = diff
  git disgracieux.

### Alternative C — YAML au lieu de JSON pour `series` et/ou `runtime`

**Principe** : stocker les deux fichiers (ou un seul) en YAML, arguant
d'une meilleure lisibilite humaine et de la possibilite d'ajouter des
commentaires inline.

**Avantages** :
- YAML autorise les commentaires (`#`), JSON non.
- Syntaxe moins verbeuse (pas de guillemets sur les cles).

**Raisons du rejet** :
- **Dependance non-stdlib** : le parsing YAML en Python necessite
  `PyYAML` (paquet pip externe). Ceci contredit la contrainte projet
  explicite "bash + Python stdlib + JSON par defaut" (cf. design §1 et
  ADR-0001). Introduire une dep pip pour la config runtime ouvrirait
  la porte a la meme question pour les autres composants — derive
  non voulue.
- **Ambiguites YAML** : YAML 1.1 contient des ambiguites (`yes/no`
  interpretes comme booleens, `01` comme octal, etc.) qui peuvent
  surprendre. JSON est strict et predictible.
- **Commentaires remplaceables** : le besoin de commentaires est
  couvert par la structure `defaults` + `overrides` (l'intent est
  explicite dans la structure) et par le header DEP-3 des `.patch`
  (le "pourquoi" humain est la).

## References

- Design doc §3.1 — layout `patches/` (consequence directe).
- Design doc §3.2 — schema detaille `series.json`.
- Design doc §3.3 — schema detaille `runtime.json`.
- Design doc §5.8 — arbitrage initial de la separation registre/runtime.
- SOA §4.4 — proposition initiale d'un `series.json` unique (alternative A
  ci-dessus).
- REV-0001 — 8eme question ouverte sur la separation registre logique vs
  runtime (motive l'arbitrage §5.8).
- REV-0003 — note methodo #5 recommandant la formalisation ADR (motive le
  present document).
- ADR-0001 — vendor submodule pristine + regeneration deterministe
  (contrainte amont : moteur idempotent, surface a tester claire).
