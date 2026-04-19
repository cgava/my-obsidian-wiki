# État de l'art — Frameworks agentiques pour CI/CD multi-apps
> 2026-04-19 — Mini-DSI personnelle

## 1. Contexte et objectifs

L'utilisateur opère un VPS sur lequel vivent plusieurs applications personnelles hétérogènes (Obsidian wiki, et d'autres à venir). Il maîtrise **Ansible** et **GitLab CI** en contexte professionnel, et utilise au quotidien **Claude Code**, des serveurs **MCP** (Model Context Protocol) et le framework **kiss-claw** pour sa productivité.

L'objectif de ce document n'est **pas** de désigner un gagnant, mais de cartographier l'écosystème 2025-2026 des outils où des agents LLM interviennent dans le cycle CI/CD (build, déploiement, monitoring), afin que la "mini-DSI" d'une à deux personnes puisse démarrer petit sur des bases saines, sans se fermer de portes.

Hypothèse de lecture : le lecteur sait déjà ce qu'est un pipeline CI/CD, un container, un playbook Ansible et un serveur MCP. On évite les rappels superflus.

## 2. Cadrage : qu'est-ce qu'un "framework agentique CI/CD" ?

On désigne ici par **framework agentique CI/CD** tout système où un ou plusieurs *agents* — entités alimentées par un LLM, dotées d'outils (`tools`) et capables de raisonnement multi-étapes — interviennent activement dans tout ou partie du cycle suivant :

1. **Build** : compilation, tests unitaires/intégration, construction d'images container, signature d'artefacts.
2. **Deploy** : promotion d'artefacts vers des environnements, application de changements d'infra, rollbacks.
3. **Operate / Monitor** : observabilité, détection d'anomalies, triage d'incidents, remédiation automatique ou semi-automatique.

Le périmètre exclut délibérément :

- Les **assistants de code pur** (Copilot, Cursor, Claude Code en mode édition) qui ne pilotent pas la chaîne CI/CD.
- Les **plateformes CI/CD classiques sans couche agent** (Jenkins, Drone, Concourse, ArgoCD "nu") — sauf si elles exposent des hooks agent-natifs.
- Les **chatbots ops** purement déclaratifs (`ChatOps` façon Hubot) sans raisonnement LLM.

On retient trois niveaux de "agenticité" :

| Niveau | Description | Exemple typique |
|--------|-------------|-----------------|
| L1 — Assisté | Le LLM suggère, l'humain exécute | Copilot dans un runner |
| L2 — Semi-autonome | L'agent exécute des outils prédéfinis, validation humaine aux étapes critiques | K8sGPT en mode remédiation, un workflow LangGraph avec `human-in-the-loop` |
| L3 — Autonome | L'agent décide et agit seul, supervision a posteriori | Agents SRE qui clôturent un incident de bout en bout |

Pour un usage mini-DSI, **L2 est la cible réaliste** : l'autonomie L3 multiplie les risques (consommation VPS, actions destructrices, dérive), et L1 apporte peu au-delà d'un assistant de code déjà disponible.

### 2.1 Trois questions pour qualifier un outil

Plutôt qu'un check-list exhaustif, trois questions suffisent pour situer un projet dans ce panorama :

1. **L'agent décide-t-il de la structure d'exécution, ou la prend-il en entrée ?**
   Un agent qui génère dynamiquement le graphe d'exécution est plus puissant mais plus dur à rendre reproductible. Un agent qui choisit dans un DAG préexistant est plus facile à auditer.
2. **Les outils sont-ils exposés via un protocole standard (MCP, OpenAPI) ou via du code embarqué ?**
   La standardisation favorise la portabilité entre frameworks et facilite le remplacement d'un composant sans tout reconstruire.
3. **L'agent a-t-il un mode *plan puis exécute* ou un mode *agir tout de suite* ?**
   Le premier est adapté aux opérations en prod, le second aux tâches répétitives à faible risque.

Ces questions sont reprises implicitement dans les analyses ci-dessous.

## 3. Catégorisation de l'écosystème

L'écosystème se découpe en cinq grandes familles qui peuvent se combiner. Un projet peut appartenir à plusieurs catégories.

### 3.1 Frameworks d'agents généralistes

Briques de bas niveau pour composer ses propres agents. Non spécifiques au CI/CD mais utilisables pour construire des orchestrations ops sur mesure.

- **LangGraph** (LangChain, Python + TypeScript) — graphe d'états explicite, supports du `human-in-the-loop`, checkpoints, rejeux. Devenu le choix "entreprise" pour des workflows agentiques sérieux. Courbe d'apprentissage non triviale mais la granularité récompense.
- **CrewAI** (Python) — métaphore "équipe d'agents avec rôles". Très lisible, démarre vite ; limites en termes de reproductibilité et d'observabilité fine quand les workflows se complexifient.
- **AutoGen / AG2** (Microsoft, Python) — conversation multi-agents, spécialisé dans les échanges entre agents. Fork `AG2` actif après le départ des auteurs originaux. Convient pour des patterns "debat entre agents", moins pour un pipeline linéaire CI/CD.
- **Letta** (anciennement MemGPT) — agents à mémoire persistante. Pertinent si l'on veut un "SRE de garde" qui accumule de la connaissance sur le VPS au fil du temps.
- **Dify** (self-hostable) — studio visuel et backend d'agents, orienté produit chatbot mais extensible aux workflows internes. Bonne couverture d'intégrations.
- **n8n (avec nœuds AI)** — automation low-code historique qui a intégré des nœuds agent/LLM. Fort pour les glue-tasks CI/CD (webhooks, cron, déclencheurs GitLab/GitHub) avec un composant LLM localisé.
- **Flowise** — équivalent visuel côté LangChain, plus léger que Dify mais moins d'intégrations.
- **Temporal + workers LLM** — non "agentique" par conception mais de plus en plus utilisé comme substrat pour des workflows agents durables ; à mentionner car il résout le problème des longues exécutions et des reprises.

Point d'attention : ces frameworks **ne savent rien du CI/CD** par défaut. L'utilisateur doit y injecter ses outils (Docker, kubectl, ansible-runner, clients GitLab/GitHub). C'est le prix de la flexibilité.

Exemples concrets d'usage pour un parc mini-DSI :

- **LangGraph** : un petit graphe à 4 nœuds — *gather context → propose change → human approval → apply* — déclenché une fois par semaine pour les mises à jour d'images Docker (`renovate`-like avec raisonnement).
- **CrewAI** : une "équipe" à 3 rôles — *release-writer* (résume les commits), *security-scanner* (lit les CVE récentes), *changelog-editor* (assemble le tout) — pour générer les release notes à chaque tag.
- **n8n** : le glue naturel entre un webhook GitLab push → vérif du lint → notification Discord → ouverture d'une issue si échec. Très peu de code, beaucoup de fiabilité.
- **Dify** : un assistant conversationnel interne "demande-moi ce que fait le VPS" branché sur les MCP de lecture (Docker, Loki, Prometheus). Utile pour l'astreinte.

La règle d'or : un framework d'agents est utile **quand on a une tâche répétitive qui mérite du raisonnement**. Pour une tâche déterministe, un script shell ou un job CI suffit, et coûte moins cher.

### 3.2 Agents AI-natifs pour DevOps / SRE

Projets conçus d'emblée pour l'opération d'infra. Ils embarquent des outils métier, des runbooks et souvent un modèle mental du cluster ou du host.

