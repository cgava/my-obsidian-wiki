# patch-system — documentation utilisateur

Le **patch-system** est un gestionnaire de patches locaux idempotents, inspiré
de **quilt + DEP-3** et de **Gentoo `etc-update`**, conçu pour corriger les
anomalies du vendor `vendor/obsidian-wiki` tracké via un remote upstream
**non-forkable**. Les patches sont stockés dans le super-repo (`patches/`) et
re-appliqués à la demande sur le working tree du submodule, qui reste
pristine.

Cette documentation suit le modèle **Diataxis** (<https://diataxis.fr>) : quatre
quadrants distincts pour quatre besoins distincts.

## Les 4 quadrants

| Quadrant | Fichier | Quand l'utiliser |
|---|---|---|
| **Tutoriel** | [tutorial.md](./tutorial.md) | Première prise en main, ~15 min, apprentissage guidé sur des fixtures. |
| **Recettes (how-to)** | [how-to.md](./how-to.md) | Besoin ponctuel — « comment faire X ? », procédure courte, sans pédagogie. |
| **Référence** | [reference.md](./reference.md) | Chercher un flag, un exit code, la sémantique exacte d'un état, le schéma JSON. |
| **Explication** | [explanation.md](./explanation.md) | Comprendre les choix de design : pourquoi submodule pristine, pourquoi détection composite, pourquoi pas d'auto-commit. |

## Statut

> **Jalons J1-J8 (sur 16) livrés** — commandes opérationnelles : `list`,
> `status`, `describe`, `diff`, `apply`, `rollback`. Les commandes `verify`
> (J9), `refresh` (J10) et `record` (J11) sont présentes en stub et retournent
> un message « not yet implemented » avec exit code non nul.

## Pointeurs amont

La documentation utilisateur ci-présente **ne remplace pas** les documents de
conception. Pour les décisions structurantes, lire :

- [`../../docs/260420-patch-system-design.md`](../../docs/260420-patch-system-design.md)
  — **design autoritatif** (783 lignes) : architecture logique (§2), schéma de
  storage (§3), UX CLI (§4), arbitrage des 8 points ouverts (§5), plan
  d'implémentation jalonné (§7).
- [`../../docs/260420-patch-system-soa.md`](../../docs/260420-patch-system-soa.md)
  — **état de l'art** (605 lignes) : comparatif quilt / DEP-3 / Debian 3.0 /
  etc-update / Ansible / Puppet / detection strategies, recommandation §4.
- [`../../docs/adr/ADR-0001-vendor-submodule-pristine.md`](../../docs/adr/ADR-0001-vendor-submodule-pristine.md)
  — décision « submodule + régénération déterministe » (structurante).
- [`../../docs/adr/ADR-0002-registre-runtime-separation.md`](../../docs/adr/ADR-0002-registre-runtime-separation.md)
  — séparation `series.json` (registre logique) / `runtime.json` (config
  d'exécution).

Chaque fichier de ce dossier cite **verbatim** les sections pertinentes du
design doc, avec une note `Source : docs/260420-patch-system-design.md §X.Y`.
En cas de divergence entre cette doc et le design, **le design fait foi**.
