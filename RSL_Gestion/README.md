# RSL Gestion — version 0.2.0

Application web locale de gestion commerciale et de stock, développée pour RSL.

## Contenu livré

- Application FastAPI avec interface web responsive.
- Base SQLite locale préchargée avec les fichiers `Clients.xlsx` et `produits euro.xlsx` fournis.
- 3 885 fiches clients importées (numéros Sage conservés).
- 6 953 articles importés (les lignes sans code/désignation et doublons de code sont ignorés, sans écrasement).
- 184 fiches fournisseurs provisoires déduites des numéros fournisseurs présents dans le fichier articles.
- Recherche clients / articles, création de devis, conversion en commande, validation avec réservation, livraisons, commandes fournisseurs, réceptions et journal de mouvements.
- Impression navigateur d'un devis.

## Lancement sous Windows

1. Décompresser le dossier dans un répertoire local.
2. Les fichiers Excel sources sont fournis dans le dossier `sources`.
3. Double-cliquer sur `start_windows.bat`.
4. Ouvrir `http://127.0.0.1:8000` dans le navigateur.

Le premier lancement installe les dépendances et initialise la base. Le lancement suivant réutilise la base existante.

## Lancement sous Linux

Depuis ce dossier : `./start_linux.sh`, puis ouvrir `http://127.0.0.1:8000`.

## Données et sauvegarde

La base se trouve dans `data/rsl_gestion.db`. Arrêter l'application avant de copier ce fichier pour une sauvegarde simple. Prévoir une sauvegarde quotidienne sur un support distinct.

## Limites importantes de cette version

Cette version est un **prototype fonctionnel de démarrage**, pas encore une version de production. Elle ne comporte pas encore d'authentification multi-utilisateur, de gestion des rôles, de chiffrement des sauvegardes, de validation de TVA/numérotation personnalisée, de documents PDF RSL finalisés, ni de connecteur Sage. Ne pas l'exposer sur Internet ou sur un réseau partagé avant sécurisation et recette.

Les fournisseurs issus de la colonne `N°Fournisseur` sont provisoires (`Fournisseur 1`, etc.) car le fichier articles ne contient pas leurs coordonnées ni leurs raisons sociales. Les relations article/fournisseur sont multiples : une association et ses références/prix sont mémorisés lors de la création d'une commande fournisseur. L'export fournisseurs Sage sera nécessaire pour fiabiliser ces fiches.

Les données manquantes du fichier articles ne sont pas inventées. En particulier, les stocks absents restent vides et les valeurs d'origine sont importées telles quelles lorsqu'elles sont disponibles. Vérifier les stocks et tarifs avant utilisation réelle.

## Architecture

- Python / FastAPI
- SQLite pour le démarrage local (migration PostgreSQL recommandée avant déploiement multi-postes)
- HTML/CSS/JavaScript

## API de santé

`GET /health` renvoie l'état de l'application.


## Module Fournisseurs (version 0.2.0)

Le menu **Fournisseurs** permet désormais de :
- créer et modifier une fiche fournisseur ;
- conserver le numéro fournisseur Sage ;
- saisir raison sociale, famille, contact, adresses, téléphone, e-mail, SIRET, TVA et notes ;
- importer un fichier Excel (.xlsx/.xlsm) ou CSV avec reconnaissance des en-têtes usuels français ;
- mettre à jour une fiche existante lorsqu'un numéro fournisseur Sage identique est trouvé ;
- réutiliser les fournisseurs dans le module Achats.

Les fournisseurs créés provisoirement à partir de la colonne `N°Fournisseur` des articles sont conservés. Un import avec le même numéro enrichit leur fiche au lieu de créer un doublon.

**Colonnes minimales d'import :** `N° Fournisseur` (facultatif) et `Raison Sociale` (obligatoire). Les autres colonnes reconnues sont facultatives.
