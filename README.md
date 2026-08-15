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
- scripts Windows install/start ;
- interface Web locale ;
- téléchargement de chaque agent généré en ZIP.

## Installation Windows
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
