# POC obsidian-wiki — Formation guidée par l'exploration

**Démarré :** 2026-04-14
**Vault :** `knlg-repo` (`/home/omc/workspace/my-obsidian-wiki/knlg-repo`)
**Repo :** `vendor/obsidian-wiki`
**Objectif :** Explorer chaque aspect d'obsidian-wiki pour en comprendre les grands principes, avant de spécifier ses propres exigences. Chaque phase produit un article-guide dans le vault.

---

## Principe du guide

Chaque phase suit le même schéma :
1. **Exécuter** la fonctionnalité testée
2. **Constater** les résultats (fichiers créés, structure, contenu)
3. **Rédiger** un article wiki `guide/phase-NN-nom.md` dans le vault, qui documente :
   - Ce que fait la fonctionnalité (principe, pas juste la commande)
   - Les commandes/skills utilisés
   - Comment parcourir le résultat dans Obsidian pour constater par soi-même
   - Les observations, limites, et idées pour sa propre version

L'article est lui-même une page wiki valide (frontmatter, wikilinks, tags).

---

## Phase 0 — Setup & Configuration ✅

**Skill testé :** `wiki-setup`
- [x] 0.1 — Corriger `.env` : `OBSIDIAN_VAULT_PATH=/home/omc/workspace/my-obsidian-wiki/knlg-repo`
- [x] 0.2 — Exécuter `wiki-setup` pour initialiser le vault
- [x] 0.3 — Vérifier la structure créée (dossiers, index, manifest, taxonomy)
- [x] 0.4 — Rédiger `guide/00-setup.md`

**Livrable :** Vault initialisé + article guide

---

## Phase 1 — Ingest de documents ✅

**Skill testé :** `wiki-ingest`
- [x] 1.1 — Créer 3 documents source de test dans `knlg-repo/_raw/`
- [x] 1.2 — Exécuter `wiki-ingest` sur ces sources
- [x] 1.3 — Vérifier : pages créées, frontmatter, wikilinks, provenance
- [x] 1.4 — Tester delta : re-run ingest → sources SKIP (hash identique)
- [x] 1.5 — Poser une note dans `_raw/` et ingérer → promotion automatique
- [x] 1.6 — Rédiger `guide/01-ingest-documents.md`

**Livrable :** 13 pages wiki + article guide

---

## Phase 2 — Ingest historique Claude ✅

**Skills testés :** `claude-history-ingest`, `wiki-history-ingest`
- [x] 2.1 — Exécuter `claude-history-ingest` (6 projets, 17 pages)
- [x] 2.2 — Vérifier les pages produites (patterns, décisions, concepts)
- [x] 2.3 — Tester le routeur unifié `wiki-history-ingest claude`
- [x] 2.4 — Rédiger `guide/02-history-ingest.md`

**Livrable :** 17 pages de connaissances historiques + article guide

---

## Phase 3 — Data ingest (formats libres) ✅

**Skill testé :** `data-ingest`
- [x] 3.1 — Créer un faux transcript de réunion (markdown)
- [x] 3.2 — Créer un faux export JSON style ChatGPT
- [x] 3.3 — Exécuter `data-ingest` sur ces sources
- [x] 3.4 — Vérifier les pages produites et la détection de format
- [x] 3.5 — Rédiger `guide/03-data-ingest.md`

**Livrable :** 5 pages + 1 update + article guide

---

## Phase 4 — Query & Recherche

**Skill testé :** `wiki-query`
- [ ] 4.1 — Query mode normal sur un concept existant
- [ ] 4.2 — Query mode index-only ("quick answer")
- [ ] 4.3 — Query sur concept inexistant → comportement gracieux
- [ ] 4.4 — Rédiger `guide/04-query.md`

**Livrable :** Article guide avec exemples de queries et réponses

---

## Phase 5 — Status & Lint

**Skills testés :** `wiki-status`, `wiki-lint`
- [ ] 5.1 — `wiki-status` : rapport sur l'état du vault
- [ ] 5.2 — `wiki-status insights` : analyse du graphe, hubs, bridges
- [ ] 5.3 — Créer une page orpheline + un wikilink cassé
- [ ] 5.4 — `wiki-lint` : détection des orphans, broken links, frontmatter manquant
- [ ] 5.5 — Rédiger `guide/05-status-lint.md`

