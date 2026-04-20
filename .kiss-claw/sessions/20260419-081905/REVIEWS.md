# REVIEWS — session 20260419-081905

### REV-0001

- **date**     : 2026-04-19
- **subject**  : kiss-executor task — rédaction du document d'état de l'art `docs/400-tp/260419-etat-art-agentic-cicd.md` (603 lignes, FR) sur les frameworks agentiques CI/CD open-source pour profil "mini-DSI"
- **verdict**  : approved-with-notes

**Summary**
Document substantiel, bien structuré, cohérent avec le profil et les contraintes du user (VPS mono-host, Ansible + GitLab CI déjà maîtrisés, mono-user, veut démarrer petit). Le cahier des charges est globalement respecté : 9 sections principales + 6 annexes, 6 catégories en §3 (dépasse le minimum de 5), tableau comparatif §4 avec les 7 colonnes demandées, 5 patterns + combinaisons en §5, MVP + phase 2-3 + anti-patterns en §7, watchlist §8 (7 entrées). Le ton est neutre et nuancé, aucune conclusion "winner-takes-all", l'annexe F offre une check-list actionnable. Quelques défauts cosmétiques et une référence croisée incorrecte justifient le statut "with-notes" plutôt que "approved".

**Points forts**
- Cadrage L1/L2/L3 en §2 + section 2.1 "trois questions" : grille de lecture qui sert de fil conducteur implicite dans tout le doc. Rare et bien vu.
- Respect scrupuleux du profil user : K8s écarté explicitement (§3.2 et anti-patterns), GitLab CI + Ansible posés comme socle à conserver, Claude Code + MCP traités comme déjà en place. §6 entière dédiée à l'adéquation. Aucune recommandation ne contredit le `memory` (Docker Compose + Ansible + GitLab CI, non-goals K8s/HA/multi-user).
- §6.3 Sécurité (7 principes : moindre privilège MCP, catalogue vs shell libre, dry-run, isolation runner, kill-switch, etc.) et §7.5 anti-patterns sont directement opérationnels.
- Annexe D sur kiss-claw : placement lucide (orchestration cognitive ≠ couche exécution ops), ne verse pas dans l'auto-promotion.
- Scénarios opérationnels §6.5 (déploiement / triage alerte / rotation secrets) : trois exemples bien choisis qui font dialoguer les concepts abstraits avec le quotidien mini-DSI.

**Issues**
- [minor / P1] **Référence croisée cassée §6.4 → scénario B** : ligne 300 parle du "scénario B ci-dessus" alors que Scénario B est défini ligne 326, donc **plus bas** dans le document. Corriger en "ci-dessous" ou déplacer §6.4 après §6.5.
- [minor / P1] **Numérotation §6 inconsistante** : après `### Profil` (ligne 256) et `### Forces et écueils` (ligne 274), la numérotation reprend brutalement à `### 6.3 Considérations sécurité` (ligne 286). Soit préfixer les deux premières en 6.1 / 6.2, soit retirer complètement les numéros de §6. L'executor avait signalé ce point — il est réel mais non bloquant.
- [minor / P2] **Tension MCP Ansible** : le doc présente correctement MCP Ansible comme jeune/communautaire dans §3.4, §6.2 (ligne 271), §7.2 (ligne 396) et watchlist §8.2. Mais ligne 427 ("Anti-patterns"), la recommandation "préférer un MCP Ansible avec liste blanche de playbooks" est donnée sans rappeler que ce MCP n'est pas encore mûr à adopter. Ajouter une demi-phrase ou renvoyer à la watchlist lèverait l'ambiguïté.
- [minor / P2] **Longueur au plancher** : 603 lignes pour une cible 600-1000. Acceptable, le doc n'est pas diet, mais toute suppression ultérieure passerait sous la cible. Point d'attention pour d'éventuelles révisions.
- [minor / P2] **Chiffres de stars en ordres de grandeur** : le disclaimer ligne 152 et les "Limites du document" ligne 517 suffisent, mais l'ordre de grandeur donné pour certains projets (Dify ~60k, n8n ~70k, Coolify ~40k) doit être considéré comme indicatif seulement. Rien à corriger — le doc est honnête sur ce point.
- [minor / P2] **Caveat "projets encore actifs"** : l'executor n'a pas revalidé en direct l'activité des projets. Acceptable pour un doc daté et explicitement borné au knowledge cutoff ; la section 8.1 ("comment évaluer un projet") fournit la méthode au lecteur pour revérifier.

**Pertinence / actionabilité**
- Un lecteur qui maîtrise déjà Ansible + GitLab CI + MCP peut, après lecture, démarrer : la §7.1 (MVP weekend) donne un schéma concret, la §7.2 (phase 2-3) fixe les jalons, l'annexe F fournit la check-list à cocher.
- Le doc guide sans imposer : MVP suggère "zéro agent de garde", phase 2 suggère Coolify **ou** Komodo, phase 3 évoque Dagger **si** les builds deviennent lourds. Le user garde le contrôle des arbitrages.

