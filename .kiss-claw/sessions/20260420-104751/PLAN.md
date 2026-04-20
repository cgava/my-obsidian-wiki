# obsidian-wiki Vendor Patch System

## Goal
Construire un système de patches local, versatile et idempotent, pour corriger les anomalies du vendor `obsidian-wiki` non-forkable — chaque patch self-documenting, détectable par état (clean/patched/partial/dirty), appliqué interactivement, réversible, et survivant aux `git pull` du vendor. Inspiré de l'état de l'art des packagers open source (quilt/DEP-3/etc.).

## Non-goals
- Corriger les anomalies locales hors vendor (orphelins `knlg-repo/`, `~/.obsidian-wiki/config`, `knlg-repo/CLAUDE.md`) → session future
- Livrer phases 5 (cross-linking asymétrique s2→s0) et 6 (POC validation 2 chaînes LLM) → session future
- Workflow automatisé d'envoi de PR upstream (placeholder DEP-3 `Applied-Upstream` prévu, pas d'automation)
- Tester / modifier le mécanisme dual-zone déjà validé Phase 4 (wrapper `set-wiki-env.sh`, `.env.s0/.env.s2`)
- Support multi-vendor — mono-vendor pour l'instant, extensibilité = bonus

## Constraints
- Stack techno : bash + Python (stdlib + JSON) par défaut ; paquet pip/apt propre OK sans demander ; exotique = confirmation
- Self-documenting : chaque patch porte description complète (contexte, impact, référence §§ audit)
- Idempotent : détection avant apply (`clean | patched | partial | dirty`)
- Interactif par défaut : user choisit patch par patch ; `--all --yes` possible via flag explicite
- Versatile : ajout/retrait d'une anomalie = édition registre, pas du moteur
- Réversible : rollback par patch

## Phases

### Phase 1 — État de l'art — DONE (commit 34c482b)
- [x] Recherche quilt + DEP-3 (Debian) — format patches/series, headers metadata
- [x] Recherche Debian source format 3.0 (quilt) — structure packaging
- [x] Recherche Gentoo `etc-update` / `dispatch-conf` — merge interactif + drift detection
- [x] Recherche Nixpkgs patches, Arch PKGBUILD `prepare()`, RPM `%patch` — modèles déclaratifs
- [x] Recherche git-native : `format-patch` / `am`, stacked patches
- [x] Recherche idempotence : patterns Ansible/Puppet (check_mode, idempotent resources)
- [x] Recherche détection : checksum vs content-match vs `patch --dry-run`
- [x] Recherche outils Python : `unidiff`, `whatthepatch`
- [x] Livrable : `docs/260420-patch-system-soa.md` + recommandation architecture (format, langage, tooling)

### Phase 2 — Design architecture — DONE (commits c164ad4 + 52bc7f8)
- [x] Décision format storage (file-per-patch quilt-like vs registre unique YAML/TOML) → file-per-patch .patch + registre JSON (§3.1 design)
- [x] Structure "anomaly record" : id, title, description, audit_ref, severity, targets[], detection, apply, rollback → §3.2 schéma records[] (severity BLOCKING/TROMPEUR/COSMETIQUE/INFO, status lifecycle active/disabled/obsolete, patch_sha256 + target baseline/patched sha256)
- [x] Décision langage (bash pur / Python / mix) + dépendances validées → Python 3.10+ stdlib + bash dispatcher, unittest, zero dep pip
- [x] Conception UX CLI : list, status, describe, diff, apply, apply --all --interactive, rollback, verify → §4.1-4.4
- [x] Détection "partielle" pour patches multi-fichiers : agrégation par-fichier → état global → §3.2 + evaluate() multi-target
- [x] Arbitrage 8 points ouverts issus de Phase 1 §4.6 + notes verificator : tous tranchés §5.1-5.8
      (1) granularité : 1 patch = 1 thème multi-fichiers OK ;
      (2) auto-commit : non, apply laisse working tree sale ;
      (3) stratégie vendor : submodule pristine + régénération (ADR-0001) ;
      (4) DEP-3 : enrichi avec préfixe X-* dans headers (RFC 6648 nuancé) ;
      (5) upstream drift : escalade user par défaut, --auto-3way opt-in CI ;
      (6) tests : unittest stdlib ;
      (7) flock obligatoire sur ops mutantes ;
      (8) séparation series.json / runtime.json (ADR-0002)