- **K8sGPT** (CNCF Sandbox) — analyse d'état Kubernetes, diagnostique les ressources cassées, propose un plan de remédiation. L'un des projets les plus matures de la catégorie, intégré à OpenAI, Anthropic, Ollama locaux.
- **HolmesGPT** (Robusta.dev) — enquêteur d'incidents qui corrèle alertes Prometheus/Grafana avec logs/événements et rédige un post-mortem. Plus orienté "investigation" que remédiation.
- **Robusta** (le produit) — plateforme qui route des alertes enrichies par LLM ; l'agentique y est un composant parmi d'autres.
- **Kubiya** — plateforme commerciale d'agents DevOps, catalogue d'actions préconstruites. Intéressant à connaître comme référence de design, moins pertinent en self-hosted pour une mini-DSI.
- **Dagger AI / Container Use** (Dagger.io) — Dagger étant un moteur CI/CD programmable (cf. 3.3), l'équipe a ajouté un mode agent où un LLM pilote le graphe de build dans un conteneur reproductible. Approche prometteuse : on reste dans un DAG déterministe, le LLM n'invente pas la chaîne de commandes mais la compose.
- **OpsAgent / SRE-GPT / divers forks** — écosystème bouillonnant, beaucoup d'expérimentations GitHub à courte durée de vie. À surveiller mais pas à adopter avant stabilisation.
- **Bolt / sweep.dev** pour la partie "agent qui ouvre des PR de fix" — côté code plus qu'ops, mais la frontière s'estompe.

Observation générale : la majorité de ces outils sont **Kubernetes-centriques**. Sur un VPS mono-host avec Docker Compose, une bonne partie du catalogue est sur-dimensionnée ou inapplicable.

Ce qui reste utile même sans K8s :

- **La méthode** (K8sGPT / HolmesGPT sont des *manières de faire* transposables) : partir d'un état déclaré, comparer à l'observé, enrichir par du contexte LLM, produire un diagnostic structuré. Rien n'empêche d'appliquer ce pattern à un `docker compose` en se passant des outils sur étagère.
- **Dagger Container Use** : reste pertinent en mono-host car Dagger tourne très bien sans cluster.
- **Robusta** (dans sa partie non-K8s) : l'idée d'enrichir des alertes par un LLM avant notification est reproductible avec quelques lignes de code au-dessus d'Alertmanager ou d'Uptime Kuma.

À revisiter si migration K8s/K3s : K8sGPT et HolmesGPT deviennent alors très pertinents.

### 3.3 Moteurs CI/CD programmables (compatibles agents)

Ces moteurs ne sont pas agentiques en eux-mêmes mais exposent une API ou un SDK qui permet à un agent d'y injecter des pipelines dynamiques. Ils forment un *substrat déterministe* sous une couche agent.

- **Dagger** — pipelines codés en Go/Python/TypeScript, exécutés dans des conteneurs, graphe mis en cache par contenu. Parfaitement adapté à un agent qui compose un pipeline à la volée puis délègue l'exécution.
- **Earthly** — `Earthfile` façon `Dockerfile`, très lisible, reproductible. Moins programmable qu'un Dagger mais plus simple à comprendre.
- **Tekton** — CRDs Kubernetes pour pipelines. Puissant mais exige un cluster et une tolérance élevée à la verbosité YAML.
- **GitLab CI + `include:` dynamiques** — l'outil déjà maîtrisé par l'utilisateur peut être piloté par un agent qui génère un `.gitlab-ci.yml` contextuel via MR. Souvent sous-estimé.
- **Woodpecker CI / Drone** — successeurs légers de Jenkins, auto-hébergeables sur un petit VPS, API propre.
- **act** (GitHub Actions local) — utile pour tester des pipelines GHA hors ligne, indirectement utilisable par un agent pour valider ses propositions.

### 3.4 Serveurs MCP pour l'infra

MCP est en train de devenir le **bus d'outils standard** entre LLM et systèmes. Un agent qui veut toucher à l'infra se branche à un ou plusieurs serveurs MCP plutôt que d'écrire des intégrations propriétaires.

