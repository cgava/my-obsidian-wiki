# my-obsidian-wiki — Mise en production VPS

## Goal
Déployer my-obsidian-wiki en production sur un VPS avec pipeline GitLab CI + Ansible, pour un usage quotidien mono-utilisateur stable.

## Non-goals
- Multi-utilisateur / gestion des accès
- Haute disponibilité / scaling
- Migration vers Kubernetes
- Développement de nouvelles features (stabilisation d'abord)

## Phases

### Phase 1 — Préparation GitLab & structure du projet
- [ ] Créer le projet GitLab (ou configurer le repo existant sur gitlab.com)
- [ ] Définir la structure du repo pour le déploiement : `deploy/ansible/`, `deploy/docker/`, `ci/`
- [ ] Documenter l'inventaire Ansible (hosts, variables) pour le VPS cible
- [ ] Créer le `.gitlab-ci.yml` squelette (stages: lint, build, test, deploy)

### Phase 2 — Provisioning VPS (Ansible)
- [ ] Playbook `provision.yml` : créer l'utilisateur applicatif dédié, configurer SSH (clé, sudoers)
- [ ] Playbook `baseline.yml` : installer les dépendances système (git, python3, node, docker, docker-compose)
- [ ] Playbook `firewall.yml` : configurer ufw/iptables (SSH, HTTP/HTTPS, ports applicatifs)
- [ ] Playbook `tls.yml` : reverse proxy (nginx/caddy) + Let's Encrypt
- [ ] Valider le provisioning : test de connexion SSH avec le user applicatif, services de base up

### Phase 3 — Conteneurisation des services
- [ ] Dockerfile pour obsidian-wiki (fork, build depuis la branche locale)
- [ ] Dockerfile pour my-claude-minion (adapter le Docker existant dans vendor/)
- [ ] Dockerfile pour QMD MCP server (optionnel, si activé)
- [ ] `docker-compose.yml` orchestrant tous les services + volumes pour les vaults
- [ ] `docker-compose.override.yml` pour le dev local (bind mounts, ports debug)
- [ ] Script `Makefile` : `make build`, `make up`, `make down`, `make logs`, `make deploy`

### Phase 4 — Pipeline CI/CD (GitLab CI)
- [ ] Stage `lint` : validation syntaxique (shellcheck skills, yamllint, etc.)
- [ ] Stage `build` : build des images Docker, push vers GitLab Container Registry
- [ ] Stage `test` : tests fonctionnels (wiki-ingest, wiki-query sur vault de test)
- [ ] Stage `deploy` : Ansible déploie les images taguées sur le VPS (manual trigger ou auto sur main)
- [ ] Configurer les variables CI/CD dans GitLab (SSH_KEY, VPS_HOST, etc.)
- [ ] Tester le pipeline complet : push → build → test → deploy

### Phase 5 — Gestion des données & vaults
- [ ] Stratégie de persistance : volumes Docker nommés pour les vaults s0/s2
- [ ] Backup automatisé : script cron (ou Ansible) pour snapshot des vaults vers stockage externe
- [ ] Seed initial : déployer le contenu actuel de knlg-repo sur le VPS
- [ ] Vérifier l'isolation s0/s2 en production (pas de fuite entre zones)

### Phase 6 — Maintenance & opérations
- [ ] Stratégie de mise à jour du fork : documenter le workflow rebase/merge upstream
- [ ] Playbook `update.yml` : pull nouvelles images, restart services, rollback si healthcheck échoue
- [ ] Monitoring basique : healthchecks Docker, alertes (mail ou webhook si service down)
- [ ] Runbook opérationnel : procédures pour rollback, restore backup, mise à jour urgente
- [ ] Tag de la v1.0.0 : première release stable en production
