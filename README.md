# AURELIA FORGE V1

AURELIA FORGE est un méta-agent qui reçoit une mission et fabrique un agent spécialisé sous forme de package ZIP.

## Capacités
- analyse métier ;
- recherche web ;
- blueprint structuré ;
- outils, sous-agents, workflows, permissions et tests ;
- niveaux d'autonomie 0 à 4 ;
- audit automatique avec score /100 ;
- audit de code déterministe avec findings structurés et statut bloquant ;
- correction des instructions si nécessaire ;
- manifeste JSON ;
- agent Python exécutable ;
- scripts Windows de développement ;
- interface Web locale ;
- téléchargement de chaque agent généré en ZIP ;
- génération automatique d'une chaîne de release Windows client ;
- installation client volontaire depuis un lien HTTPS avec bootstrapper vérifié ;
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
11. génération de `release-manifest.json` avec version, URL HTTPS, SHA-256, taille, date, signature et statut `VALIDATED_FOR_REMOTE_WINDOWS_INSTALL`.

La chaîne est **fail-closed** : si une étape échoue, la release client est bloquée.

Le PC distant reçoit uniquement le Setup signé. Il n'a besoin ni de Python, ni de pip, ni de PyInstaller, ni d'Inno Setup, ni du code source.

Chaque package contient aussi `install_from_link.ps1`, `CLIENT_README.md` et `CLIENT_MESSAGE_TEMPLATE.md`. Le client doit cliquer volontairement et le bootstrapper ouvre le Setup avec l'UI normale après vérification du SHA-256 et d'Authenticode. Aucune installation silencieuse, distante ou non consentie n'est fournie. Une publication de lien reste bloquée jusqu'au statut `VALIDATED_FOR_REMOTE_WINDOWS_INSTALL`.

Les builds non signés sont réservés au développement et à la QA. Il est interdit de demander aux clients de désactiver Defender, SmartScreen ou Smart App Control. Voir `WINDOWS_RELEASE_STANDARD.md`.

## Signature

Les secrets de signature ne sont jamais committés dans Git. Le pipeline utilise soit :

- `CODE_SIGN_CERT_SHA1` pour un certificat installé dans le magasin Windows ;
- soit `CODE_SIGN_PFX_PATH` + `CODE_SIGN_PFX_PASSWORD`.

`SIGNTOOL_PATH` et `ISCC_PATH` peuvent être définis si les outils ne sont pas trouvés automatiquement.

## Contrôle continu

Le dépôt contient `.github/workflows/windows-ci.yml`, qui vérifie sur Windows la compilation Python de Forge et la génération des fichiers de release.

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
Utilisateur -> Researcher -> Architect -> Auditor blueprint -> génération -> Auditor code -> tests/self-test/smoke-test -> package ZIP -> build EXE -> test -> signature -> Setup -> test installation -> désinstallation -> validation release

## Audit de code Forge

Après génération, Forge exécute un audit local et déterministe sur le package avant de créer le ZIP. Le rapport `code-audit.json` contient, pour chaque finding, la sévérité (`critical`, `error`, `warning`, `info`), le fichier, la ligne lorsque disponible, le diagnostic, le correctif proposé et le statut bloquant.

Les contrôles couvrent la syntaxe/compilation Python, les imports et dépendances déclarées, les exceptions évidentes, les fichiers attendus, la présence de tests, les secrets potentiels, les dépendances non épinglées ou sensibles, les chemins Windows, les accès fichiers/SQLite, `subprocess` et le réseau. Les tests disponibles, le self-test `agent.py --self-test` et le `smoke_test.py` lorsqu’ils existent sont exécutés. Un finding critique, un test échoué ou un self-test échoué bloque la matérialisation.

Le rapport de code est conservé dans le package et retourné par l’API `/api/build`. Il complète l’audit de blueprint produit par Auditor ; les blueprints historiques restent acceptés, mais toute release doit passer l’audit de code du package réellement généré.

## Technologie
Python, OpenAI Agents SDK, Responses API via SDK, FastAPI, Pydantic, PyInstaller, Inno Setup, Authenticode.