- [x] Traiter notes verificator mineures : whatthepatch erratum §6.1, URLs §6.3 caveat, Python 3.10+ retenu §6.2
- [x] Livrable : `docs/260420-patch-system-design.md` (783 l) + ADR-0001 (236 l) + ADR-0002 (253 l)

### Phase 3 — Framework (moteur + pilote) — IN PROGRESS (8/16 jalons)

Plan détaillé 16 jalons en design §7. Groupement par livraison :

#### Jalons 1-4 — Squelette + registre + fixtures + detect sha256 — DONE (commit a3bf296, 31 tests)
- [x] J1 squelette : scripts/patch-system bash dispatcher + scripts/patch_system/ package Python
- [x] J2 registre : registry.py load/save/validate schema v1 (§3.2)
- [x] J3 fixtures : tests/fixtures/vendor-mini/ + vendor-mini-patched/ + 3 patches DEP-3 + series.json
- [x] J4 detect sha256 v1 : clean/patched/dirty/absent + agrégation multi-cibles

#### Jalons 5-8 — Detect composite + apply + rollback + CLI polish — DONE (commit a804caf, 67 tests)
- [x] J5 detect composite : evaluate() avec git apply --check (forward=clean+cosmetic / reverse=patched+cosmetic) + hunks split partial
- [x] J6 moteur apply v1 : git apply --index, idempotence, flock patches/.lock, updates last_applied/last_result
- [x] J7 rollback : git apply --reverse --index, garde-fou last_result==patched
- [x] J8 CLI polish : describe, diff, status format §4.4, --json mode, filtres list/status

#### Jalons 9-11 — Verify + refresh + pilote B3 réel — TODO
- [ ] J9 verify complet : recalcul patch_sha256, drift vendor, cohérence targets + exit codes §4.1 (0/1/2/3)
- [ ] J10 refresh : recalcul baseline/patched sha depuis l'état courant (après git pull vendor)
- [ ] J11 premier patch réel B3 (`vendor/.env` OBSIDIAN_RAW_DIR) + entrée series.json + README utilisateur (documenter convention patches/series.json + patches/*.patch co-located signalé REV-0005)

#### Jalons 12-16 — Interactif + all + fallback + intégration — TODO (hors batch courant)
- [ ] J12 apply mode interactif (etc-update-like y/n/s/d/3/r/q/? §4.2)
- [ ] J13 apply --all + rollback --all + --stop-on-fail
- [ ] J14 fallback patch(1) + --auto-3way + runtime.json overrides
- [ ] J15 patches B1/B2/B4 + p2-* ajout progressif
- [ ] J16 verify-in-CI (hook git ou .gitlab-ci.yml minimal)

### Phase 4 — Enregistrement anomalies vendor (subsumé dans J11-J15 Phase 3 si tout roule)
- [ ] Patch B1 — wiki-ingest fallback `$VAULT_PATH/_raw/` (→ J15)
- [ ] Patch B2 — wiki-ingest verification sécurité hardcodée (→ J15)
- [ ] Patch B4 — vendor/.env OBSIDIAN_RAW_DIR relatif (si pas subsumé par B3 selon design)
- [ ] Patch pattern "Read .env" (12 occurrences vendor/) — groupé 1 patch 12 targets (§5.1 granularité)
- [ ] Patch pattern "_raw/ in vault" (~5-6 occurrences vendor/) — groupé 1 patch
- [ ] Chaque patch : description complète + référence doc audit

### Phase 5 — Validation + doc mainteneur
- [ ] Scénario E2E 1 : vendor vierge (tous patches `clean`)
- [ ] Scénario E2E 2 : vendor partiellement patché (états mixtes)
- [ ] Scénario E2E 3 : vendor réinitialisé après `git pull` (re-detect → re-apply)
- [ ] Doc `knlg-repo/patches/README.md` — comment ajouter/retirer une anomalie
- [ ] Placeholder DEP-3 `Applied-Upstream` documenté pour l'avenir
