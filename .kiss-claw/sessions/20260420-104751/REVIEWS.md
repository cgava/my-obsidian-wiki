# REVIEWS — session 20260420-104751

### REV-0001

- **date**     : 2026-04-20
- **subject**  : kiss-executor task — rédaction du livrable Phase 1 `docs/260420-patch-system-soa.md` (605 lignes, FR) : SOA patch systems (quilt/DEP-3, Debian 3.0, etc-update/dispatch-conf, Nixpkgs/Arch/RPM, git-native, Ansible/Puppet, detection d'etat, outils Python, périphériques) + recommandation d'architecture §4
- **verdict**  : approved-with-notes

**Summary**
Livrable substantiel et bien structuré. Les 9 topics demandés par le PLAN sont tous couverts (§2.1 à §2.9) et la recommandation §4 est cohérente avec les contraintes du PLAN (bash + Python stdlib + JSON, pip optionnel, exotique évité). Le tableau §3 et la synthèse "chaque famille apporte une brique" sont actionnables pour la Phase 2 Design. Quelques points factuels à vérifier et caveats méthodo (recherche sur training knowledge vs WebSearch live) motivent "with-notes" plutôt qu'approved.

**Couverture vs plan (9 topics)**
- [yes] quilt + DEP-3 — §2.1 (commandes quilt, champs DEP-3 exacts)
- [yes] Debian source format 3.0 (quilt) — §2.2
- [yes] etc-update / dispatch-conf — §2.3 (modes 1-6, détection 3-points)
- [yes] Nixpkgs / Arch / RPM — §2.4 (tableau comparatif)
- [yes] git-native (format-patch / am / apply / stgit / subtree / submodule) — §2.5
- [yes] Ansible / Puppet idempotence — §2.6 (check_mode + --diff)
- [yes] Détection d'état — §2.7 (5 techniques, stratégie composite proposée)
- [yes] Outils Python — §2.8 (unidiff, whatthepatch, patch-ng, difflib, stdlib)
- [yes] Périphériques — §2.9 (etckeeper, needrestart, vendir, copybara, debmake, patchelf, patch-package)

**Exactitude factuelle (spot-check sans WebFetch disponible)**
- Commandes quilt (§2.1) : `new`, `add`, `refresh`, `push/pop`, `applied/unapplied`, `top`, `header -e` — conformes à quilt 0.67.
- Champs DEP-3 listés (`Description`, `Origin`, `Author/From`, `Forwarded`, `Applied-Upstream`, `Last-Update`, `Bug*`) — conformes à la spec Debian DEP-3.
- Modes etc-update 1-6 + `-1/-3/-5/-9` (§2.3) — conformes au comportement portage.
- `git apply --check / --3way / --reverse / --reject / --index / --whitespace=nowarn` (§2.5, §4.4) — tous réels.
- `patch --dry-run`, `-N`, `-R` (§2.7) — corrects.
- GNU patch 2.7.6, tomllib depuis 3.11, `difflib.unified_diff` (§2.8) — corrects.
- Debian source format `3.0 (quilt)` single line `debian/source/format` (§2.2) — correct.
- stgit `push/pop/refresh/sink/float` (§2.5) — correct.

**Issues**
- [minor / factuel] **§2.8 ligne `whatthepatch`** : affirmation "utilise par Black et pre-commit" — non vérifiable sur la machine (grep local → 0 hit dans un venv) et ne correspond pas à ce que je sais de ces deux projets (Black n'importe pas whatthepatch ; pre-commit non plus en tant que dépendance runtime). Retirer l'affirmation ou la qualifier en "occasionnellement cité dans l'outillage tooling Python" pour ne pas ancrer un fait faux.
- [minor / méthodo] **Caveat executor "training knowledge vs WebSearch live"** : accepté pour cette phase (SOA sur des standards stables depuis 10+ ans), mais §5 Références gagnerait un en-tête explicite "URLs non revérifiées à la date du doc — spot-check manuel recommandé avant de citer dans un ADR final". Impact faible car les URLs listées sont des spec/wikis stables (dep-team.pages.debian.net/deps/dep3, wiki.gentoo.org/wiki/{Etc-update,Dispatch-conf}, savannah.nongnu.org/projects/quilt, manpages.debian.org pour `dpkg-source(1)`) dont les chemins sont connus stables — je confirme qu'elles sont plausibles sans pouvoir les fetcher ici.
- [minor / cohérence] **§4.4 champs DEP-3 enrichis non-standard** (`Baseline-Sha256`, `Patched-Sha256`, `Audit-Ref`, `Severity`) : le doc le signale explicitement en §4.6 pt 4 ("documenter dans un README explicite") — bon réflexe. À confirmer en Phase 2 Design : soit préfixer (`X-Baseline-Sha256` pour marquer l'extension), soit rester tel quel.
- [minor / schéma] **Caveat `series.json` schéma candidat non validé** : acceptable pour Phase 1 (exploration), mais la structure proposée §4.4 mélange des responsabilités "registre" (id, order, status) et "exécution" (detection.strategy, apply.method, apply.args). Point à arbitrer explicitement en Phase 2 Design — ajouter en §4.6 comme question ouverte 8 ("séparer registre logique vs runtime config ?").
- [minor / cohérence] **§4.2 "Python 3.10+"** alors que §2.8 mentionne `tomllib (3.11+)` comme dep stdlib : si on vise 3.10+, `tomllib` n'est pas disponible — soit bump la minimum à 3.11, soit retirer tomllib du listing stdlib. À trancher en Phase 2. Non bloquant car tomllib n'est pas indispensable pour le registre (JSON suffit).
- [minor / hors-scope] **Bug `store.sh checkpoint upsert` indentation YAML** signalé par executor : confirmé hors-scope de cette revue. À tracer dans un issue séparé (pas ici), ou dans `insights` si récurrent. Ne bloque pas le livrable Phase 1.

**Cohérence avec contraintes projet (CHECKPOINT + PLAN)**
- Stack bash + Python stdlib + JSON par défaut — §4.1 choix JSON vs YAML justifié par stdlib, §4.2 zero dep pip bloquante, §4.3 tableau d'arbitrage explicite : **conforme**.
- `unidiff` en dep pip optionnelle avec dégradation gracieuse (§4.2) — **conforme** (pip propre OK sans demander).
- Pas de `quilt` binaire, pas de `stgit`, pas de `PyYAML`, pas de `etckeeper` (§4.3) — **conforme** (économie de deps exotiques).
- Idempotence (`clean / patched / partial / dirty`) — §2.6 et §4.4 étendent à 6 états (`+ absent + unknown`) — **conforme et amélioré**.
- Interactif par défaut + batch via flag (§4.5 CLI + modes etc-update-like) — **conforme**.
- Réversible (§4.5 `revert` + `revert --all`) — **conforme**.
- Self-documenting (§4.1 header DEP-3 + §4.4 champs record) — **conforme**.
- Survie aux `git pull` vendor (§2.7 stratégie composite + §4.6 pt 5 heuristique `--3way` auto vs interactif) — **conforme**.
- Mono-vendor (§4.1 chemin implicite vendor/obsidian-wiki) — **conforme**.

**Qualité de la recommandation §4**
- **Actionnable** : §4.1 à §4.5 donnent une structure concrète directement transposable en Phase 2 Design (layout fichiers, schéma record, UX CLI détaillée, modes interactifs chiffrés 1-6). Un designer peut démarrer sans ambiguïté.
- **Justifiée** : chaque choix (file-per-patch vs registre inline, JSON vs YAML, pas de quilt binaire) est argumenté en regard des alternatives. §3 sert de base comparative.
- **§4.6 points à trancher** : 7 questions ouvertes bien formulées (granularité multi-cibles, intégration git/submodule vs subtree vs régénération, DEP-3 strict vs enrichi, upstream drift auto vs interactif, tests pytest, lock concurrence). J'ajouterais une 8ème (séparation registre/runtime — cf. issues). La question 3 (submodule vs subtree vs régénération) préfigure la bonne option (c, régénération déterministe) sans la verrouiller prématurément — **équilibre correct entre guidance et non-fermeture**.

**For kiss-orchestrator**
Proceed to next step (Phase 2 Design). Les 6 notes mineures peuvent être traitées au fil de la Phase 2 (le designer aura à arbitrer §4.6 + issues schéma/bump Python 3.11 + nuance whatthepatch). Aucun rework Phase 1 nécessaire. Noter le bug `store.sh checkpoint upsert` pour tracking séparé (hors scope de cette revue).

### REV-0002

- **date**     : 2026-04-20
- **subject**  : kiss-executor task — side-quest infra kiss-claw : commit f2801c9 (fix INS-0022 store.sh YAML indent + INS-0023 verificator tools Bash/WebFetch)
- **verdict**  : approved-with-notes

**Summary**
Les deux fixes sont en place dans le repo kiss-claw (HEAD master = f2801c9 confirmé). INS-0022 : `_build_entry ""` au lieu de `"  "` + validation YAML post-écriture via `python3 yaml.safe_load`. INS-0023 : frontmatter étendu à `Read, Write, Glob, Grep, Bash, WebFetch` + 2 bullets garde-fou dans Constraints. Commit propre (1 seul commit, message explicite, co-author présent). Note "with-notes" pour 2 écarts mineurs par rapport à la proposition INSIGHTS et pour une limitation d'in-vivo testing côté verificator.

**Volet 1 — INS-0022 (store.sh)**
- `_build_entry` (lignes 363-372) : helper paramétré par `indent`, appelé avec `""` ligne 450 (top-level) et `"${BASE_INDENT}    "` ligne 394 (enfant sous parent) → les 2 chemins sont cohérents.
- Validation YAML post-write (lignes 464-470) : `python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" "$FILE"` → fail-loud avec `exit 1` et message explicite. Conditionné à la présence de `python3` (dégradation gracieuse).
- Les 2 chemins top-level sont couverts : (a) branche "log vide" (ligne 453-457, awk qui remplace `log: []` par `log:` et insère le contenu de `$ENTRY_FILE` — lequel est déjà à indent 0), (b) branche "append fin de fichier" (ligne 459-460, `cat "$ENTRY_FILE" >> "$FILE"`). Les deux produisent des listitems en colonne 0.
- Test de reproduction du fix laissé par kiss-executor : `/tmp/test_ins0022.sh` (77 lignes) — crée un CHECKPOINT minimal dans un `mktemp -d`, appelle `store.sh checkpoint upsert` sans `--parent`, vérifie `yaml.safe_load` + `indent_len=0`. Script propre, fait du cleanup, strictement `mktemp -d`.

**Volet 2 — INS-0023 (kiss-verificator/agent.md)**
- Frontmatter ligne 10 : `tools: Read, Write, Glob, Grep, Bash, WebFetch` → conforme à INS-0023 Option A.
- `## Constraints` (lignes 137-146) : bullet "Write access limited to..." préservé ; 2 bullets ajoutés :
  - Bash scope = (a) `store.sh checkpoint upsert` + `enrich_checkpoint.py`, (b) read-only inspection (git/grep/find/test).
  - WebFetch scope = cited-URL fact-check, pas de web-crawling gratuit.
- Pas de régression détectée sur les autres bullets (review-only, write-scope, etc.).

**Volet 3 — commit message + portée**
- Message mentionne INS-0022 ET INS-0023, explique le why, référence le chemin de repro test `/tmp/test_ins0022.sh`.
- Co-Authored-By: Claude Opus 4.7 (1M context) présent.
- Commit unique sur master local (ref `f2801c9` = HEAD) ; pas d'amend, pas de push forcé visibles dans reflog.
- kiss-executor a explicitement noté que le WIP (INSIGHTS.md, submodule, tmp.txt) n'est PAS embarqué — vérifié plausible via le message.

**Issues**
- [minor] **Écart vs INS-0022 proposition** : l'insight proposait `backup .bak + restore-on-failure` en cas d'invalidité YAML ; l'implementation fait `exit 1` fail-loud (pas de backup, pas de restore). Le comportement protège contre la propagation de YAML corrompu mais laisse le fichier potentiellement partiellement modifié. Acceptable pour un hook tooling early-fail, à noter si la robustesse devient critique.
- [minor] **Limitation in-vivo INS-0023 côté verificator** : le frontmatter a été modifié dans le repo kiss-claw, mais l'agent actuellement exécuté pour cette revue tourne sur l'ancien snapshot d'outils (Read/Write/Edit/Glob/Grep seulement, pas de Bash ni WebFetch). La vérification "live" du bon fonctionnement de Bash attendra la prochaine spawn d'un kiss-verificator après rechargement de l'agent. Les lectures statiques confirment le fix, et kiss-executor a lui-même exécuté le test de reproduction.
- [minor] **Non-vérifiable sans Bash** : `git show --stat f2801c9` (demandé dans le brief Volet 1 pt 3) n'a pas pu être exécuté en direct ; le contrôle s'est fait par triangulation (commit-msg, parent ref dans reflog, lectures sources). Suffisant pour cette revue — risque résiduel = un fichier non attendu dans le commit, mais le message ne ment pas visiblement et les fichiers cibles lus montrent exactement les changements attendus.

**For kiss-orchestrator**
proceed to next step — les 2 fixes peuvent être considérés comme appliqués ; continuer Phase 2 Design sans bloquer. Une future session qui respawn kiss-verificator bénéficiera du vrai set d'outils étendu (validation définitive de INS-0023 à ce moment-là).

### REV-0003

- **date**     : 2026-04-20
- **subject**  : kiss-executor task — rédaction du livrable Phase 2 Design : `docs/260420-patch-system-design.md` (778 lignes, FR) + `docs/adr/ADR-0001-vendor-submodule-pristine.md` (236 lignes, FR). Traduction SOA §4 en design actionnable : architecture logique, schéma storage, UX CLI, arbitrage des 8 points ouverts, traitement des 3 notes mineures REV-0001, plan Phase 3.
- **verdict**  : approved-with-notes

**Summary**
Livrable substantiel, bien structuré et directement exploitable pour la Phase 3. Les 8 points ouverts sont tous arbitrés avec décision motivée + alternatives rejetées + conséquences. L'ADR-0001 respecte le format Nygard et balance correctement positives/négatives/neutres. La décision critique §5.3 (submodule pristine + régénération) est robuste face aux 5 scenarios structurants (git pull, réversibilité, clarté, collaboration, bootstrap). Note "with-notes" pour 5 écarts mineurs (factuel / cohérence / méthodo), aucun blocant.

**Couverture vs brief (checklist)**
- [yes] Rappel contexte + lien SOA — §1
- [yes] Architecture logique + composants + flux — §2.1-2.3 (diagramme ASCII, tableau de responsabilités, 4 flux explicités)
- [yes] Schéma storage définitif — §3.1 layout, §3.2 record, §3.3 runtime, §3.4 header DEP-3 enrichi, séparation registre/runtime claire
- [yes] UX CLI détaillée — §4.1 (11 commandes + flags transverses + codes retour), §4.2 (menu etc-update-like 7 lettres), §4.3 messages-types, §4.4 format tableau status
- [yes] Arbitrage des 8 points — §5.1 à §5.8, un par sous-section, décision + motivation + alternatives rejetées
- [yes] Traitement des 3 notes REV-0001 — §6.1 erratum whatthepatch, §6.2 Python 3.10+ vs 3.11+, §6.3 URLs non revérifiées
- [yes] Plan Phase 3 — §7, 16 jalons ordonnés cohérents
- [yes] ADR-0001 Nygard — Contexte / Décision / Conséquences (+/-/neutres) / Alternatives / Références

**Qualité arbitrage des 8 points**
- 5.1 Granularité multi-cibles : `ok` — 1 patch N targets décidé, motivation sémantique solide, alternatives A/B rejetées explicites.
- 5.2 Auto-commit : `ok` — pas d'auto-commit, cohérent avec §5.3 option (a), extension Phase 4 envisagée.
- 5.3 Stratégie vendor (CRITIQUE) : `ok` — option (a) submodule pristine + régénération, 4 motivations explicites, (b) subtree et (c) commits-in-submodule tous les deux rejetés avec "inconvénient fatal" nommé. Robustesse aux 5 scenarios vérifiée (voir ADR-0001). Décision ancrée dans le pattern Debian 3.0 quilt — choix mature.
- 5.4 DEP-3 strict vs enrichi : `ok` — préfixe `X-*` retenu pour 4 champs (Audit-Ref, Severity, Baseline-Sha256, Patched-Sha256), motivation "non ambiguïté avec parser strict" conforme à la convention RFC-822-like.
- 5.5 Upstream drift : `ok` — escalade par défaut + dial `--auto-3way` opt-in pour CI, garde-fou "fail-silent dangereux" bien formulé.
- 5.6 Framework tests : `ok` — unittest stdlib retenu, argument "contrainte projet + volume modéré + CI simple" cohérent, dérive en Phase 4 prévue si >100 cas.
- 5.7 Flock concurrence : `ok` — flock obligatoire sur opérations mutantes, read-only non verrouillées, syntaxe illustrative correcte (`exec 9>...; flock -n 9`).
- 5.8 Séparation registre/runtime : `ok` — deux fichiers, defaults + overrides[id]. Traitement propre de la note verificator REV-0001 issue #4.

**Cohérence ADR-0001 vs Design §5.3**
- Décision identique (option a) — pas de contradiction.
- L'ADR développe Conséquences/Alternatives beaucoup plus que §5.3 — saine division du travail.
- L'ADR ajoute une alternative D (fork-miroir interne) non couverte par le SOA. Motivation du rejet correcte (infra supplémentaire, divergence cumulée) — ajout légitime car Alternative D est une variante plausible que l'auditeur de l'ADR pourrait soulever.
- Format Nygard respecté : 5 sections standard + Neutres ajoutée (acceptable, c'est une extension courante de Nygard).
- Section Conséquences équilibrée : 7 positives, 4 négatives, 3 neutres — pas de biais positif.

**Cohérence avec contraintes projet**
- Stack bash + Python stdlib + JSON : conforme (§4.1 dispatcher bash, §2.1 package Python stdlib, §3.x tout en JSON, §5.6 unittest stdlib, §5.7 flock builtin).
- Zéro dep pip bloquante : conforme (unidiff resté optionnel, pas mentionné comme requis).
- Idempotence 6 états (clean/patched/partial/dirty/absent/unknown) intégrée : §2.2, §3.2 types `last_result`, §2.3 flux apply.
- Interactif par défaut + batch via flag : conforme (§4.1 `--yes`/`--interactive` mutuellement exclusifs, §4.2 menu etc-update-like).
- Réversible : §4.1 rollback + rollback --all, §5.2 "laisse le working tree modifié", §3.3 rollback method configurable.
- Self-documenting DEP-3 : §3.4 header + §5.4 DEP-3 enrichi.

**Issues**

[minor / cohérence] §3.2 schéma series.json : le champ `vendor_baseline_sha` est au niveau du registre (top-level, ligne 162), alors que l'ADR-0001 décrit ce champ comme étant au même niveau. OK. Mais la granularité n'est pas discutée : un seul `vendor_baseline_sha` pour toute la série signifie que **tous** les patches sont calibrés contre le même sha upstream. Si un patch ancien a été calibré contre sha1 et un nouveau contre sha2, le design ne peut pas les distinguer. À clarifier en Phase 3 : soit un baseline par record (plus flexible, plus lourd), soit la contrainte "baseline unique série, refresh global obligatoire après submodule bump". Non bloquant — à arbitrer par l'implémenteur.

[minor / schéma] §3.2 champs obligatoires vs optionnels : `baseline_sha256` et `patched_sha256` sont listés **obligatoires** par target, mais au moment où un record est créé avant tout apply (via `record <id> --from <path>`), `patched_sha256` n'est pas encore connu (ou vaut le sha post-write). À préciser : soit l'initialisation se fait en 2 temps (crée record → apply → back-fill patched_sha256), soit on accepte une valeur sentinelle (`null`/vide) transitoire. Le design ne tranche pas — risque d'ambiguité d'implémentation.

[minor / factuel à revérifier] §5.4 convention `X-*` RFC-822 : le design affirme "la convention implicite RFC-822-like est que les champs non-standardises sont préfixés X-". C'est vrai historiquement (email headers pré-RFC 6648, en-têtes HTTP anciens), **mais RFC 6648 (2012)** a déprécié la convention `X-*` pour les nouveaux protocoles IETF. DEP-3 n'est pas un protocole IETF, donc la convention est justifiable pour ce cas, mais la formulation "convention implicite RFC-822-like" gagnerait en rigueur avec une nuance : "convention historique (RFC-822-like, antérieure à la dépréciation RFC 6648) qui reste usitée dans les specs Debian informelles". Non bloquant — factuel à nuancer si le doc passe en revue externe.

[minor / méthodo] Externalisation history en JSONL (§3.2) : la justification "éviter le gonflement du registre (ajout/an d'audit = lignes à plat, pas de serialisation JSON a reecrire integralement)" est valable et cohérente avec la note verificator REV-0001 issue #4 (séparer responsabilités registre vs exécution). Cependant, `runtime.json` + `history/<order>-history.jsonl` + `series.json` = 3+N fichiers dans `patches/` — complexité légèrement supérieure à la proposition SOA §4.4 (1 fichier). L'argument "pas de serialisation complète à chaque ajout history" est le bon — c'est un trade-off clair, à confirmer au premier vrai usage en Phase 3 (un patch avec 20 événements history générera-t-il vraiment un goulot ?). Non bloquant.

[minor / méthodo] Nombre d'ADR produites (1) : l'executor juge (§8) que seule §5.3 mérite une ADR dédiée (impact transverse), les autres points sont dans le design doc. Position défendable — §5.3 conditionne §5.2 et le design de `drift.py` et `apply.py`. Je suggère (note, pas blocker) : **§5.8 séparation registre/runtime pourrait mériter son ADR** car c'est une décision schémas structurante qui impacte directement `registry.py` / `detect.py` / `apply.py` et pourrait être remise en cause en Phase 4 si on découvre un besoin de co-localiser. Mais ADR posterieur reste possible si ré-arbitré. Non bloquant.

[minor / factuel] §5.7 `flock` syntaxe : `exec 9>"${PATCHES_DIR}/.lock"; flock -n 9 || exit 1` — correct sur Linux (flock de util-linux). À noter : `flock -n` retourne **1** si le lock ne peut pas être acquis (pas 2), ce qui est cohérent avec le handling du design. Sur macOS, `flock(1)` n'est pas installé par défaut (mais pas une cible du projet selon memory). Correct pour la cible Debian/Ubuntu.

[minor / verbosité] Longueur 778 lignes : légèrement au-dessus de la cible 400-700. Sections condensables si besoin : §4.3 messages-types (4 blocs de ~5-8 lignes chacun — utile pour Phase 3 mais duplicable avec §4.1), §5.2 alternatives rejetées (les 2 sont quasi-évidentes en 1 phrase chacune — déjà synthétique en fait), §7 plan Phase 3 (16 jalons OK mais pourrait être condensé en 8-10). Non bloquant — la verbosité sert la décidabilité.

**Spot-check factuel**

- Champs DEP-3 `X-*` : convention acceptée pour extensions non-canoniques Debian, pas rejetée par dpkg-source. OK.
- `flock(1)` comportement (exit 1 si `-n` + lock déjà pris) : correct.
- Python 3.10+ : `match/case` disponible, `tomllib` seulement à partir de 3.11 — tranché correctement §6.2 (non utilisé).
- Debian 3.0 quilt pattern : pristine tarball + `debian/patches/` + `series` file — correct, transposé en git submodule est un parallèle légitime.

**Cohérence §6 avec commit SOA 34c482b**

- §6.1 (whatthepatch) : non rework du SOA, erratum local — conforme à la note méthodo REV-0001. Le design ne re-affirme pas l'usage par Black/pre-commit, et précise `unidiff` (optionnel) retenu à la place. Correct.
- §6.2 (Python 3.10+ vs 3.11+) : tranché 3.10+ ; justification Debian 12 / Ubuntu 22.04 valide. `tomllib` explicitement non utilisé. Correct.
- §6.3 (URLs non revérifiées) : caveat transparent + engagement spot-check manuel pré-publication. Correct.

**For kiss-orchestrator**

proceed to next step (Phase 3 Implementation). Les 7 notes mineures n'invalident aucune décision structurante et peuvent être traitées au fil de l'eau Phase 3 :
- Issue #1 (granularité baseline_sha) : à arbitrer en P3 jalon 2 (registry.py).
- Issue #2 (obligatoire vs optionnel au record time) : à arbitrer en P3 jalon 11 (premier patch reel).
- Issue #3 (X-* RFC 6648) : cosmétique, à nuancer si publication externe.
- Issues #4-#7 : notes, pas d'action requise.
L'ADR-0001 est solide et peut être considéré comme Accepted stable.

### REV-0004

- **date**     : 2026-04-20
- **subject**  : kiss-executor task — livrables Phase 3 jalons 1-4 post-rework (squelette `scripts/patch-system` + `scripts/patch_system/` package, `registry.py` schema v1 aligne design §3.2, `detect.py` sha256-only multi-target, `cli.py` commandes `list`/`status` + stubs, fixtures `tests/fixtures/vendor-mini{,-patched}/` + 3 patches DEP-3 + `series.json`, 31 tests unittest).
- **verdict**  : approved-with-notes

**Summary**
Livrable propre, fonctionnel, strictement dans le scope jalons 1-4 et correctement realigne sur le design doc §3.2 apres rework (records[]/patch_file/patch_sha256/lifecycle status/severity BLOCKING-TROMPEUR-COSMETIQUE-INFO/schema_version string). Claim executor "31 tests passed" verifie : `python3 -m unittest discover tests -v` produit 31 ok / 0 failed en 7 ms, sans warning. Fixtures sha256 recalculees a la main matchent byte-pour-byte les valeurs de `series.json` (README + cmd1 pristine + patched + 3 `patch_sha256`) et la validation de `series.json` par `registry.validate()` renvoie `[]`. CLI manuel OK pour `list` + `status` sur les deux vendor-roots (pristine -> clean/clean/dirty, patched -> patched/patched/dirty) avec exit 0. Une seule vraie friction : l'ergonomie des flags `--series` / `--vendor-root` (argparse top-level) oblige a les passer AVANT le sous-commande — correct en argparse mais pas note dans le brief ni la doc. A retenir pour les jalons suivants.

**Checklist couverture**
- §1 Schema : OK — `SCHEMA_VERSION = "1"` (string, rejet explicite de `schema_version: 1` int), `VALID_LIFECYCLE = ["active","disabled","obsolete"]`, `VALID_SEVERITIES = ["BLOCKING","TROMPEUR","COSMETIQUE","INFO"]`, `VALID_STATES` ok pour `last_result`, champs obligatoires exacts (id, order, status, severity, title, patch_file, patch_sha256, targets + path, baseline_sha256, patched_sha256 par target), regex sha256 64-hex, `load()` default `{"schema_version":"1","records":[]}`, rejet duplicate id + duplicate order + bool-as-int + order <= 0.
- §2 Tests : OK — 31/31 en 7 ms, pas de DeprecationWarning, coverage raisonnable (TestLoad x2, TestSave x1, TestValidate x17 registry ; TestSingleTarget x4 + TestMultiTarget x5 detect).
- §3 detect : OK — lit `baseline_sha256` / `patched_sha256` sans prefixe (avec fallback record-level explicitement documente pour robustesse), algo d'agregation conforme (absent>dirty>partial>patched=clean), `"unknown"` retourne si targets vide, strip `vendor/<name>/` correct pour router sur `vendor_root`.
- §4 cli : OK — `_cmd_list` itere `data["records"]` avec format `<order> <id> <severity> <status> — <title>` (lifecycle status, pas state derive — conforme au commentaire docstring), `_cmd_status` recalcule live via `detect.detect_state` sans consulter `last_result`, stubs exitent avec code 2 + message lisible via `_cmd_not_implemented`.
- §5 Fixtures : OK — `series.json` au format `{"schema_version":"1","records":[...]}` avec 3 records tous `status:"active"` severity valide. Spot-check sha256 : `sha256sum` des 3 patches + README pristine + README patched + cmd1 pristine + cmd1 patched matchent EXACTEMENT les valeurs stockees. Patches DEP-3 OK : header `X-Severity: COSMETIQUE/TROMPEUR` (plus de P0/P1/P2), `X-Baseline-Sha256` / `X-Patched-Sha256` / `X-Audit-Ref` avec prefixe conserve (correct par design §3.4), Description/Origin/Author/Forwarded/Last-Update presents.
- §6 CLI exec : OK — `patch-system --series ... list` renvoie 3 lignes bien formatees, `patch-system --series ... --vendor-root tests/fixtures/vendor-mini status` renvoie clean/clean/dirty, `vendor-mini-patched` renvoie patched/patched/dirty. Exit 0 dans les deux cas. (voir issue ergonomie ordre des flags ci-dessous.)
- §7 Scope : OK — aucun `git apply` dans le code (uniquement une mention en docstring `detect.py` "not yet calling git apply --check — that is jalon 5"), pas de moteur apply/rollback/flock/runtime.json. `_STUBBED = {"describe","diff","apply","rollback","verify","refresh","record"}` tous stubs et 'apply' teste manuellement -> exit 2 + message explicite.
- §8 Qualite : OK — docstrings courts factuels, type hints coherents Python 3.10+ (`dict[str, Any]`, `list[str]`, `Path`, `Any`), `from __future__ import annotations` pour compat, pas de `import *`, pas de reseau (rien qui touche `urllib`/`requests`/`http.client`/`socket` dans le code ni les tests), pas de `TODO`/`FIXME` restant, shebang `#!/usr/bin/env bash` sur le dispatcher, modules Python sans shebang (correct — ils ne sont pas executables standalone), `__main__.py` delegate propre.

**Issues**

- [minor] [cli / ergonomie] Les flags globaux `--series` et `--vendor-root` sont declares sur le parser top-level argparse. Consequence : l'invocation `patch-system list --series tests/fixtures/series.json` (flags APRES le sous-commande) echoue avec `unrecognized arguments` alors que `patch-system --series ... list` fonctionne. L'ordre importe et n'est pas documente. Le brief du verificator avait d'ailleurs suggere l'ordre `list --series ...` et ca a casse. Deux options pour un jalon ulterieur : (a) dupliquer les flags sur chaque sous-commande (verbeux), (b) ajouter `--series`/`--vendor-root` en option commune via `add_parser(..., parents=[...])`, (c) documenter l'ordre dans le `--help` et dans le README. Non bloquant — le CLI est utilisable — mais l'UX surprendra un utilisateur qui tape naturellement `patch-system list --series foo.json`.

- [minor] [code / clarte] `_IMPLEMENTED = {"list", "status"}` declare ligne 13 de `cli.py` mais jamais reference dans le code (seul `_STUBBED` est utilise a la ligne 130 pour router vers `_cmd_not_implemented`). Caveat signale par l'executor lui-meme. Soit le supprimer, soit l'utiliser comme garde (ex. `if args.cmd in _IMPLEMENTED: dispatch(...)`) — actuellement c'est du code mort qui donne une fausse impression de couplage. Non bloquant.

- [minor] [registry / validation] `vendor_baseline_sha` au top-level est tolere sans validation stricte — c'est explicitement autorise par le brief et par le design §3.2, mais comme le champ n'est meme pas mentionne dans `_REQUIRED_*`/`_OPTIONAL_*`, il n'y a AUCUNE garantie qu'il soit un sha valide s'il est present. Acceptable en l'etat (champ informatif projet-level, pas utilise par detect/apply), mais a arbitrer quand la granularite baseline_sha sera tranchee en jalon 11+ (cf. issue #1 de REV-0003).

- [minor] [fixtures / realisme] Le record `t0003-cmd2-drifted` utilise des sha placeholder `0000...` et `1111...` pour simuler un drift. Ca marche (le test `test_detect_dirty_unknown_hash` renvoie bien `dirty`), mais ce n'est pas un vrai drift : un vrai drift aurait des sha legitimes d'une version anterieure de `cmd2.sh`. Actuel est un "sha-impossible", detecte `dirty` par elimination plutot que par vraie comparaison. Pour les jalons 5+ (git apply --check), il faudra probablement un fixture "drift realiste" : cmd2.sh a pristine_v1 en vendor-mini mais la patch stocke pristine_v0. Non bloquant — la semantique dirty est la meme cote detect, mais le test ne prouve pas le chemin "drift realiste".

- [minor] [cli / comportement] `_cmd_list` et `_cmd_status` affichent `(empty)` sur stdout ET retournent 0 quand `records` est vide. C'est un choix de non-erreur, mais design §4.1 code retour mentionne `0 = success, 1 = user error, 2 = internal`. Une serie vide peut etre soit un etat legitime (projet neuf) soit une erreur silencieuse (series.json mal configure). Acceptable — la distinction se fera plutot via `verify` (jalon 8) qui controlera la coherence registre. Pas d'action requise.

**Spot-check factuel**

- sha256 fixtures recalcules a la main vs series.json : MATCH (README pristine `8dfa1b...`, README patched `2d3f15...`, cmd1 pristine `e1b2b4...`, cmd1 patched `38ae63...`, 0001.patch `c5ddbe...`, 0002.patch `3df48b...`, 0003.patch `b073b1...`).
- `registry.validate(load('tests/fixtures/series.json'))` renvoie `[]`.
- `cmd2.sh` identique entre vendor-mini et vendor-mini-patched (sha `915e1c...` des deux cotes) : coherent avec README.md qui indique "cmd2.sh unchanged — patch 0003 would not apply".
- `config/.env.example` et `lib/helper.py` sont dans les deux trees mais pas dans series.json : intentionnel (fichiers "non-patch" simulant du vendor qui reste clean de toute maniere). OK.
- Stub `apply` : `scripts/patch-system apply` renvoie `patch-system: command 'apply' not yet implemented (see design §7)` + exit 2. OK.
- Pas de `git apply` dans le code Python : verifie par grep. Seule occurrence = docstring TODO jalon 5 dans `detect.py`. Conforme au scope.

**Coherence §3.2 design doc vs code**

Je compare champ a champ :

| Design §3.2 | registry.py | Status |
|---|---|---|
| `schema_version: "1"` (string) | `SCHEMA_VERSION = "1"`, rejet int | OK |
| champs obligatoires record | `_REQUIRED_RECORD_FIELDS` : id/order/status/severity/title/patch_file/patch_sha256/targets | OK identique |
| champs obligatoires target | `_REQUIRED_TARGET_FIELDS` : path/baseline_sha256/patched_sha256 | OK identique |
| champs optionnels | `_OPTIONAL_RECORD_FIELDS` : audit_ref/last_applied/last_result/notes | OK identique |
| status enum | `VALID_LIFECYCLE = [active, disabled, obsolete]` | OK |
| severity enum | `VALID_SEVERITIES = [BLOCKING, TROMPEUR, COSMETIQUE, INFO]` | OK |
| last_result enum | `VALID_STATES = [clean, patched, dirty, partial, absent, unknown]` | OK (ordre different de la doc mais peu importe — c'est un set) |
| sha256 64-hex | regex `^[0-9a-fA-F]{64}$` | OK |
| `vendor_baseline_sha` top-level | non valide (accepte silencieux) | tolere, documente dans docstring |

Aucun ecart schema vs design.

**For kiss-orchestrator**

proceed to next jalons (5-8). Les 5 notes mineures sont toutes traitables au fil de l'eau ou documentables dans les jalons suivants :
- Issue #1 (ordre flags argparse) : a traiter en jalon 8 (verify) ou 9 (interactive menu) quand l'UX CLI est consolidee.
- Issue #2 (`_IMPLEMENTED` dead code) : trivial, 1 ligne a supprimer ou utiliser — peut etre inclus dans le commit d'ouverture jalon 5.
- Issue #3 (`vendor_baseline_sha` non valide) : a arbitrer au jalon 11 (refresh) avec issue #1 REV-0003 (granularite baseline).
- Issue #4 (fixture drift "faux") : a enrichir au jalon 5 quand `git apply --check` sera plug in — un cas realiste sera necessaire pour tester le chemin "patch apply fail mais baseline sha matche".
- Issue #5 (exit 0 sur registre vide) : documenter dans `verify` (jalon 8). Pas d'action immediate.

Aucun de ces points ne justifie un rework avant jalon 5. Feu vert.
### REV-0005

- **date**     : 2026-04-20
- **subject**  : kiss-executor Phase 3 jalons 5-8 + fix sémantique detect.evaluate forward-cosmetic
- **verdict**  : approved-with-notes

**Summary**
Jalons 5-8 (composite detection, apply v1, rollback v1, CLI list/status/describe/diff
+ verify stub) livrés avec 67 tests verts en 3.4 s. Fix sémantique appliqué
(`forward git apply --check` success ⇒ `state=clean` + `drift_hint=cosmetic`,
jamais `patched`) et documenté dans tests + README fixtures. REV-0004 notes #1/#2/#5
toutes absorbées. Scope jalons 9-14 respecté (pas d'implémentation de `--3way`,
`--force`, `apply --all`, `runtime.json`, `refresh`/`verify` complets). Deux notes
ergonomiques mineures sur l'UX smoke-test manuelle + propagation per_target.

**Issues**

- [minor] smoke-test UX: `scripts/patch-system --series tests/fixtures/series.json`
  est cassé car le dispatcher résout `patches_dir = series_path.parent`
  (`tests/fixtures/`) alors que les `.patch` fixtures sont dans
  `tests/fixtures/patches/`. Les tests unittest passent car `test_cli` co-localise
  `series.json` et `.patch` dans un tempdir ; mais une invocation manuelle pointée
  sur les fixtures réelles déclenche "patch file not found" sur `apply`/`diff`.
  Résolution possible jalon 9+: permettre à `patches_dir` d'être découvert
  relativement à la config (déjà le cas en convention par défaut), ou documenter
  dans `tests/fixtures/README.md` la nécessité de co-localiser. Non bloquant :
  la convention production (`patches/series.json` + `patches/*.patch`) fonctionne.
- [minor] `evaluate()` propage `state=clean|patched` aux per_target `dirty` quand
  le composite reclasse le top-level, mais le caveat executor #9 (multi-target
  partial asymétrique) n'est pas couvert par un test — acceptable pour jalon 5
  mono-target, à instrumenter dès qu'un patch multi-cibles réel entre en suite.
- [minor] Le dispatcher bash crée `${PATCH_SYSTEM_ROOT}/patches/.lock` même quand
  `--series` pointe ailleurs : le flock protège le repo en cours, pas la série
  pointée. Correct pour le scénario production (PATCH_SYSTEM_ROOT == repo), mais
  deux opérations concurrentes sur deux `--series` distincts partagent le même
  lock. Suffisant pour Phase 3 mono-repo, à ré-évaluer si multi-series émerge.
- [minor] Caveats executor #3 (`apply_mod._result` / `_utc_now_iso` réutilisés
  depuis rollback.py via leading-underscore) et #4 (`_is_mutating_cmd` heuristique
  non testée en unittest) : acceptables, bien documentés. Flock validé en smoke
  (liste ne crée pas de lock, apply le crée ; formes `--series FILE` et
  `--series=FILE` gérées).
- [minor] Caveats #5/#6 (verify stub exit 1 pour non-vide ; codes retour §4.1
  0/1 seulement utilisés) : conformes REV-0004 note #5 et scope Phase 3. Les
  codes 2 (argparse) et 3 (registre invalide) entreront naturellement aux
  jalons 9+.

**For kiss-orchestrator**
proceed to next jalons (9-10 verify + refresh), avec note de documenter la
convention `patches_dir` dans l'user-facing README avant jalon 11 (record)