**Livrable :** Rapports d'audit + article guide

---

## Phase 6 — Cross-linker & Tag Taxonomy

**Skills testés :** `cross-linker`, `tag-taxonomy`
- [ ] 6.1 — `cross-linker` : auto-insertion de wikilinks manquants
- [ ] 6.2 — Vérifier les liens ajoutés (scoring, confiance)
- [ ] 6.3 — `tag-taxonomy` : audit et normalisation des tags
- [ ] 6.4 — Rédiger `guide/06-crosslinker-tags.md`

**Livrable :** Vault mieux lié + article guide

---

## Phase 7 — Wiki Update (cross-project)

**Skill testé :** `wiki-update`
- [ ] 7.1 — Exécuter `wiki-update` depuis le repo `my-obsidian-wiki`
- [ ] 7.2 — Vérifier la page projet créée
- [ ] 7.3 — Re-run → test delta (last_commit_synced)
- [ ] 7.4 — Rédiger `guide/07-wiki-update.md`

**Livrable :** Page projet + article guide

---

## Phase 8 — Export du graphe

**Skill testé :** `wiki-export`
- [ ] 8.1 — Exécuter `wiki-export` → graph.json, graph.graphml, cypher.txt, graph.html
- [ ] 8.2 — Vérifier chaque format de sortie
- [ ] 8.3 — Rédiger `guide/08-export.md`

**Livrable :** Fichiers d'export + article guide

---

## Phase 9 — Rebuild & Archive

**Skill testé :** `wiki-rebuild`
- [ ] 9.1 — `wiki-rebuild archive` → snapshot
- [ ] 9.2 — Simuler corruption (supprimer quelques pages)
- [ ] 9.3 — `wiki-rebuild restore` → restauration
- [ ] 9.4 — Vérifier l'intégrité post-restore
- [ ] 9.5 — Rédiger `guide/09-rebuild-archive.md`

**Livrable :** Archive testée + article guide

---

## Phase 10 — Skill Creator

**Skill testé :** `skill-creator`
- [ ] 10.1 — Créer un skill "weekly-journal-summary"
- [ ] 10.2 — Vérifier le SKILL.md généré
- [ ] 10.3 — Rédiger `guide/10-skill-creator.md`

**Livrable :** Skill créé + article guide

---

## Phase 11 — Synthèse & Verdict

- [ ] 11.1 — Rédiger `guide/00-index.md` : index du guide avec liens vers chaque article
- [ ] 11.2 — Rédiger `guide/11-verdict.md` : grille d'évaluation, principes retenus, exigences pour sa propre version
- [ ] 11.3 — `wiki-lint` final sur le vault complet
- [ ] 11.4 — `wiki-export` final pour le graphe complet

**Livrable :** Guide complet indexé + synthèse des principes retenus

---

## Grille d'évaluation (remplie au fil des phases)

| Critère | Phase | Statut | Notes |
|---------|-------|--------|-------|
| Facilité de setup | 0 | ✅ | Structure claire, .env simple, setup.sh non nécessaire pour POC |
| Qualité d'extraction documents | 1 | ✅ | 13 pages bien structurées depuis 3 sources |
| Qualité d'extraction historique | 2 | ✅ | 17 pages depuis 6 projets Claude, memory files = gold |
| Formats de données supportés | 3 | ✅ | Markdown transcript + JSON ChatGPT, détection auto |
| Delta tracking | 1 | ✅ | Hash SHA-256, re-run = SKIP confirmé |
| Query experience | 4 | ⏳ | |
| Audit tools | 5 | ⏳ | |
| Provenance tracking | 1 | ✅ | ^[inferred], ^[extracted], ^[ambiguous] fonctionnels |
| Cross-linking automatique | 6 | ⏳ | |
| Tag management | 6 | ⏳ | |
| Cross-project sync | 7 | ⏳ | |
| Export / visualisation | 8 | ⏳ | |
| Archive / restore | 9 | ⏳ | |
| Extensibilité (skills) | 10 | ⏳ | |
| **Principes retenus** | 11 | ⏳ | |