- **MCP Docker / Docker MCP Toolkit** (officiel Docker) — contrôle de conteneurs locaux, `compose up`, logs, inspect. Conçu pour cadre local et sécurisé.
- **MCP Kubernetes** (plusieurs implémentations communautaires) — `kubectl` en outils exposés. Qualité variable, vérifier le maintien.
- **MCP GitHub** (officiel GitHub, en remplacement du serveur communautaire d'origine) — gestion d'issues, PR, actions, releases.
- **MCP GitLab** (communauté) — équivalent GitLab, moins complet que son cousin GitHub mais fonctionnel pour les opérations courantes.
- **MCP Ansible** (communauté, plusieurs candidats) — encore jeune, souvent un wrapper autour de `ansible-runner`. Peut exposer l'inventaire, lancer des playbooks, lire des résultats.
- **MCP SSH / Shell** — à manipuler avec la plus grande prudence : permet à un agent d'exécuter des commandes distantes. Bon pour du diagnostic read-only, risqué pour des changements.
- **MCP Terraform / Pulumi** — pour ceux qui font de l'IaC ; lit des states, propose des plans.
- **MCP Prometheus / Grafana / Loki** — lecture d'observabilité, de plus en plus populaire pour le triage d'incidents.

Point clé : MCP permet de **découpler agent et outillage**. On peut changer de framework agent sans réécrire les intégrations.

### 3.5 Plateformes self-hosted "agent-friendly"

Plateformes de type PaaS simplifié, pensées pour auto-héberger ses apps. Elles ne sont pas "agentiques" mais exposent des APIs que des agents peuvent piloter ; plusieurs commencent à intégrer des assistants LLM natifs.

- **Coolify** — PaaS open-source auto-hébergé, déploie des apps depuis Git, supporte Docker/Compose/Kubernetes. Très actif, API REST, ajout récent d'intégrations IA pour la génération de configurations.
- **Dokku** — ancien et stable, "mini Heroku" basé sur buildpacks + Docker. CLI riche, scriptable.
- **CapRover** — concurrent de Dokku, UI plus soignée, API documentée.
- **Komodo** (anciennement Monitor) — orchestrateur de serveurs Docker avec UI, pipelines de build, alerting. Peu connu, mais très pertinent pour un VPS multi-apps.
- **Portainer** — UI de gestion Docker/Kubernetes, API stable ; un agent peut y déclencher des stacks.
- **Dockge** — gestionnaire Compose léger, complémentaire d'un setup Portainer-like.

Ces plateformes offrent un **point d'entrée API unique** que l'agent peut piloter sans connaître les détails bas-niveau (volumes, réseaux, health checks).

### 3.6 Offres intégrées aux forges (GitLab Duo, GitHub Copilot Workspace / Actions Agents)

Parallèlement à l'écosystème open-source, les forges de code ajoutent leurs propres couches agentiques. Statut en avril 2026 :

- **GitLab Duo Agents** — agents intégrés à la plateforme, couvrent la génération de code, la revue, la suggestion de pipelines. Verrouillage de plateforme et coût tiers. Intéressant si l'on est déjà sur GitLab Ultimate ; moins en self-hosted CE classique.
- **GitHub Copilot Workspace / Actions Agents** — Copilot s'étend aux workflows GitHub Actions. Intégration fluide mais payant par siège. Bien pour les équipes 100 % GitHub.
- **Gitea / Forgejo + extensions communautaires** — alternative self-hosted, intégrations agent plus frustes mais entièrement libres. À surveiller.

Pour un profil mini-DSI qui héberge son propre GitLab (ou paie un compte modeste), ces offres restent accessoires : Claude Code + MCP GitLab couvre l'essentiel sans dépendance supplémentaire. À (ré-)évaluer si les tarifs deviennent agressifs ou si l'intégration native atteint un niveau que les MCP ne pourront pas reproduire.

## 4. Tableau comparatif

Les catégories sont : **FA** = Framework d'agents, **OPS** = Agent DevOps/SRE, **CI** = Moteur CI/CD, **MCP** = Serveur MCP, **PF** = Plateforme self-hosted.

Les stars sont données en ordre de grandeur approximatif (ne pas considérer comme source fiable, la donnée évolue vite).

| Projet | Cat. | Stars (ordre) | Maturité | Start-small | Agent-ready | Commentaire |
|--------|------|---------------|----------|-------------|-------------|-------------|
| LangGraph | FA | ~10k | Mûr | Moyen | Oui, par design | Le plus solide pour orchestrer un workflow agent ops complexe |
| CrewAI | FA | ~25k | Mûr | Facile | Oui | Démarre vite, questionnable à l'échelle |
| AutoGen / AG2 | FA | ~30k | Mûr mais en transition | Moyen | Oui | Mieux pour "conversations d'agents" que pour des pipelines |
| Dify | FA | ~60k | Mûr | Facile (Docker) | Oui | Studio complet, bon pour un assistant DevOps conversationnel |
| n8n | FA | ~70k | Très mûr | Facile | Oui (nodes AI) | Glue idéale pour CI/CD multi-apps déclencheurs |
| K8sGPT | OPS | ~7k | Mûr (CNCF) | K8s requis | Oui | Standard de facto du diag K8s |
| HolmesGPT | OPS | ~1-3k | Actif | K8s recommandé | Oui | Complément naturel de K8sGPT pour l'enquête |
| Dagger | CI | ~10k | Mûr | Moyen | Oui (Container Use) | Pipeline en code, très testable |
| Earthly | CI | ~10k | Mûr | Facile | Partiellement | Bon entre-deux Docker/Make |
| Woodpecker CI | CI | ~5k | Mûr | Facile | Oui (via API) | CI auto-hébergée minimaliste |
| MCP Docker | MCP | variable | Jeune mais officiel | Facile | Natif | Indispensable pour agents locaux |
| MCP GitLab | MCP | faible | Jeune | Facile | Natif | Qualité variable selon fork |
| Coolify | PF | ~40k | Mûr | Très facile | API + LLM intégré | Excellent "cœur" pour un VPS multi-apps |
| Komodo | PF | ~3-5k | En croissance | Facile | API | Spécifiquement pensé multi-serveurs Docker |
| Dokku | PF | ~30k | Très mûr | Très facile | Via API/CLI | Solide et éprouvé, moins "moderne" |

**Lecture du tableau** :

- *Start-small* : effort pour un premier déploiement fonctionnel sur un VPS modeste.
- *Agent-ready* : facilité avec laquelle un agent LLM peut piloter le système (API propre, docs claires, serveur MCP existant).

## 5. Patterns architecturaux observés

Cinq patterns reviennent dans les déploiements agentiques CI/CD. Ils ne sont pas exclusifs ; on les combine.

### 5.1 Orchestrateur central

Un agent unique (ou un framework comme LangGraph) tient le graphe d'exécution. Les autres composants sont des outils qu'il appelle. C'est le pattern classique *ReAct* ou *Plan-and-Execute*.

- **Forces** : simple à raisonner, un seul point de logs, un seul contexte.
- **Limites** : le contexte LLM sature vite quand les apps se multiplient ; point de défaillance unique.
- **Exemple** : un workflow LangGraph qui orchestre build → test → deploy → smoke test pour une app donnée.

Flux simplifié d'un orchestrateur central pour un cycle de déploiement :

```
  ┌────────────┐
  │  Trigger   │  (MR merged, cron, commande humaine)
  └─────┬──────┘
        ▼
  ┌────────────┐       ┌──────────────┐
  │  Planner   │──────▶│ Tools catalog│  (MCP Docker, MCP GitLab…)
  └─────┬──────┘       └──────────────┘
        ▼
  ┌────────────┐
  │  Build     │  (dagger / docker build)
  └─────┬──────┘
        ▼
  ┌────────────┐
  │  Test      │  (pytest, smoke, lint playbooks)
  └─────┬──────┘
        ▼
  ┌────────────┐
  │  Deploy    │  (ansible-playbook, compose up)
  └─────┬──────┘
        ▼
  ┌────────────┐
  │  Verify    │  (HTTP healthcheck, prometheus scrape)
  └─────┬──────┘
        ▼ (fail → retry ou issue)
  ┌────────────┐
  │  Report    │  (commentaire MR, message Discord)
  └────────────┘
```

Tout le contexte circule dans un même graphe : un seul prompt système, un historique linéaire de messages outils, un checkpoint au passage d'un nœud. Pratique pour déboguer, lourd à maintenir dès que l'on gère plus de 3 ou 4 apps aux profils distincts.

### 5.2 Fleet d'agents spécialisés

Plusieurs agents aux rôles distincts (*builder*, *deployer*, *observer*, *fixer*), coordonnés par un routeur.

- **Forces** : contextes séparés, évolutivité, possibilité de modèles différents par rôle (haiku pour un ping, opus pour un diag).
- **Limites** : synchronisation, dette de communication, observabilité plus complexe.
- **Cadre naturel** : CrewAI, AutoGen, ou une orchestration maison (type kiss-claw).

### 5.3 MCP-bus (agents + outils découplés)

Les agents sont indifférents à l'outillage sous-jacent : ils consomment des capacités via MCP. Pattern en forte croissance depuis la standardisation de MCP en 2024-2025.

- **Forces** : découplage maximal, réutilisation d'outils entre agents et entre frameworks, sécurité fine par serveur MCP.
- **Limites** : latence légèrement accrue, dépendance à la qualité des serveurs MCP choisis.
- **Pertinence mini-DSI** : élevée — permet de rester "agnostique framework" et de changer d'agent principal plus tard.

### 5.4 GitOps + agents (agents en "proposeurs")

Les agents ne déploient pas directement ; ils ouvrent des MR/PR sur un dépôt de configuration. L'application se fait par un opérateur GitOps (ArgoCD, Flux) ou par la CI classique.

- **Forces** : traçabilité totale (tout passe par Git), réversibilité naturelle, l'humain reste en boucle au niveau du `merge`.
- **Limites** : boucle lente ; inadapté à la remédiation d'incident en temps réel.
- **Pertinence mini-DSI** : très élevée — cohérent avec la culture GitLab CI existante.

Séquence type :

```
Agent          Dépôt infra       CI             Opérateur GitOps / VPS
  │               │              │                       │
  │ open MR ──────▶              │                       │
  │               │  trigger ────▶                       │
  │               │              │  dry-run, lint        │
  │               │  ◀── report  │                       │
  │ humain review │              │                       │
  │               │◀── merge ────│                       │
  │               │              │  apply ───────────────▶
  │               │              │                       │ (ansible / compose up)
  │               │              │ ◀── smoke test result │
  │  post-check ◀─┼──────────────┼───────────────────────│
```

L'agent peut être réinvoqué en fin de séquence pour valider le succès et, le cas échéant, ouvrir une issue si le smoke test échoue.

Layout de dépôt qui facilite ce pattern pour une mini-DSI :

```
infra/
├── inventory.yml            # hôtes et groupes Ansible
├── group_vars/              # variables partagées
├── host_vars/               # variables par hôte
├── playbooks/
│   ├── site.yml             # playbook principal (bootstrap + apps)
│   └── roles/               # rôles Ansible réutilisables
├── docker-compose/
│   ├── app-a/
│   │   ├── compose.yml
│   │   └── .env.sample
│   └── app-b/ ...
├── AGENTS.md                # intentions, conventions MR, zones sensibles
└── .gitlab-ci.yml           # lint + dry-run + manual apply
```

Un agent qui respecte ce layout peut en déduire seul où modifier pour une tâche donnée : bump de version → `docker-compose/<app>/compose.yml`, nouveau secret → `group_vars/all/vault.yml`, nouvel hôte → `inventory.yml`. La prévisibilité du chemin réduit les erreurs d'édition à des endroits imprévus.

### 5.5 Event-driven (agents réactifs)

Les agents sont déclenchés par des événements : webhook GitHub/GitLab, alerte Prometheus, push sur un registry, cron. Ils exécutent un micro-workflow puis se taisent.

- **Forces** : parcimonie (pas d'agent "de garde" qui consomme en continu), coût maîtrisé, tolérance aux pannes simple.
- **Limites** : cold start, moins adapté aux tâches nécessitant un contexte long.
- **Substrat typique** : n8n, GitHub/GitLab Actions, Temporal.

### 5.6 Combinaisons usuelles

Dans la pratique, les patterns s'empilent. Trois combinaisons récurrentes :

- **GitOps + MCP-bus** : l'agent propose des MR sur un dépôt de config via un MCP GitLab/GitHub, l'opérateur GitOps applique. Pattern le plus sûr pour de la prod.
- **Event-driven + Orchestrateur central** : un événement (webhook, alerte) réveille un workflow LangGraph court, qui orchestre 3-5 étapes puis se termine. Coût borné, observabilité claire.
- **Fleet d'agents + MCP-bus** : les rôles se partagent un catalogue d'outils MCP. La spécialisation se fait par le prompt système, pas par le code. Facile à itérer tant qu'on ne tombe pas dans le piège "chaque agent son propre petit LLM mal configuré".

Les combinaisons à éviter :

- **L3 (autonome) + absence de GitOps** : aucune traçabilité, rollback à la main.
- **Orchestrateur central unique pour N apps différentes** : le contexte LLM sature, les erreurs se propagent entre apps.
- **Fleet d'agents sans MCP-bus** : les intégrations se dupliquent dans chaque agent, la dette technique explose.

## 6. Analyse : adéquation au besoin du user

### 6.1 Profil : VPS mono-host, 1 à 3 apps hétérogènes, 1 opérateur (éventuellement 2)

| Pattern | Fit pour ce profil | Raison |
|---------|--------------------|--------|
| Orchestrateur central | **Élevé** au démarrage | Un seul opérateur humain, simplicité d'abord |
| Fleet d'agents | **Moyen** | Overkill pour 2-3 apps ; pertinent si le nombre grimpe |
| MCP-bus | **Élevé** | L'utilisateur utilise déjà MCP avec Claude Code — terrain familier |
| GitOps + agents | **Très élevé** | Aligné sur les pratiques existantes (GitLab CI), faible risque |
| Event-driven | **Élevé** | Pas de "bot de garde" qui consomme 24/7, pas besoin de cluster |

Sur les catégories de projets :

- **Frameworks d'agents généralistes** : utiles à connaître mais *pas* indispensables tant que Claude Code + MCP couvrent les besoins interactifs. En écrire un petit workflow LangGraph ou CrewAI pour des tâches récurrentes (release notes, bumps de version, rotation de secrets) est un bon premier pas.
- **Agents DevOps K8s-centrés** (K8sGPT, HolmesGPT) : **hors périmètre** tant que le setup reste Docker Compose. À rouvrir si/quand le VPS migre vers K3s/Talos ou équivalent.
- **Moteurs CI/CD programmables** : Dagger est l'option la plus intéressante à moyen terme, mais **GitLab CI déjà maîtrisé** reste le meilleur choix tant qu'il suffit. Migrer pour migrer est un anti-pattern.
- **Serveurs MCP** : à adopter au fur et à mesure des besoins — MCP Docker et MCP GitLab en priorité, MCP Ansible dès qu'il se stabilise.
- **Plateformes self-hosted** : **Coolify** apparaît comme le meilleur compromis moderne ; **Dokku** pour qui préfère la stabilité et le CLI ; **Komodo** à considérer si l'on veut piloter plusieurs hôtes Docker sans passer à K8s.

### 6.2 Forces et écueils d'un setup Ansible + GitLab CI augmenté par des agents

**Ce qui marche bien :**

- Ansible reste une excellente couche "dernière commande exécutée sur la machine". Un agent peut générer ou modifier des playbooks via MR, mais l'exécution reste ansible-playbook classique.
- GitLab CI, avec des pipelines dynamiques (`include:`, `trigger:`), est parfaitement pilotable par un agent via l'API.

**Ce qui coince :**

- Ansible **n'est pas réactif** : pour de l'auto-remédiation temps-réel, un agent + Ansible n'est pas le bon couple. Préférer un superviseur léger (Komodo, scripts Docker) avec escalade vers un playbook si la situation persiste.
- Le mélange Ansible + Docker Compose + GitLab CI est **verbeux** : un agent qui veut "faire quelque chose" doit choisir la bonne couche. Un bon document d'intentions (un `AGENTS.md` par repo ?) est précieux.

### 6.3 Considérations sécurité

Donner à un LLM — dont les sorties restent probabilistes — un accès à un environnement de production exige des gardes. Quelques principes opérationnels :

- **Moindre privilège par MCP.** Un serveur MCP n'expose que les outils strictement nécessaires. Un agent de déploiement n'a pas à pouvoir lire les secrets applicatifs s'il peut les injecter via variables d'environnement préconfigurées.
- **Catalogue d'actions plutôt que shell libre.** Un MCP qui expose `deploy(app, version)` est plus sûr qu'un MCP qui expose `run_shell(cmd)`. Cela vaut quelques heures d'écriture d'emballages.
- **Dry-run systématique.** Toute commande mutante doit être capable de s'exécuter en mode `--check` / `--diff` (Ansible), `compose config` (Docker), `terraform plan`. L'agent présente le diff, l'humain approuve.
- **Isolation du runner.** L'agent tourne dans un conteneur ou une VM dédiée, sans accès latéral aux autres apps. Les secrets sont montés au dernier moment, via un vault ou des variables CI scoped.
- **Journalisation agent-aware.** Chaque action prise par un agent est loggée avec : prompt, outils appelés, arguments, résultat, identifiant d'agent. Utile pour l'audit et pour nourrir une future boucle d'amélioration.
- **Kill-switch humain visible.** Un moyen trivial (un flag dans un fichier, une variable d'env, un endpoint HTTP) de figer tous les agents en cours. Indispensable en cas de boucle pathologique.
- **Revue pré-prod obligatoire.** Aucun agent n'écrit directement dans la branche de prod ; les MR de bot sont assorties d'un label `ai-generated` et revues comme n'importe quelle contribution externe.

### 6.4 Choix de la "colle" entre l'agent et l'infra

Pour un workflow event-driven (cf. scénario B en §6.5 ci-dessous), plusieurs candidats sont envisageables. Ils ne sont pas équivalents :

| Option | Convient pour | Ne convient pas pour |
|--------|---------------|----------------------|
| **Job GitLab CI déclenché par webhook** | Workflow court (< 1h), idempotent, qui tient dans un pipeline | Tâches longues ou nécessitant une mémoire inter-runs |
| **n8n self-hosted** | Glue multi-intégrations (Slack, webhook, LLM, email), visuel | Logique complexe / versionnée en code |
| **Script Python + cron/systemd timer** | Tâche simple, maintenue par 1 personne | Workflows à étapes multiples avec reprises |
| **Temporal (self-hosted)** | Workflows longs, durables, avec retries et visibilité fine | Petits parcs — overhead important à faire tourner |
| **Workflow LangGraph dans un conteneur ephemère** | Logique agentique sérieuse, versionnée | Actions déclaratives simples (trop de machinerie) |

Règle simple : **commencer par GitLab CI ou un script Python**, migrer vers n8n si le nombre d'intégrations explose, vers LangGraph si la logique LLM devient cœur de métier, vers Temporal seulement si un workflow dépasse plusieurs heures avec besoin de reprise.

### 6.5 Scénarios opérationnels types

Pour fixer les idées, trois scénarios tirés du profil mini-DSI :

**Scénario A — Déploiement d'une nouvelle version de l'app X**

1. L'utilisateur demande à Claude Code : "déploie `my-obsidian-wiki` en v1.4.0 sur le VPS".
2. Claude, via le MCP GitLab, ouvre une MR dans le dépôt infra qui bump le tag d'image dans `docker-compose.yml`.
3. La pipeline GitLab CI valide le compose, lance un `ansible-playbook --check` en dry-run, publie un résumé en commentaire de MR.
4. L'utilisateur merge. Une pipeline `on: main` applique le playbook réel.
5. Un job post-deploy (smoke test HTTP) confirme le succès ou rollback.

Ici l'agent reste un **proposeur** : aucune autonomie, mais la friction est réduite à deux clics (approve MR, approve manual job).

Commandes réellement exécutées en coulisses :

```bash
# étape 3 : dry-run posté en commentaire de MR
ansible-playbook -i inventory.yml playbooks/site.yml \
  --limit my-obsidian-wiki --check --diff --tags deploy

# étape 4 : apply réel, déclenché par le manual job CI
ansible-playbook -i inventory.yml playbooks/site.yml \
  --limit my-obsidian-wiki --tags deploy

# étape 5 : smoke test
curl -sSf https://wiki.example.org/healthz | jq '.status == "ok"'
```

Trade-offs : le chemin MR → dry-run → manual apply ajoute 2 à 5 minutes face à un `compose up -d` direct, mais chaque action est auditée, ré-exécutable, et un retour en arrière se fait par simple `git revert` + re-run du playbook. À ce prix, l'agent peut itérer sans risque de mutation silencieuse.

**Scénario B — Triage d'une alerte Prometheus sur l'app Y**

1. Une alerte `AppDown` se déclenche (Prometheus → Alertmanager → webhook).
2. Le webhook réveille un workflow n8n / LangGraph qui instancie un agent de triage.
3. L'agent consulte : logs Loki (MCP Loki), métriques récentes (MCP Prometheus), état container (MCP Docker, read-only).
4. Il corrèle et ouvre une issue GitLab avec : symptômes, timeline, hypothèse, lien vers les logs pertinents.
5. Aucune action de remédiation automatique. L'humain tranche et agit (éventuellement via un second tour agent).

L'agent n'a ici qu'une capacité **read-only** et produit un artefact (l'issue). Le risque est minimal, la valeur d'investigation est réelle.

Exemples d'appels d'outils typiques de l'agent pendant le triage :

```
loki_query(query='{app="Y"} |= "error"', range='15m')
prometheus_query_range(query='rate(http_requests_total{app="Y",status=~"5.."}[1m])', range='30m')
docker_inspect(container='app-Y')
docker_logs(container='app-Y', tail=200)
gitlab_create_issue(project='infra', title='AppDown Y — triage auto',
                    body='<markdown résumé>', labels=['incident','ai-generated'])
```

Trade-offs : la qualité du triage dépend entièrement de la richesse des signaux exposés par les MCP en lecture. Mieux vaut investir dans 5 MCP read-only bien intégrés (Loki, Prometheus, Docker, Alertmanager, GitLab) qu'aspirer à l'auto-remédiation avec des outils en écriture mal sécurisés. Le coût LLM d'un triage reste modeste (quelques milliers de tokens) tant que l'agent ne rapatrie pas des mégaoctets de logs bruts — prévoir un résumé ou un filtrage côté MCP.

**Scénario C — Rotation des secrets trimestrielle**

1. Un cron GitLab déclenche un workflow "rotation secrets".
2. Un agent lit la liste des apps, identifie les secrets à faire tourner (JWT signing keys, tokens d'API, etc.).
3. Pour chaque app, il génère un nouveau secret, ouvre une MR modifiant un fichier chiffré (SOPS / Ansible Vault), et prévoit la bascule coordonnée.
4. L'utilisateur revoit la MR, l'accepte, la pipeline applique.
5. L'agent, toujours event-driven, re-passe après application et vérifie que chaque app est en bonne santé avec son nouveau secret.

Tâche rébarbative et à haut risque manuel : la valeur d'un agent est ici très nette, à condition que les *dry-run* et le schéma de bascule soient robustes.

Schéma de bascule type pour un secret à deux phases (génération + propagation) :

```
T0 : agent génère new_secret, l'ajoute au vault SOPS, ouvre MR
T0 + review : humain merge, CI applique → les apps reçoivent new_secret
              en variable d'env, mais continuent à signer avec old_secret
T0 + N minutes : agent relance un job de bascule qui fait pivoter
                 la variable "active" (feature flag simple)
T0 + N + X : agent vérifie santé (métriques auth réussies ≥ seuil),
             puis supprime old_secret du vault dans une seconde MR
```

Trade-offs : la phase double-clé coûte un cycle CI supplémentaire et exige que les apps sachent accepter *deux* secrets valides simultanément pendant la fenêtre de bascule. Cela se paie par un peu de code applicatif, mais évite les fenêtres de service dégradé pendant la rotation. Pour des secrets critiques (clés JWT, tokens OAuth), ce surcoût est justifié ; pour des secrets moins sensibles (webhook Discord), une rotation brutale avec 30 secondes d'indisponibilité reste acceptable.

**Scénario D — Quand l'agent se trompe : procédure de repli**

Un quatrième scénario, souvent sous-estimé : que se passe-t-il quand l'agent produit une MR défectueuse ou déclenche une action indésirable ?

1. Le verificator (humain ou agent) détecte l'anomalie — au mieux avant merge (diff surprenant), au pire après apply (smoke test rouge, alerte Prometheus).
2. Si l'incident est déjà en prod, un `git revert <sha>` + re-run du playbook suffit dans 90 % des cas, à condition que les playbooks soient idempotents et que la pipeline `ci/apply` soit rejouable.
3. Pour les 10 % restants (migration de schéma DB, changement de certificat TLS irréversible), un runbook humain documenté (cf. Annexe F) prend le relais. L'agent n'est pas qualifié pour ces cas.
4. L'incident est consigné dans un fichier `audit/agent-incidents.md` avec : MR fautive, symptôme, temps de détection, temps de remédiation, cause probable. Cette donnée nourrit l'amélioration des prompts et du catalogue d'outils MCP.

Trade-offs : cette discipline de journalisation coûte 10 à 15 minutes par incident, mais évite la répétition silencieuse du même bug par l'agent. Au bout de 6 mois, le fichier devient la meilleure source de vérité pour affiner le prompt système de l'executor ops.

## 7. Recommandations pour démarrer

### 7.1 Stack minimale (MVP weekend)

Objectif : avoir un cycle build → deploy → observer fonctionnel, sans agent permanent, avec des agents *déclenchables à la demande* via Claude Code.

```
┌───────────────────────────────────────────┐
│   Claude Code (client)                    │
│   └─ MCP Docker (local VPS via SSH tunnel)│
│   └─ MCP GitLab                           │
│   └─ MCP Filesystem (sur le repo infra)   │
└───────────────────────────────────────────┘
                 │
                 ▼ (MR)
┌───────────────────────────────────────────┐
│   Dépôt GitLab "infra" (Ansible + Compose)│
│   └─ CI : lint playbooks, dry-run         │
│   └─ Manual job : apply en prod           │
└───────────────────────────────────────────┘
                 │
                 ▼ (SSH + ansible)
┌───────────────────────────────────────────┐
│   VPS                                     │
│   └─ Docker Compose par app               │
│   └─ Caddy reverse-proxy auto-TLS         │
│   └─ node-exporter (léger, pour plus tard)│
└───────────────────────────────────────────┘
```

Composants concrets :

- **Claude Code** comme "cockpit agent" (déjà en place).
- **MCP Docker** local pour les actions sur le VPS (via un petit tunnel ou un runner dédié).
- **MCP GitLab** pour le cycle MR / issues / pipelines.
- **Pipelines GitLab CI** existants, éventuellement augmentés d'un job `lint:ansible` et `dry-run:compose`.
- **Zéro agent "de garde"** : tous les agents sont invoqués manuellement. Budget LLM parfaitement prévisible.

Gain immédiat : l'utilisateur peut demander à Claude "déploie l'app X en version Y" et le déploiement passe par une MR auto-ouverte, une pipeline CI, un apply manuel. GitOps minimal, agent en proposeur.

### 7.2 Stack évolutive (phase 2-3)

Quand le nombre d'apps dépasse 3-4, ou quand le besoin d'observabilité active émerge :

1. **Ajouter Coolify (ou Komodo)** comme couche de déploiement unifiée. Les playbooks Ansible se limitent alors au provisioning système et au bootstrap de la plateforme ; les apps elles-mêmes vivent dans Coolify. Les agents pilotent via l'API Coolify.
2. **Introduire un agent récurrent** (event-driven, pas permanent) : un workflow LangGraph ou n8n déclenché par webhook GitLab pour :
   - générer des release notes,
   - valider la santé post-déploiement,
   - ouvrir une issue si le smoke test rate.
3. **Ajouter MCP Prometheus / Loki** quand une stack d'observabilité (VictoriaMetrics + Grafana + Loki) est en place. Les agents peuvent alors faire du triage d'incident à la demande.
4. **Encapsuler les playbooks critiques** derrière un serveur MCP Ansible maison (ou communautaire une fois mûr) pour que les agents n'aient jamais à "deviner" une commande ansible-playbook — ils choisissent dans un catalogue fini.
5. **Envisager Dagger** pour les builds les plus lourds (images multi-stages, matrices de tests). La portabilité entre local et CI est un vrai gain ; l'intégration agentique via `Container Use` devient un bonus.

### 7.3 Critères de choix résumés (aide-mémoire)

Quand arbitrer entre plusieurs options, revenir à ces quelques critères :

| Critère | Question à se poser |
|---------|---------------------|
| **Reproductibilité** | Le pipeline / l'action d'agent est-il rejouable à l'identique ? |
| **Auditabilité** | Peut-on, 6 mois plus tard, savoir ce que l'agent a fait et pourquoi ? |
| **Coût marginal** | Chaque invocation a-t-elle un coût LLM + CPU borné et prévisible ? |
| **Courbe d'apprentissage** | Combien de week-ends pour être opérationnel ? |
| **Sortie facile** | Si le projet meurt demain, est-ce que je peux le remplacer sans tout jeter ? |
| **Surface de sécurité** | Quels privilèges l'agent a-t-il sur le système ? |

Un outil qui coche 5 sur 6 est généralement un meilleur choix qu'un outil qui coche les 6 mais qu'on ne comprend qu'à moitié.

### 7.4 Erreurs classiques observées dans des setups similaires

Au-delà des anti-patterns architecturaux, quelques erreurs récurrentes observées dans la littérature 2024-2025 et dans des retours d'expérience publics (blogs, confs) :

- **Sous-estimer le coût du contexte.** Un agent qui "lit l'ensemble du dépôt pour comprendre" à chaque invocation consomme 50 à 200 fois plus de tokens qu'un agent qui lit sélectivement. Sur 1000 invocations/mois, la différence se chiffre en dizaines d'euros.
- **Prompts systèmes copiés-collés sans adaptation.** Utiliser tel quel un prompt de framework générique mène souvent à des comportements incohérents avec la charte d'équipe (ton, formatage des MR, niveau de verbosité).
- **Absence d'environnement de répétition.** Déployer directement en prod l'amélioration d'un prompt est un anti-pattern. Avoir un environnement "staging agent" avec un dépôt miroir est un investissement rentable dès la 3ᵉ itération.
- **Dépendance à un modèle propriétaire sans alternative.** Si le framework ne tourne qu'avec un seul provider (OpenAI-only, Anthropic-only), toute indisponibilité paralyse la chaîne. Privilégier les frameworks qui acceptent plusieurs providers.
- **Confondre "agent intelligent" et "agent fiable".** Un agent moins capable mais dont on connaît précisément les limites et les modes de défaillance est préférable à un agent brillant mais imprévisible.

### 7.5 Anti-patterns à éviter

- **Agent "ops" permanent 24/7 sans budget LLM strict.** Même un petit agent de garde peut consommer des tokens de manière non bornée en cas de boucle infinie.
- **Donner à un agent un accès SSH root direct sans garde-fous.** Préférer un MCP Ansible avec une liste blanche de playbooks autorisés, ou un MCP Docker restreint aux commandes non-destructives. Réserve : l'écosystème MCP Ansible est encore jeune (cf. §3.4 et watchlist §8.2) ; valider l'implémentation retenue sur un bac-à-sable avant toute adoption en prod, ou se replier en attendant sur un wrapper maison autour de `ansible-runner`.
- **Mélanger trois frameworks d'agents "pour voir".** Choisir un point d'entrée (Claude Code pour l'interactif, un framework unique pour les workflows batch) et s'y tenir six mois.
- **Migrer l'existant (GitLab CI, Ansible) juste parce que "c'est pas agent-natif".** Ce qui marche et qu'on maîtrise a plus de valeur qu'un outil à la mode.
- **Orchestrer depuis le VPS de production.** Les exécutions agentiques consomment CPU, RAM et bande passante ; les pousser sur un runner dédié (même modeste) évite d'impacter les apps.
- **Kubernetes "au cas où".** Pour 3 apps sur un VPS, K8s coûte plus qu'il ne rapporte. Docker Compose + une plateforme PaaS suffit, et la plupart des agents ops savent s'y adapter.
- **Ignorer la traçabilité.** Toute action d'agent en prod doit laisser une trace : MR, commit, log centralisé. Sans ça, la post-mortem devient impossible.

## 8. Projets à suivre / watchlist

### 8.1 Comment évaluer un projet candidat

Avant d'adopter un projet de la watchlist, cinq indicateurs simples :

1. **Rythme de commits** sur les 6 derniers mois : un projet actif en publie au moins quelques dizaines. Sous ce seuil, suspicion d'abandon.
2. **Taille et diversité du pool de contributeurs** : un seul auteur signifie un risque de bus factor de 1.
3. **Clarté des issues fermées** : les issues critiques sont-elles traitées ou accumulées ?
4. **Présence d'un `CHANGELOG.md` ou de release notes** : signe de maturité opérationnelle.
5. **Existence d'une stratégie de versionnement** (semver, release cycle) : indispensable pour planifier les upgrades.

Un projet prometteur qui échoue sur 3 critères sur 5 reste un pari, pas un choix.

### 8.2 Liste de veille

Projets pertinents pour le profil mais qu'il est sage de **monitorer sans adopter** aujourd'hui — trop jeunes, trop instables, ou orientés entreprise.

- **Dagger Container Use (ex-Dagger AI)** — à re-évaluer tous les trimestres. Si l'intégration LLM gagne en stabilité, c'est potentiellement le meilleur moteur CI/CD agentique disponible en self-hosted.
- **Letta** — promesse forte (agents à mémoire persistante pour un "SRE de garde"), mais maturité opérationnelle encore à prouver. Intéressant si le VPS grossit et qu'un agent avec mémoire longue devient utile.
- **MCP Ansible** — plusieurs implémentations concurrentes en 2025 ; attendre qu'un leader émerge avant d'intégrer.
- **Komodo** — croissance rapide, très bon fit mini-DSI. À tester sur un environnement annexe avant production.
- **Kagent / divers projets CNCF "AI for K8s"** — écosystème en formation, à surveiller si migration K8s un jour.
- **GitLab Duo Agents / GitHub Actions Agents** — les offres natives des forges ; leur intégration s'enrichit en 2025-2026, parfois au prix du verrouillage vendeur. À surveiller sans enthousiasme excessif.
- **Temporal + agents** — pour quand les workflows d'agents deviendront trop longs ou trop durables pour un simple cron.

## 9. Sources et références

Les projets sont listés par ordre d'apparition dans le document. Les URLs pointent vers les dépôts officiels ou les sites de référence, non vérifiées à la minute près mais stables historiquement.

**Frameworks d'agents généralistes**

- LangGraph — <https://github.com/langchain-ai/langgraph>
- CrewAI — <https://github.com/crewAIInc/crewAI>
- AutoGen — <https://github.com/microsoft/autogen> / AG2 — <https://github.com/ag2ai/ag2>
- Letta — <https://github.com/letta-ai/letta>
- Dify — <https://github.com/langgenius/dify>
- n8n — <https://github.com/n8n-io/n8n>
- Flowise — <https://github.com/FlowiseAI/Flowise>
- Temporal — <https://github.com/temporalio/temporal>

**Agents DevOps / SRE**

- K8sGPT — <https://github.com/k8sgpt-ai/k8sgpt>
- HolmesGPT — <https://github.com/robusta-dev/holmesgpt>
- Robusta — <https://github.com/robusta-dev/robusta>
- Kubiya — <https://kubiya.ai>
- Dagger Container Use — <https://github.com/dagger/container-use>

**Moteurs CI/CD programmables**

- Dagger — <https://github.com/dagger/dagger>
- Earthly — <https://github.com/earthly/earthly>
- Tekton — <https://github.com/tektoncd/pipeline>
- Woodpecker CI — <https://github.com/woodpecker-ci/woodpecker>
- act (GHA local) — <https://github.com/nektos/act>

**Serveurs MCP**

- Spécification MCP — <https://modelcontextprotocol.io>
- MCP Docker (officiel) — <https://github.com/docker/mcp-servers>
- MCP GitHub — <https://github.com/github/github-mcp-server>
- Inventaire MCP communautaire — <https://github.com/modelcontextprotocol/servers>

**Plateformes self-hosted**

- Coolify — <https://github.com/coollabsio/coolify>
- Dokku — <https://github.com/dokku/dokku>
- CapRover — <https://github.com/caprover/caprover>
- Komodo — <https://github.com/moghtech/komodo>
- Portainer — <https://github.com/portainer/portainer>
- Dockge — <https://github.com/louislam/dockge>

**Lectures complémentaires et contexte**

- CNCF Landscape — section "AI for DevOps" : <https://landscape.cncf.io>
- Articles de référence sur les agents ops : blogs Robusta, Dagger, LangChain (recherche datée 2024-2026).
- Discussions KubeCon 2024-2025 sur l'intégration LLM / Kubernetes (vidéos CNCF YouTube).

---

**Limites de ce document** :

- Les chiffres de stars sont des ordres de grandeur observés au premier trimestre 2026, non vérifiés en temps réel — à recouper si l'on veut un chiffre exact.
- L'écosystème MCP évolue vite : certains serveurs cités peuvent avoir été renommés, abandonnés ou supplantés depuis la rédaction.
- Le panorama ignore délibérément les offres SaaS entièrement managées (Vercel AI, Render AI, etc.) qui ne correspondent pas au cahier des charges self-hosted.
- Aucune comparaison de coût LLM n'est donnée ; elle dépend trop du volume d'usage pour être pertinente dans un document statique.

---

## Annexe A — Notes sur le coût LLM et le choix du modèle

Le coût d'opérer des agents LLM dans le cycle CI/CD dépend de trois facteurs : **fréquence d'invocation**, **longueur du contexte**, **puissance du modèle**. Quelques règles empiriques utiles :

- **Pour une action déterministe bien cadrée** (lint, smoke test, génération d'un changelog), un petit modèle (haiku-class, ou un modèle ouvert 7-14B) suffit. Le gain d'un grand modèle est marginal et le coût s'accumule vite.
- **Pour du diagnostic ou de la planification** (triage d'incident, génération de playbook), un modèle "moyen" (sonnet-class) offre le meilleur ratio qualité/coût.
- **Pour une analyse profonde ponctuelle** (post-mortem d'un incident complexe, revue d'architecture), un grand modèle (opus-class) est justifié, mais doit rester exceptionnel.
- **Local vs cloud** : un modèle local (Ollama, llama.cpp) sur le VPS lui-même est tentant mais consomme la RAM/CPU des apps. Un serveur LLM dédié (autre VPS, ou API payante) isole mieux les charges.
- **Budget mensuel explicite** : fixer un plafond mensuel (par exemple, 10€ / mois sur une API) force la parcimonie. Au-delà du plafond, les invocations tombent sur un modèle local ou sont différées.

Pour un profil mini-DSI, une règle raisonnable est : **cloud + petit modèle pour 95 % des actions, cloud + grand modèle pour 5 %, local pour la redondance**. La surveillance mensuelle (cf. Annexe B) rend cette discipline soutenable.

## Annexe B — Matrice patterns × taille du parc

Une lecture croisée pour affiner le choix d'architecture selon le nombre d'apps gérées. Les croix indiquent le niveau de pertinence : `+` possible, `++` adapté, `+++` recommandé, `-` à éviter.

| Pattern | 1-2 apps | 3-5 apps | 6-10 apps | 10+ apps |
|---------|----------|----------|-----------|----------|
| Orchestrateur central | `+++` | `++` | `+` | `-` |
| Fleet d'agents | `-` | `+` | `++` | `+++` |
| MCP-bus | `++` | `+++` | `+++` | `+++` |
| GitOps + agents | `+++` | `+++` | `+++` | `+++` |
| Event-driven | `++` | `+++` | `+++` | `++` |

Lecture : pour 1-2 apps, la simplicité prime — un orchestrateur central assorti de GitOps suffit. Au-delà de 5 apps, la fleet et le MCP-bus deviennent structurants. GitOps est toujours pertinent ; c'est la forme de discipline de base.

## Annexe C — Observabilité des agents eux-mêmes

Un point souvent négligé : **qui surveille l'agent ?** Trois dimensions à instrumenter dès le début :

1. **Traces d'exécution** : chaque appel d'outil par l'agent est tracé avec timestamp, arguments, résultat. Outils : LangSmith (si on utilise LangGraph), OpenTelemetry + collecteur maison, ou simple log structuré en JSON.
2. **Coûts par invocation** : tokens in, tokens out, modèle appelé, coût estimé. Un simple wrapper autour du client LLM fait l'affaire ; sans cette métrique, la dérive de coût ne se détecte qu'au relevé mensuel.
3. **Taux d'échec et de correction humaine** : combien de MR d'agents sont mergées telles quelles, combien sont corrigées, combien sont fermées ? Cette donnée guide l'itération sur les prompts et l'outillage.

Pour un profil mini-DSI, un tableau de bord Grafana minimal (3 panneaux : invocations/jour, coût/jour, taux d'acceptation MR) est largement suffisant et dissuade les dérives silencieuses.

## Annexe D — Relation avec kiss-claw (le framework utilisé par l'auteur)

L'utilisateur emploie déjà **kiss-claw**, un méta-framework d'orchestration multi-agents en Claude Code. Il s'inscrit dans le pattern **fleet d'agents spécialisés** (orchestrator / executor / verificator) avec un substrat de session partagée (`KISS_CLAW_SESSION`).

Placement dans le paysage :

- **Catégorie** : framework d'agents généraliste, spécialisé par la définition de rôles (orchestrator, executor, verificator, planificator).
- **Pattern principal** : orchestrateur central + séparation stricte *auteur / vérificateur*. Intègre un mécanisme de checkpoint et de rejeu.
- **Force** : le *separation of concerns* entre celui qui produit et celui qui vérifie est un invariant conceptuel solide. Réduit les risques de sur-confiance.
- **Complémentarité avec le paysage CI/CD** : kiss-claw sait orchestrer du travail agentique mais **n'apporte pas** d'intégration native build/deploy/monitor. Les intégrations doivent venir par MCP (Docker, GitLab, Ansible) ou par des scripts appelés par l'executor.
- **Évolution naturelle** : pour piloter le CI/CD du VPS, définir un *rôle executor spécialisé "ops"* avec accès MCP Docker + MCP GitLab, et un verificator ops (vérifie qu'aucune action mutante sans MR associée). L'orchestrateur reste le même.

Concrètement, kiss-claw se positionne comme **la couche d'orchestration de travail cognitif** (planification, rédaction, revue) ; les frameworks de la section 3.1 (LangGraph, n8n…) seraient, en complément, **la couche d'exécution ops** pour des workflows récurrents non-interactifs. Les deux ne sont pas concurrentes.

**Parallèle plus détaillé entre kiss-claw et une mini-DSI agentique.** Plusieurs invariants structurels de kiss-claw se transposent directement au pilotage CI/CD :

- **Session isolée par `KISS_CLAW_SESSION`** ↔ **environnement de run isolé par identifiant de pipeline**. Dans les deux cas, on veut rejouer ou auditer un traitement sans que deux exécutions concurrentes ne se marchent dessus. Le token de session kiss-claw est l'équivalent conceptuel d'un `CI_PIPELINE_ID` GitLab : un identifiant court qui sert de clé pour tous les artefacts produits pendant le run.
- **Séparation executor / verificator** ↔ **pipeline `build+apply` vs `verify`**. L'executor propose un changement, le verificator le juge sur critères objectifs (compile, tests passent, diff acceptable). Transposé aux ops : l'agent ops propose une MR, une pipeline `ci/verify` indépendante la juge. L'agent n'auto-approuve jamais son propre travail.
- **Checkpoint + rejeu** ↔ **MR + revert Git**. Le mécanisme de checkpoint de kiss-claw (qui permet de reprendre un run interrompu) a pour équivalent ops le commit atomique : toute mutation agent produit un état reproductible par rejeu.
- **REVIEWS.md accumulé dans la session** ↔ **commentaires de MR + artefacts CI**. La trace écrite et horodatée qui justifie la décision est la même primitive dans les deux contextes.

**Rôle "executor ops" à définir.** Pour piloter le CI/CD du VPS, on pourrait définir dans kiss-claw un rôle `executor-ops` dont le prompt système inclurait :

```
- Tu opères exclusivement via des MR GitLab, jamais par SSH direct.
- Toute action mutante doit être précédée d'un dry-run posté en MR.
- Tu n'as pas accès aux secrets applicatifs ; ils sont injectés par la CI.
- Tu ouvres une MR par intention logique, pas par fichier modifié.
- Si tu détectes une anomalie, tu ouvres une issue et tu t'arrêtes.
```

Et un `verificator-ops` correspondant :

```
- Vérifie qu'aucune MR de l'executor ne pousse de secret en clair.
- Vérifie que chaque MR porte le label `ai-generated`.
- Vérifie que le dry-run Ansible est présent en commentaire.
- Vérifie que les tests smoke sont définis pour les apps touchées.
- Signale sans approuver : l'approbation finale reste humaine.
```

**Pourquoi ce schéma colle au profil mini-DSI.** Un opérateur humain seul ne peut pas jouer simultanément les rôles d'auteur et de relecteur critique de ses propres changements — c'est le même biais cognitif qui rend la relecture de son propre code peu efficace. Le découpage kiss-claw le prend en charge par construction. Pour une mini-DSI où l'humain est déjà overbooké, déléguer la revue mécanique (lint, conformité, dry-run) à un verificator agentique libère le temps humain pour les décisions qui le méritent vraiment : faut-il déployer ce soir, ce changement est-il stratégiquement aligné, etc.

**Limite à garder à l'esprit.** kiss-claw n'apporte aucun outil prêt à l'emploi pour les ops ; il fournit la discipline d'orchestration mais les intégrations (MCP Docker, MCP GitLab, serveurs maison) restent à brancher. Tenter de le substituer à un framework d'agents généraliste comme LangGraph pour des workflows longs et durables serait un contre-emploi — kiss-claw vise la collaboration synchrone avec un humain, pas l'exécution asynchrone à large échelle.

## Annexe E — Glossaire express

- **Agent (au sens LLM)** : entité logicielle combinant un LLM, un prompt système, un ensemble d'outils, et une boucle de raisonnement (typiquement *ReAct* ou *Plan-Act-Observe*).
- **MCP (Model Context Protocol)** : protocole standardisé en 2024 par Anthropic, adopté progressivement par d'autres éditeurs, qui définit comment un LLM peut découvrir et appeler des outils externes exposés par un serveur dédié.
- **GitOps** : approche opérationnelle où l'état désiré de l'infra est défini dans un dépôt Git et réconcilié par un opérateur. Toute mutation passe par un commit.
- **Human-in-the-loop** : point d'arrêt explicite dans un workflow agent où une approbation humaine est requise avant de poursuivre.
- **DAG (Directed Acyclic Graph)** : structure de pipeline où les étapes sont liées par des dépendances sans boucle. Tekton, Dagger et GitLab CI sont tous des moteurs de DAG.
- **Container Use** : mode récent de Dagger permettant à un agent LLM de composer des pipelines Dagger, avec exécution dans un conteneur isolé.
- **Mini-DSI** : désigne ici une équipe de 1-2 personnes opérant un petit parc applicatif avec une exigence professionnelle (traçabilité, sécurité) mais sans les moyens d'une DSI d'entreprise.
- **ReAct** : pattern d'agent alternant *Reasoning* (le LLM réfléchit) et *Acting* (le LLM appelle un outil). Boucle classique des agents modernes.
- **Runner** : hôte d'exécution d'un job CI/CD. Peut être partagé ou dédié. Héberger un runner sur le VPS lui-même est déconseillé pour des raisons d'isolation.
- **Dry-run** : exécution simulée qui rapporte ce qui serait fait sans le faire réellement. Premier garde-fou agent.

## Annexe F — Check-list de démarrage (concrète)

Pour qui veut passer à l'action ce week-end, en restant dans le périmètre "stack minimale" :

- [ ] Un dépôt `infra/` GitLab contient : `inventory.yml`, `playbooks/site.yml`, `docker-compose/<app>/` par app déployée.
- [ ] Le VPS a un utilisateur `deploy` non-root avec accès SSH clé publique, sudoers limité aux commandes nécessaires (ou `ansible_become_password` via vault).
- [ ] Caddy (ou équivalent) gère le reverse-proxy et le TLS automatique. Aucune app n'écoute directement sur 80/443.
- [ ] Un job `ci/lint` valide `docker compose config` et `ansible-lint` à chaque MR.
- [ ] Un job `ci/dry-run` exécute `ansible-playbook --check --diff` et poste le résultat en commentaire de MR.
- [ ] Un job `ci/apply` (manuel, branche `main`) applique réellement.
- [ ] Un job `ci/smoke` vérifie que chaque app répond sur son endpoint de santé.
- [ ] Claude Code est configuré avec au moins : MCP GitLab (lecture MR / CI status), MCP Filesystem (sur le repo infra local), un MCP Docker si l'accès au VPS est tunnellé.
- [ ] Un fichier `AGENTS.md` à la racine du dépôt infra décrit : périmètre, commandes autorisées, chemins sensibles, conventions de MR.
- [ ] Un suivi mensuel : combien de MR ouvertes par agent, combien mergées, quels incidents ?

**Étapes complémentaires pour durcir le setup sur la durée** (à étaler sur plusieurs week-ends, pas à empiler d'un coup) :

- [ ] **Backup infra versionné.** Un job cron hebdomadaire qui `pg_dump` (ou équivalent) chaque base applicative, chiffre le dump avec age/SOPS, et le pousse vers un bucket S3-compatible (ou un second VPS). Restauration testée au moins une fois par trimestre.
- [ ] **Journal des actions d'agent.** Un fichier `audit/agent-actions.jsonl` en append-only sur le repo infra, où chaque invocation agent laisse une ligne (timestamp, agent, action, MR associée). Pas besoin d'outillage lourd ; un simple hook post-MR suffit.
- [ ] **Kill-switch documenté.** Un fichier `infra/AGENTS_DISABLED` dont la présence à la racine désactive tous les workflows CI déclenchés par des agents. Documenter la commande exacte (`touch AGENTS_DISABLED && git commit && git push`) dans le `AGENTS.md`.
- [ ] **Bac-à-sable staging.** Un sous-domaine `staging.example.org` avec une copie légère de la stack où les agents peuvent itérer sans affecter la prod. Synchroniser l'inventaire entre staging et prod via un include Ansible commun.
- [ ] **Budget LLM mensuel chiffré.** Un dashboard (même minimal : un gist ou un Grafana) qui remonte tokens consommés / coût estimé par semaine. Seuil d'alerte à 80 % du budget mensuel prévu.
- [ ] **Rotation de secrets trimestrielle planifiée.** Un événement récurrent dans l'agenda du user, avec pour livrable la checklist d'apps ayant tourné leurs secrets (cf. scénario C).
- [ ] **Revue annuelle des MCP.** Une fois par an, réévaluer chaque serveur MCP installé : toujours maintenu ? alternative plus mûre disponible ? outils exposés toujours pertinents ? Supprimer sans regret les intégrations dormantes.
- [ ] **Documentation des runbooks critiques.** Au moins trois runbooks écrits à la main (pas générés par agent) : "restaurer depuis backup", "rollback d'une app en urgence", "révoquer un secret compromis". Les agents peuvent assister mais pas remplacer l'expertise humaine sur ces procédures critiques.

Cette check-list n'introduit **aucun outil agentique nouveau** au sens fort : elle prépare simplement le terrain pour que les agents (Claude Code en tête) soient utiles, traçables et sans risque. Le reste viendra par itérations.

Les étapes complémentaires, elles, construisent progressivement un socle défensif : sauvegarde, audit, kill-switch, bac-à-sable, budget. Un agent ne fait pas oublier les fondamentaux SRE — il les rend d'autant plus nécessaires que son comportement reste probabiliste.