**Recommandation finale**
**Ready to share with user** sous réserve de corriger P1 (référence croisée §6.4 + numérotation §6). Les items P2 peuvent être traités à la prochaine itération ou lors du retour user. Aucune issue bloquante sur le fond.

**For kiss-orchestrator**
Proceed to next step — deux micro-corrections cosmétiques peuvent être appliquées par un nouveau passage executor léger (delta < 20 lignes), ou reportées selon le feedback du user.

### REV-0002

- **date**     : 2026-04-19
- **subject**  : kiss-executor rework — correction des issues REV-0001 sur `docs/400-tp/260419-etat-art-agentic-cicd.md` (603 → 757 lignes)
- **verdict**  : approved

**Summary**
Les 4 fixes demandés sont correctement appliqués, sans régression. Le document passe de 603 à 757 lignes (cible 750-850 atteinte). Les ajouts majeurs (§5.1 ASCII, §5.4 layout GitOps, §6.5 scénario D, annexe D prompts, annexe F durcissement) enrichissent le doc sans contredire le cahier des charges ni le `memory` projet. Ton neutre préservé, français correct, structure globale intacte.

**Validation des 4 fixes**
- [yes] **P1 réf croisée §6.4 → scénario B** : ligne 355 `"cf. scénario B en §6.5 ci-dessous"` pointe désormais correctement vers §6.5 (ligne 367), scénario B défini ligne 398. Fix propre.
- [yes] **P1 numérotation §6** : §6.1 Profil (l.311), §6.2 Forces/écueils (l.329), §6.3 Sécurité (l.341), §6.4 Colle (l.353), §6.5 Scénarios (l.367). Séquence 6.1→6.5 cohérente.
- [yes] **P2 MCP Ansible §7.5** : ligne 537, incise explicite `"Réserve : l'écosystème MCP Ansible est encore jeune (cf. §3.4 et watchlist §8.2) ; valider sur bac-à-sable avant prod, ou se replier sur un wrapper maison autour de ansible-runner."` Rappel d'immaturité bien présent, renvois croisés corrects.
- [yes] **P2 longueur** : 757 lignes, dans la fourchette 750-850.

**Nouvelles issues**
No issues found. Aucune régression détectée sur les autres références croisées (vérif §3.x, §5.x, §6.x, §7.x, §8.x toutes cohérentes).

**Décision sur caveats executor**
- **Scénario D §6.5 (ligne 445)** : ACCEPTÉ. L'ajout "Quand l'agent se trompe — procédure de repli" traite une dimension critique (que faire quand l'agent produit une MR défectueuse) cohérente avec l'esprit mini-DSI prudente. 10 lignes bien calibrées, pas de hors-sujet. L'élargissement de 3 à 4 scénarios est marginal et justifié.
- **Annexe D prompts executor-ops/verificator-ops (lignes 691-709)** : ACCEPTÉ. Formulation `"on pourrait définir dans kiss-claw un rôle executor-ops dont le prompt système inclurait"` est explicitement conditionnelle, les blocs de prompt sont présentés comme une esquisse ("Et un verificator-ops correspondant :"). Aucun risque que le lecteur confonde avec un état existant de kiss-claw. La limite finale ligne 713 ("kiss-claw n'apporte aucun outil prêt à l'emploi pour les ops") verrouille l'interprétation.

**Qualité des ajouts majeurs**
- **§5.1 diagramme ASCII (l.191-219)** : lisible, 7 nœuds Trigger→Report, commentaires utiles. Renforce la compréhension sans surcharger.
- **§5.4 layout GitOps (l.268-285)** : pertinent, arborescence concrète Ansible+Compose qui matérialise le pattern. Aligné avec `memory` projet (Ansible + Docker Compose).
- **§6.5 scénarios enrichis + scénario D** : chaque scénario A/B/C reçoit désormais des blocs `bash`/pseudo-code qui ancrent les concepts. Scénario D couvre proprement le cas d'échec.
- **Annexe D +40 lignes** : parallèle kiss-claw ↔ mini-DSI bien argumenté (session ↔ pipeline-id, executor/verificator ↔ build/verify, checkpoint ↔ commit). Pas d'auto-promotion.
- **Annexe F +8 étapes (l.743-752)** : backup, audit log, kill-switch, staging, budget LLM, rotation secrets, revue MCP, runbooks critiques. Aucun doublon avec §7 (MVP/phase 2-3) ou §6.3 (sécurité) — c'est du "durcissement sur la durée", niveau différent.

**Observation mineure non bloquante**
- Ligne 51 : "L'écosystème se découpe en **cinq** grandes familles" alors que §3 détaille désormais 3.1 → 3.6 (soit six). Décalage hérité du doc initial, non flagué en REV-0001. À corriger en "six" lors d'un futur passage opportuniste — pas bloquant.

**Recommandation finale**
**Ready to share with user, definitive.** Les 4 fixes sont propres, pas de régression, les caveats executor sont légitimes et acceptables. Le doc est à maturité pour livraison.

**For kiss-orchestrator**
Proceed to close — aucun rework nécessaire. La micro-inconsistance "cinq/six familles" ligne 51 peut être traitée en cleanup ultérieur si le user le demande, sinon ignorée.
