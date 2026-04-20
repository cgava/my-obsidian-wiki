# ADR-0001 — Vendor submodule pristine + regeneration deterministe

- Date : 2026-04-20
- Statut : Accepted
- Session kiss-claw : 20260420-104751
- Phase : 2 — Design architecture
- Documents amont : `docs/260420-patch-system-soa.md` §2.2 / §2.5 / §4.6 pt 3, `docs/260420-patch-system-design.md` §5.3

## Contexte

Le projet maintient `vendor/obsidian-wiki` (skills bash/markdown) track via
un remote Git upstream **non-forkable** (pas de droits de push). L'audit
`docs/260418-dual-sensitivity-analysis.md` a identifie des anomalies
bloquantes (B1-B4) et trompeuses (p2-read-dotenv, p2-raw-in-vault) qui
exigent des corrections locales persistantes. La Phase 1 (etat de l'art) a
retenu un systeme de patches quilt-like + header DEP-3 enrichi. Il reste a
trancher **comment materialiser concretement les patches dans le depot
super-repo**, ce qui conditionne tout le reste (apply, rollback, drift,
survie aux `git pull` upstream, collaboration).

Le SOA §4.6 pt 3 a formalise 3 options :
- **(a) Submodule + regeneration deterministe** — le submodule reste
  pristine (tracking upstream pur), les patches sont stockes dans le
  super-repo et re-appliques a chaque checkout/fresh clone par
  `patch-system apply`.
- **(b) Subtree + commits locaux** — import complet du vendor dans le
  super-repo, merges periodiques via `git subtree pull`, patches stockes
  comme commits normaux du super-repo.
- **(c) Submodule + commits-in-submodule** — les patches sont des commits
  faits *dans* le submodule, divergeant localement de l'upstream.

Le choix impacte :
1. **Survie a `git pull` submodule** — qui conserve les patches au travers
   d'une mise a jour upstream ?
2. **Reversibilite** — comment revenir a un etat pristine ?
3. **Clarte historique** — peut-on distinguer code upstream / corrections
   locales dans `git log` ?
4. **Collaboration** — l'etat post-patch est-il partageable entre machines
   de dev ?
5. **Complexite operationnelle** — combien d'etapes pour un nouveau
   contributeur qui clone le repo ?

## Decision

**Nous retenons l'option (a) : submodule git + regeneration deterministe.**

Concretement :
- `vendor/obsidian-wiki` reste un `git submodule` classique, pointant vers
  un commit de l'upstream. `git -C vendor/obsidian-wiki log` = historique
  upstream pur, sans modifications locales.
- Les patches locaux sont stockes dans le super-repo sous `patches/`
  (`series.json` + `runtime.json` + `*.patch` avec header DEP-3 enrichi).
- Les patches ne sont **jamais** commites dans le submodule. Apres un
  `git submodule update`, le working tree du submodule est reset a
  l'upstream ; `patch-system apply --all` regenere l'etat patched.
- Le sha du submodule enregistre dans le super-repo (`gitlink`) est le **sha
  upstream**, pas un sha local. Aucun besoin de push d'un fork.
- Un champ `vendor_baseline_sha` dans `series.json` enregistre le sha
  upstream contre lequel les patches ont ete calibres. Un decalage entre
  ce champ et le HEAD courant du submodule = signal de drift potentiel a
  arbitrer (`patch-system verify`).

Cette decision est structurante : elle implique que l'etat patched est
**transitoire** (working tree uniquement), et que le patch-system doit etre
**idempotent, rapide et testable** — parce qu'il sera execute frequemment
(apres chaque clone, apres chaque submodule update).

## Consequences

### Positives

- **Separation nette upstream / local** : `git log` du submodule n'est
  jamais pollue par nos corrections. `git log` du super-repo montre
  l'evolution des patches (ajouts, refreshes) sans melange avec le code
  upstream.
- **Survie aux `git pull` upstream triviale** : un `git submodule update
  --remote` met le submodule a un nouveau HEAD upstream, le working tree
  vendor est reset, `patch-system apply` regenere. Pas de merge conflict
  entre "nos commits locaux" et "les commits upstream" — ce conflit-la
  n'existe tout simplement pas.
- **Reversibilite triviale** : `rollback --all`, ou `git -C vendor/obsidian-wiki
  checkout .`, ou `git submodule update --force`. Trois chemins qui donnent
  tous l'etat pristine.
- **Audit-ability** : chaque `.patch` est un fichier *review-able* avec un
  header DEP-3 qui explique le *pourquoi* (champs `Description`,
  `X-Audit-Ref`, `X-Severity`). Chaque anomalie est traceable jusqu'a
  `docs/260418-dual-sensitivity-analysis.md`.
- **Forwardabilite upstream future** : le jour ou l'upstream devient
  contribuable (fork autorise, PR possible), un `.patch` DEP-3 est
  directement utilisable (`git am` ou envoi via mailing list) sans
  retraitement.
- **Aucun fork non partageable** : chaque machine de dev clone le meme
  super-repo, le meme submodule (point vers le meme sha upstream), applique
  les memes patches. Etat reproductible.
- **Coherent avec le pattern Debian 3.0 quilt** (SOA §2.2) : "pristine +
  serie + regeneration deterministe" est le modele mature pour "vendoring
  corrige". Nous le transposons au git submodule.

### Negatives

- **Etape supplementaire au bootstrap** : apres `git clone && git submodule
  update --init`, l'utilisateur doit lancer `patch-system apply --all`
  pour obtenir un vendor fonctionnel. Mitigation : documente clairement
  dans le README ; peut etre automatise par un hook `git hooks/post-checkout`
  en Phase 4.
- **Etat patched non persistant sur disque** : si quelqu'un inspecte le
  working tree vendor apres un simple `git clone` (sans `apply`), il ne
  voit pas les corrections — il peut croire que le bug est toujours la.
  Mitigation : la commande `patch-system status` expose l'ecart ; le
  README recommande l'apply en bootstrap.
- **Charge computationnelle recurrente** : `patch-system apply --all` est
  execute souvent (chaque checkout / chaque bump upstream). Doit rester
  sous la seconde pour ne pas friction le workflow. Mitigation : le
  design privilegie `git apply --check` rapide ; les patches sont petits
  (~quelques hunks chacun).
- **Drift detection oblige** : un `git pull` upstream peut invalider un
  patch sans que personne ne s'en rende compte avant le prochain
  `apply`/`verify`. Mitigation : `patch-system verify` + integration CI
  (verifier systematiquement apres un submodule bump). Le design prevoit
  un champ `vendor_baseline_sha` pour le signal.

### Neutres

- **Duplication d'information** : le sha du submodule est *a la fois* dans
  le super-repo (gitlink) et dans `series.json` (`vendor_baseline_sha`).
  Une divergence entre les deux est justement le signal voulu — pas un
  bug.
- **Pas d'auto-commit lie** : l'ADR-0001 rend l'option "auto-commit apres
  apply" quasi-obligatoirement negative (cf. Design §5.2). Commiter dans
  un submodule qui doit rester pristine serait une contradiction. C'est
  donc un impact indirect **accepte**.
- **Monorepo simple** : le repo racine reste un seul super-repo avec un
  submodule. Aucun split en multi-repos.

## Alternatives rejetees

### Alternative B — subtree + commits locaux

**Principe** : `git subtree add --prefix vendor/obsidian-wiki <upstream>
<ref> --squash` importe l'arbre upstream dans le super-repo. Les patches
sont ensuite des commits normaux qui modifient `vendor/obsidian-wiki/*`.
Les mises a jour upstream se font via `git subtree pull --prefix
vendor/obsidian-wiki <upstream> <ref> --squash`.

**Avantages** :
- Patches sont de vrais commits git, visibles dans `git log`.
- Pas d'etape bootstrap supplementaire (le checkout contient deja l'etat
  patched).
