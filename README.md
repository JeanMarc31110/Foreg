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
- génération automatique d'une chaîne de release Windows client ;
- standard FEWURA Windows obligatoire pour toute release client.

## Release Windows client automatisée

Chaque nouvel agent généré par Forge contient désormais :

- `requirements-release.txt` pour PyInstaller ;
- `installer.iss` pour Inno Setup ;
- `build_release.ps1` avec la chaîne de validation complète ;
- `build_release.bat` pour lancer la release ;
- `RELEASE_WINDOWS.md` ;
- un mode `--self-test` intégré au futur EXE.

La chaîne exécute dans cet ordre :

1. création de l'environnement de build ;
2. compilation du vrai EXE Windows autonome avec PyInstaller ;
3. exécution du vrai EXE avec `--self-test` ;
4. signature Authenticode de l'EXE ;
5. vérification de sa signature ;
6. construction du Setup Inno Setup ;
7. signature et vérification du Setup ;
8. installation silencieuse du Setup dans un répertoire Windows propre de test ;
9. vérification de la signature de l'EXE installé ;
10. exécution de l'application installée avec `--self-test` ;
11. génération de `release-manifest.json` avec SHA-256 et statut `VALIDATED`.

La chaîne est **fail-closed** : si une étape échoue, la release client est bloquée.

Le PC distant reçoit uniquement le Setup signé. Il n'a besoin ni de Python, ni de pip, ni de PyInstaller, ni d'Inno Setup, ni du code source.

Les builds non signés sont réservés au développement et à la QA. Il est interdit de demander aux clients de désactiver Defender, SmartScreen ou Smart App Control. Voir `WINDOWS_RELEASE_STANDARD.md`.

## Signature

Les secrets de signature ne sont jamais committés dans Git. Le pipeline utilise soit :

- `CODE_SIGN_CERT_SHA1` pour un certificat installé dans le magasin Windows ;
- soit `CODE_SIGN_PFX_PATH` + `CODE_SIGN_PFX_PASSWORD`.

`SIGNTOOL_PATH` et `ISCC_PATH` peuvent être définis si les outils ne sont pas trouvés automatiquement.

## Contrôle continu

Le dépôt contient `.github/workflows/windows-ci.yml`, qui vérifie sur Windows la compilation Python de Forge et la génération des fichiers de release.

## Installation Windows de Forge

Option 1 — Installer utilisateur (fichier .exe)

1. Téléchargez Forge_Installer_<version>.exe depuis les releases ou artefacts CI.
2. Double-cliquez pour lancer l'installation (ou exécutez en silencieux: Forge_Installer_<version>.exe /VERYSILENT /NORESTART).

Option 2 — Déploiement silencieux (entreprise)

Utiliser les scripts fournis dans installer\:
- PowerShell (recommandé): installer\install-client-pro.ps1 -InstallerPath "C:\\path\\to\\Forge_Installer.exe" -Quiet
- Batch: installer\install-client-pro.bat Forge_Installer.exe

Construire localement (pour développeurs/QA):

1. Installer Python 3.11+, pip.
2. pip install -r requirements.txt (ou pip install pyinstaller)
3. pyinstaller --onefile --name Forge main.py
4. Installer Inno Setup et lancer ISCC sur installer\\Forge_Installer.iss pour produire le .exe

Signature (optionnelle):

Le pipeline CI peut signer l'exécutable et le setup si les secrets GitHub sont fournis (CODE_SIGN_P12 encodé base64 et CODE_SIGN_PFX_PASSWORD). Ne committez jamais de certificats dans le dépôt.

CI/CD:

La workflow .github/workflows/windows-installer.yml construit l'EXE, crée l'installateur Inno Setup et publie l'artefact. Déclencher via push sur main ou manuellement via workflow_dispatch.

Voir aussi: RELEASE_WINDOWS.md et WINDOWS_RELEASE_STANDARD.md (si présents).

## Exemple
Crée un agent spécialisé dans la gestion des factures fournisseurs d'une PME française.
Il doit recevoir des PDF, contrôler HT/TVA/TTC, détecter les doublons, classer les pièces,
préparer les écritures et demander validation humaine avant transmission ou paiement.

## Architecture
Utilisateur -> Researcher -> Architect -> Auditor -> correction -> package ZIP -> build EXE -> test -> signature -> Setup -> test installation -> validation release

## Technologie
Python, OpenAI Agents SDK, Responses API via SDK, FastAPI, Pydantic, PyInstaller, Inno Setup, Authenticode.
