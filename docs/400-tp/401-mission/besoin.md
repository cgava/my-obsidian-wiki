


# type d'ingestion

* pouvoir indentifier la liste d'ingestion possible
** Actuellement on a : Document ingestion, History ingestion, Data ingestion

### lien video youtube
faut-il enrichir directement la page dans _raw, avec le transcript, puis faire l'ingestion du résultat dans le wiki ? 
ou
garder uniquement la page avec le lien dasn _raw, et faire le transcript dans les références ???

### project git
Il y a déjà de la documentation dans les projets git (en md, en txt...)
Ajouter le projet en sous-module du raw permet de garder le lien, avec le hash du projet en question 
Comment différencier les perso des publis ? Les publics sont dans le s0

cf : wiki-update = update du wiki d'un projet existant, ou de son contenu, son historique


## structure

je mettrais bien le log et l'index dans le dossier _meta

# Suivre en version _raw / et vault

* initialiser des depôts pour synchroniser la données sur tel // 
* au fur et à mesure des pipes d'ajout, c'est les branches de _raw qui progressent
* au fur et à mesure qu'on prend connaissance (humain) du résultat, la branche du wiki avance



# Classification

Forcer le frontmatter, selon le type d'article (concept, entity, journal, etc, etc) -> avec mcp-obsidian
-> A quoi ça sert ???



05-status-lint : "promotion de fichier".. 

# Deploiement et evolution

Comment déployer, automatiquement, le système ?

Comment va-t-il être maintenu (il faut des tests auto) ?

Comment sera-t-il évolué (si le dépôt vient à changer), qu'est-ce qui se passe ?
Solution 1: Faire un dummy pendant les tests 
= un dépôt, avec exactement la même structure, et qu'on peut faire évoluer => donc un projet, dummy, avec la même structure, sur laquelle exécuter les tests..

Plus petit, mais suffisant pour tester les outils.

# Synchronisation multi-devices
Donc, accessible depuis le téléphone, ça serait bien 