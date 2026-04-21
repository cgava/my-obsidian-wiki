# Doc Diataxis patch-system — complétion J9-J15

## Goal
Étendre la documentation Diataxis du patch-system (`scripts/docs/`) pour couvrir les évolutions livrées après J8 (J9 à J15), sans réécriture de l'existant, et en préservant la cohérence globale des 4 piliers Diataxis.

## Non-goals
- Refonte ou réécriture de la doc J8 existante (seules des corrections de cohérence peuvent être appliquées en rework si le verificator les identifie)
- Ajout de contenu qui n'est pas strictement justifié par une évolution J9-J15
- Changement de langue (reste FR)
- Changement de chemin cible (reste `scripts/docs/`)

## Contraintes
- Format Diataxis strict : chaque ajout doit être placé dans le bon pilier (tutorial / how-to / reference / explanation)
- Langue : français
- Chemin : `scripts/docs/`
- Verificator : doit analyser la doc **complète** (J8 + ajouts) pour cohérence globale et manques résiduels — éviter l'effet patchwork

## Phases

### Phase 1 — Complétion de la doc Diataxis J9-J15 (cycle unique)

- [x] Step 1 — Exécuter audit + rédaction (executor, délégation 1) : identifier ce qui est couvert par la doc J8, identifier les évolutions J9-J15 livrées dans le code et les commits, produire un tableau diff "évolution → pilier Diataxis cible → ajout nécessaire OUI/NON (justifié)", puis rédiger directement les ajouts dans les 4 fichiers `scripts/docs/*.md` (tutorial, how-to, reference, explanation) + mise à jour `scripts/docs/README.md` si pertinent
- [ ] Step 2 — Revue globale (verificator) : analyser la doc complète (existant + ajouts) pour valider (a) la couverture exhaustive de J9-J15, (b) le respect strict du format Diataxis, (c) la cohérence terminologique et navigationnelle entre les 4 piliers, (d) l'exactitude technique vs le code réel — produire un REVIEW avec statut approved / approved-with-notes / needs-rework
- [ ] Step 3 — Rework (executor, délégation 2) : traiter les remarques du verificator (y compris corrections éventuelles sur la doc J8 existante si le verificator les a identifiées comme nécessaires à la cohérence globale)