- `git blame` sur les lignes patchees pointe vers le commit explicatif.

**Raisons du rejet** :
- **Melange upstream / local dans l'historique** : `git log vendor/` affiche
  un mix de commits squash upstream + commits locaux de patches. Pas de
  separation lisible. Pour un auditeur (qui veut distinguer "bug upstream"
  de "notre correction"), lecture complexe.
- **Forwardabilite upstream dégradée** : pour envoyer un patch upstream, il
  faut reconstruire un `.patch` propre a partir d'un `git format-patch` sur
  le commit local — le commit inclut du contexte super-repo (commit message,
  auteur, refs super-repo) qui n'a pas de sens cote upstream. Notre
  approche (a) garde le `.patch` toujours forwardable sans transformation.
- **Merge subtree frictionnel** : `git subtree pull --squash` merge l'etat
  upstream ; nos commits locaux doivent ensuite etre "replayed" au-dessus —
  en pratique, c'est du rebase manuel a chaque upstream update. Les
  conflits peuvent etre douloureux (le squash fait perdre le contexte par
  commit upstream).
- **Reversibilite floue** : `rollback` d'un patch = `git revert` du commit
  correspondant ; mais le revert ne re-genere pas la pristine a
  l'identique, il cree un nouveau commit inverse — l'historique gonfle a
  chaque aller-retour.
