# Reviews — session 20260421-072517

## REV-0001

- **date**     : 2026-04-21
- **subject**  : kiss-executor task — Step 1 : audit + rédaction additions Diataxis pour J9-J15 dans `scripts/docs/`
- **verdict**  : **needs-rework**

### Summary

L'executor a livré des ajouts **techniquement corrects, exhaustifs et correctement placés dans le pilier Diataxis** (reference, how-to, explanation ; tutorial intact). La couverture J9-J15 est complète. **Mais** — et c'est pour cela que je tranche `needs-rework` plutôt que `approved-with-notes` — l'utilisateur a explicitement demandé d'**éviter l'effet patchwork** et ta doc livrée présente **≥ 8 contradictions directes** entre les sections J8 conservées et les sections ajoutées. Un lecteur qui lit linéairement voit : « cette commande est non-implémentée (§1.7) » puis, 60 lignes plus bas : « voici sa spec complète (§1.8) ». Le non-goal « pas de réécriture J8 » doit céder devant la cohérence globale que le verificator était explicitement mandaté pour auditer.

### Couverture J9-J15

| Évolution | Ref | How-to | Expl. | OK ? |
|---|---|---|---|---|
| `verify` (3 checks, `--json`, `--strict`) | §1.8 | ✓ | §9.1 | ✅ |
| `refresh` (clean/patched, `--dry-run`, `--yes`, history JSONL) | §1.9 | ✓ | §9.2 | ✅ |
| `apply --interactive` / `--force` / `--auto-3way` | §1.5bis | ✓ | — | ✅ |
| `apply --all` / `--stop-on-fail` | §1.5bis | ✓ | §10.1-10.3 | ✅ |
| `rollback --all` / `--stop-on-fail` | §1.6bis | ✓ | §10.1, §10.4 | ✅ |
| Menu `y/n/s/d/3/r/q/?` (ui.py verbatim) | §1.5bis | ✓ | — | ✅ |
| Mutex `--yes` / `--interactive` | §1.5bis | ✓ | — | ✅ |
| Flock unique par run `--all` | — | ✓ (briève) | §10.2 | ✅ |
| `runtime.json` schéma + resolve + méthodes | §7 | ✓ (via recette B3) | §8 | ✅ |
| Fallback `patch(1) -p1 -N` + détection absence | §7.4 | ✓ | §8.2 | ✅ |

**Verdict couverture** : complète. Aucun trou fonctionnel détecté.

### Respect Diataxis (par pilier)

- **Tutorial** (intact) : OK. Le parcours single-record reste pédagogiquement valide et factuellement correct (le quote `rollback ... --force (jalon 14, not yet implemented)` est toujours émis verbatim par `rollback.py:118`). **Je valide la décision de non-augmentation**.
- **How-to** : nouvelles recettes bien orientées tâche (objectif → étapes → exit codes). RAS Diataxis.
- **Reference** : ajouts neutres, info-dense, tableaux exit codes ; conforme. Remarque : les suffixes `bis` (§1.5bis, §1.6bis) sont un hack structurel, mais acceptable.
- **Explanation** : §8, §9, §10 ciblent le « pourquoi » sans sombrer dans la prescription. RAS Diataxis.

### Cohérence globale (MUST FIX)

Contradictions factuelles entre J8-conservé et ajouts (8 points listés verbatim ci-dessous, tous sont des mensonges actifs pour le lecteur) :

1. **`reference.md` §1.0 ligne 36-38** — le help argparse reproduit dit :
   ```
   verify              (stub until jalon 9/10) Integrity checks.
   refresh             (not yet implemented — jalon 10)
   record              (not yet implemented — jalon 11)
   ```
   Le code (`cli.py` lignes 803-826) émet maintenant :
   ```
   verify              Integrity + drift + target coherence (design §4.1).
   refresh             Recompute baseline/patched sha256 from current state.
   record              (not yet implemented — jalon 12)
   ```
   Le bloc doit refléter le help réel. Noter aussi **J11 → J12** pour `record`.

2. **`reference.md` §1.5 lignes 185-186** : « Le mode interactif (jalon 12) et `--force` (jalon 14) ne sont pas encore implémentés » — **FAUX**. Les deux sont en §1.5bis.

3. **`reference.md` §1.5 lignes 198-199** : « Comme il n'existe pas encore de mode interactif (J12), `--yes` revient pour l'instant à refuser les états ambigus » — le « pour l'instant » est obsolète.

