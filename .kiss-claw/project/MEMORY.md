# MEMORY.md — shared project context

> Auto-loaded by all agents. Keep under 200 lines.

## Project

- **Name**: my-obsidian-wiki — Mise en production VPS
- **Goal**: Déployer en production sur VPS avec GitLab CI + Ansible + Docker Compose
- **Status**: Phase 1 / Préparation GitLab

## Tech stack

- Obsidian Wiki (fork bash/skills) — vendor/obsidian-wiki
- my-claude-minion (Python 3.10+, Docker) — vendor/my-claude-minion
- knlg-repo (vault dual-zone s0/s2) — knlg-repo/
- QMD MCP server (optionnel) — pas encore installé
- Ansible (provisioning + deploy)
- GitLab CI (build, test, deploy pipeline)
- Docker Compose (orchestration services)
- Nginx ou Caddy (reverse proxy + TLS)

## Non-goals

- Multi-utilisateur
- Haute disponibilité / scaling
- Kubernetes
- Nouvelles features (stabilisation d'abord)

## Contexte infra

- VPS existant, user applicatif à créer
- GitLab.com (compte existant)
- Mono-utilisateur
- L'utilisateur connaît Ansible + GitLab CI (usage professionnel)

## Agents in use

- kiss-orchestrator — planning and state
- kiss-executor — implementation
- kiss-verificator — reviews
- kiss-improver — improvement loop

## Key decisions

- 2026-04-19 — GitLab CI + Ansible + Docker Compose (pas Nix, pas git+systemd seul) — familiarité Ansible, build externalisé, rollback via image tags