- **Separation `code upstream` / `corrections locales` perdue** :
  contrairement au modele Debian 3.0 quilt ou `debian/patches/` est
  visiblement distinct du tarball pristine. Avec subtree, les deux sont
  dans le meme cone de fichiers.

### Alternative C — submodule + commits-in-submodule

**Principe** : `vendor/obsidian-wiki` est un submodule classique, mais les
patches sont commites *dans* le submodule (crud locaux). Le sha du
submodule enregistre dans le super-repo est le sha **post-patch** (HEAD
local, pas upstream).

**Avantages** :
- Etat patched persistant : apres `git clone && git submodule update
  --init`, le working tree du submodule est deja patched.
- Pas de commande `apply` a lancer au bootstrap.
- Inspection visuelle du vendor = etat reel utilise.

**Raisons du rejet** :
- **`git pull upstream` cote submodule = conflit garanti** : notre HEAD
  local diverge de l'upstream. Chaque update demande un `git rebase` ou
  `git merge` manuel de nos commits contre upstream — plus invasif qu'un
  rejouer de patches.
- **Etat non partageable sans push** : le HEAD local du submodule n'existe
  sur aucun remote (impossible, upstream non-forkable). Pour que les autres
  machines de dev voient l'etat patched, il faut soit (i) push du
  submodule vers un remote alternatif (complexifie l'infra : hebergement
  d'un miroir + tracking a faire), soit (ii) chacun recree les commits
  localement (pas pratique, pas reproductible).
- **Reinvention du patch-system au niveau git** : les commits-in-submodule
  jouent **deja** le role des patches (atomicite, rollback via revert,
  ordering), mais sans les metadonnees DEP-3 ni le flow de detection-et-act
  idempotent. On aurait les memes besoins (tracer les anomalies, detecter
  drift, etc.) mais exprimes en git log + scripts ad-hoc — perte de tout
  l'interet d'un vrai patch-system.
- **Collaboration impossible** sans (i) ci-dessus. Kill switch pour un
  projet multi-machine.

### Alternative D (non reperee en SOA) — fork-miroir hostes en interne

**Principe** : pousser un miroir du vendor sur un remote interne
(GitLab prive, Gitea, un simple bare repo), y maintenir une branche
`local-patches` avec nos commits, la puller au lieu du submodule upstream.

**Raisons du non-retenu (pour memoire)** :
- Ajoute une infrastructure de plus a maintenir (hebergement, sync avec
  upstream).
- Divergence de branche qui cumule avec le temps — on retrouve les memes
  problemes que l'alternative C une fois la sync automatique cassee.
- Le SOA n'a pas evalue cette piste — pas dans le perimetre Phase 1 —
  mais meme a froid, le cout operationnel la disqualifie pour un projet
  a volume modere.

## References

- SOA §2.2 Debian source format 3.0 (quilt) — pattern "pristine + serie +
  regeneration deterministe".
- SOA §2.5 Git-native workflows (submodule vs subtree vs git-vendor).
- SOA §4.6 pt 3 — formalisation initiale des 3 options (a)/(b)/(c).
- Design §5.3 — traduction en decision avec alternatives rejetees.
- Design §3.1 — layout `patches/` dans le super-repo (consequence de
  cette ADR).
- `docs/260418-dual-sensitivity-analysis.md` — anomalies B1-B4 et p2-*
  qui motivent l'existence du patch-system.
- Pattern Debian 3.0 quilt — `dpkg-source(1)`,
  <https://manpages.debian.org/bookworm/dpkg-dev/dpkg-source.1.en.html>
  (URL non revérifiée live en Phase 1, voir Design §6.3).
