# AURELIA FORGE V1

AURELIA FORGE est un méta-agent qui reçoit une mission et fabrique un agent spécialisé sous forme de package ZIP.

## Capacités
- analyse métier ;
- recherche web ;
- blueprint structuré ;
- outils, sous-agents, workflows, permissions et tests ;
- niveaux d'autonomie 0 à 4 ;
- audit automatique avec score /100 ;
- correction des instructions si nécessaire ;
- manifeste JSON ;
- agent Python exécutable ;
- scripts Windows de développement ;
- interface Web locale ;
- téléchargement de chaque agent généré en ZIP ;
- standard FEWURA Windows obligatoire pour toute release client.

## Standard Windows client
Forge impose désormais à tout agent Windows destiné à un utilisateur final : vrai EXE, Setup professionnel, données hors de Program Files, test du vrai EXE, installation réelle et test après installation, signature Authenticode de l'EXE et du Setup, vérification de signature et blocage de publication si la signature manque ou est invalide.

Les builds non signés sont réservés au développement et à la QA. Il est interdit de demander aux clients de désactiver Defender, SmartScreen ou Smart App Control. Voir `WINDOWS_RELEASE_STANDARD.md`.

## Installation Windows de Forge
1. Clonez ou téléchargez le dépôt.
2. Double-cliquez sur `install.bat`.
3. Ouvrez `.env`.
4. Ajoutez votre clé API OpenAI.
5. Double-cliquez sur `start.bat`.
6. L'interface s'ouvre sur `http://127.0.0.1:8765`.

## Exemple
Crée un agent spécialisé dans la gestion des factures fournisseurs d'une PME française.
Il doit recevoir des PDF, contrôler HT/TVA/TTC, détecter les doublons, classer les pièces,
préparer les écritures et demander validation humaine avant transmission ou paiement.

## Architecture
Utilisateur -> Researcher -> Architect -> Auditor -> correction -> package ZIP

## Technologie
Python, OpenAI Agents SDK, Responses API via SDK, FastAPI, Pydantic.
