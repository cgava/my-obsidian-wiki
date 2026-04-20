# Obsidian Link Fixer

## Goal
Script CLI réutilisable pour réparer tous les liens (wikilinks + frontmatter) cassés après déplacement de fichiers dans le vault Obsidian.

## Non-goals
- Déplacer les fichiers (uniquement réparer les liens)
- Ajouter de nouveaux liens (c'est le job du cross-linker)
- Support d'autres formats que Markdown/Obsidian

## Phases

### Phase 1 — Exploration & Design
- [ ] Analyser la structure des liens dans knlg-repo (wikilinks, frontmatter refs)
- [ ] Identifier les patterns de liens à réparer (formats exacts)
- [ ] Définir l'interface CLI (args, options, output)

### Phase 2 — Implémentation
- [ ] Écrire le script (Python) avec CLI argparse
- [ ] Scanner le vault pour trouver les références aux fichiers déplacés
- [ ] Mettre à jour les wikilinks [[ancien-chemin]] → [[nouveau-chemin]]
- [ ] Mettre à jour les refs dans le frontmatter YAML
- [ ] Mode --dry-run avec rapport détaillé (type de lien, fichier source, ligne)

### Phase 3 — Test & validation
- [ ] Tester sur les 5 fichiers déplacés
- [ ] Vérifier qu'aucun lien valide n'est cassé
- [ ] Documenter l'usage (--help intégré)