4. **`reference.md` §1.5 lignes 201-207** : tableau « Flags documentés dans le design mais pas encore implémentés » liste `--interactive / --force / --auto-3way` comme « Non implémenté ». **Tous implémentés** (vérifié dans `apply.py:256+`, menu `ui.py`).

5. **`reference.md` §1.7 lignes 367-381** : toute la section « Commandes à venir » est **fausse pour verify/refresh**. Seul `record` reste stub. Cette section devrait disparaître ou être réduite à `record`.

6. **`reference.md` §2.5 ligne 607** : « non consommée par les commandes J1-J8 » — incorrect depuis J14 (`runtime.json` est consommé par `apply`/`rollback` via `runtime_mod.load_runtime` appelé dans `cli.py::_cmd_apply` ligne 474).

7. **`reference.md` §4.1 lignes 658-659** : « `refresh` (stub, le lock est pris même si l'exécution échoue) » et « `record` (stub, idem) » — `refresh` n'est plus stub.

8. **`how-to.md` lignes 134-148** — la recette « Comment diagnostiquer un état partial ou dirty ? » contient :
   - « En jalon J8 actuel » (l.134) — anachronique
   - « `--interactive` ou `--force` arbitreraient — non encore implémentés (jalons 12/14) » (l.141-142) — **FAUX**
   - « puis `refresh` (J10) quand disponible » (l.143) — `refresh` EST disponible
   - « Régénérer le patch (`record`, J11) depuis l'état voulu (pas encore implémenté) » (l.222) — record est J12, pas J11
   - « Attendre les jalons 12 (mode interactif…) et 14 (`--force` + fallback `patch(1)` + `--auto-3way`) » (l.223-224) — **tout est livré**

9. **`how-to.md` ligne 218** : « Si le conflit est sémantique : pas d'auto-résolution en J8 » — anachronique.

10. **`explanation.md` §2.3 lignes 105-108** : « État actuel (J8) : le mode interactif n'est pas encore implémenté. En attendant, les états `dirty` / `partial` sont refusés avec un message explicite `arbitration required`, et l'opérateur doit corriger manuellement ou attendre J12. » — **FAUX** (J12 livré).

11. **`explanation.md` §4 lignes 228-232** : « État J1-J8 : `series.json` est implémenté et consommé. `runtime.json` est prévu pour les jalons ultérieurs… Les commandes opérationnelles J8 utilisent des défauts en dur » — **FAUX** depuis J14.

12. **`explanation.md` numérotation §6 → §8 → §9 → §10 → §11** : **§7 n'existe plus**. Le renumérotage du « Lectures complémentaires » J8 en §11 crée une lacune logique (saut §6→§8). Un lecteur cherche « où est §7 ». La renumérotation doit être cohérente : soit §7 "Lectures" déplacé en queue en §11 ET §8/9/10 deviennent §7/8/9 ; soit la série est §6, §7, §8, §9, §10 monotone sans gap.

### Exactitude technique — spot-checks sur le code réel

Points vérifiés OK :
- Menu 8 lettres + header « Patch NNNN target <path> is <state>. » = `ui.py:41-64` verbatim ✅
- `runtime.json` schéma, méthodes `git-apply`/`patch`, erreurs `RuntimeError_` = `runtime.py:27-130` ✅
- Exit codes `verify` = `verify.py:247-264` ✅
- Règle refresh clean→baseline / patched→patched / autre→refus = `refresh.py:143-154` ✅
- Messages canoniques « ambiguous state » + « --yes mode forbids » = `ui.py:79-88` + `apply.py:490` ✅
- Message mutex « --yes and --interactive are mutually exclusive » = `apply.py:326` ✅
- `apply --all`/`rollback --all` ordre, flock unique, résumé = `cli.py:497-628` ✅

**Inexactitudes détectées (SHOULD FIX)** :

13. **`reference.md` §1.5bis tableau menu** + **`how-to.md` ligne 432** : descriptions de `s` et `d` (« affiche le diff 3-points (pristine / local / patched) » et « affiche le diff patch -> local ») reproduisent le **texte du menu**, mais pas le **comportement réel**. Le code `apply.py:223-230` affiche juste le contenu du `.patch` préfixé par « (s) 3-point diff not yet implemented — showing patch file: » ou « (d) diff patch -> local ; showing patch content: ». Le menu verbatim est OK en tant que transcription d'UI, mais les tableaux descriptifs doivent noter ce gap (« — actuellement fallback vers contenu du `.patch` »). C'est la seule case d'`apply.py` encore « not yet implemented » que votre doc cache.

14. **`reference.md` §1.5bis ligne 249** : « Exit code : `0` n'est PAS émis — `apply` renvoie un résultat `success=False` (exit `1`). » — formulation tordue. Direct : « Exit code : `1` ». Code OK (`apply.py:326` retourne `_result(False, ...)` → exit 1).

15. **`reference.md` §4.2** : cite design verbatim « `verify --read-only` … l'utilisateur peut consulter l'etat pendant qu'un apply tourne. » — mais le parser argparse de `verify` n'a **pas** de flag `--read-only`. C'est une divergence design↔code préexistante (déjà en J8) que la nouvelle §1.8 reproduit implicitement. À mentionner au moins en note.

### Verdict sur tutorial.md

**Accord avec la non-augmentation** (décision de l'executor), arguments :
- Tutorial J8 reste factuellement correct (le quote `--force ... not yet implemented` reflète toujours l'output actuel de `rollback.py`).
- Le parcours pédagogique est cohérent : un apprenant découvre le cycle `list → status → describe → diff → apply → idempotence → rollback → garde-fou` qui suffit pour comprendre la mécanique.
- `apply --all` et `verify`/`refresh` sont **task-oriented** (régénération après pull) ou **diagnostic** — Diataxis les place à juste titre dans how-to + reference.

**Nice-to-have** (pas blocking) : étape optionnelle 10 dans le tutorial — « Étape 10 — Régénérer l'état patched après un pull : `apply --all` ». Cela clôt l'arc pédagogique sur le cas d'usage canonique ADR-0001. À trancher avec l'utilisateur.

### Issues (classées par sévérité)

**MUST FIX** (bloquent le verdict `approved`) :
- [blocking] Contradictions factuelles ≥ 8 points (cf. Cohérence globale 1-11). Chaque section J8 qui affirme « non implémenté » pour verify/refresh/apply-flags doit être rectifiée (soit supprimée, soit annotée « Voir §X.Ybis pour la spec livrée J12-J14 »).
- [blocking] Numérotation explanation.md : §6→§8 saute §7. À corriger en renumérotant §8/9/10 → §7/8/9 et §11 → §10 (monotone), ou autre schéma cohérent.
- [blocking] `reference.md §1.0` help argparse : mettre à jour le bloc verbatim pour refléter les help strings actuels (`cli.py:803-826`) et `jalon 11` → `jalon 12` pour `record`.

**SHOULD FIX** (cohérence terminologique / exactitude) :
- [minor] `reference.md §1.5bis` menu `s`/`d` : ajouter note « fallback actuel : affichage du contenu du `.patch` préfixé d'un message — vrai 3-point diff prévu post-P3 ».
- [minor] `reference.md §1.5bis ligne 249` : reformuler en direct « Exit code : `1` ».
- [minor] `reference.md §4.2` : noter que `--read-only` cité verbatim depuis design n'est pas (encore ?) implémenté dans le parser argparse de `verify`.
- [minor] Consolidation optionnelle : fusionner §1.5bis dans §1.5, §1.6bis dans §1.6 au lieu du suffixe `bis` — structure Diataxis plus propre (mais c'est de la refonte, à arbitrer par l'orchestrator).

**NICE TO HAVE** :
- [nice] Tutorial : étape 10 `apply --all` (optionnel, à trancher utilisateur).
- [nice] `reference.md §2.5` + `explanation.md §4` : remplacer les mentions « État J1-J8 » / « non consommée par J1-J8 » par un libellé générique avec date, moins vulnérable à l'obsolescence.

### For kiss-orchestrator

**rework this step** — déléguer un Step 3 (rework) à kiss-executor avec ces trois actions prioritaires :

1. Corriger les 11 points de la section « Cohérence globale ». Traiter le non-goal « pas de réécriture J8 » comme levé **uniquement** pour ces corrections factuelles (pas pour refonte de style). Préférer annotations/suppressions ciblées sur la renumérotation lourde.
2. Corriger la numérotation de `explanation.md` pour monotonie §6 → §7 → §8 → §9 → §10.
3. Ajouter les 3 SHOULD FIX points (menu s/d fallback, exit code §1.5bis, note §4.2 --read-only).

Le tutorial peut rester intact. Les NICE-TO-HAVE sont laissés à la discrétion executor/utilisateur.
