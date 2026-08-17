# Standard FEWURA Windows pour tous les agents

Ce standard s'applique à tout agent Windows créé par Forge et destiné à un client ou utilisateur final.

## Règle de livraison

Une build n'est pas une release client tant que les contrôles suivants ne sont pas tous validés :

1. audit de code Forge `code-audit.json` avec verdict `PASSED` ;
2. tests métier et techniques ;
3. compilation du vrai EXE Windows ;
4. test du vrai EXE compilé ;
5. données modifiables hors de `Program Files` ;
6. signature Authenticode de l'EXE applicatif ;
7. vérification de la signature ;
8. création du Setup contenant l'EXE signé ;
9. signature Authenticode du Setup ;
10. vérification de la signature du Setup ;
11. installation réelle du Setup sur Windows ;
12. test de l'application installée ;
13. vérification de la signature après installation ;
14. désinstallation et vérification de l'absence de l'EXE installé ;
15. publication uniquement si toute la chaîne est verte.

## Prérequis et reproductibilité client

- Python et Node doivent être embarqués dans l'EXE gelé ou ne pas être requis ; aucune installation globale d'outil de développement n'est autorisée par défaut ;
- `release-manifest.json` contient toujours `prerequisites`, avec `name`, `minimum_version`, `official_source`, `detection_method`, `sha256`, `signature` et `status` (`bundled` ou `external`) ;
- seuls les composants réellement nécessaires au profil de l'agent sont déclarés ; une liste vide signifie que le package est autonome ;
- le bootstrapper détecte les composants externes, n'installe que ceux qui manquent, ouvre leur installateur avec l'interface Windows/UAC visible et bloque en cas d'accès refusé, d'échec, de hash/signature invalide ou de redémarrage requis ;
- après les prérequis, le self-check bloque le lancement si le runtime, les ports, les écritures, `%LOCALAPPDATA%`, la base locale, le réseau ou les certificats TLS requis ne sont pas valides ;
- aucune publication de lien n'est permise si la chaîne n'a pas été reproduite sur une machine Windows propre.

## Installation depuis un lien client

Chaque agent généré reçoit `install_from_link.ps1`, `release-manifest.json`, `CLIENT_README.md` et `CLIENT_MESSAGE_TEMPLATE.md`.

- le client clique volontairement sur une URL HTTPS et lance lui-même le bootstrapper ;
- le bootstrapper télécharge le Setup, vérifie son SHA-256 et sa signature Authenticode, puis refuse toute anomalie ;
- il lance le Setup avec son interface normale : aucune option silencieuse, aucun lancement distant et aucune installation non consentie ;
- `deployment_mode=client_link` et `link_install_enabled=true` sont les valeurs standard ;
- le lien configurable reste bloqué tant que le manifeste n'a pas `release_status=VALIDATED_FOR_REMOTE_WINDOWS_INSTALL`, une URL HTTPS, une taille, une date, un SHA-256 et `authenticode_setup=VALID`.

Une mise à jour n'est recherchée que lorsque l'utilisateur lance volontairement la vérification ou que l'agent lui propose explicitement cette action.

## Signature

Pour une distribution directe, FEWURA doit utiliser une identité de signature publique reconnue. Azure Artifact Signing est le mécanisme CI/CD privilégié lorsque l'organisation et le produit sont éligibles.

Les builds non signés sont réservés au développement/QA. Ils ne doivent jamais être envoyés comme installateurs client.

## Blocage fail-closed

Un finding `critical`, un test disponible échoué, un self-test échoué, un smoke-test échoué, un EXE absent, un Setup absent, une signature invalide, une installation échouée ou une désinstallation incomplète bloque la release. Le pipeline ne doit jamais transformer un échec en statut `VALIDATED_FOR_REMOTE_WINDOWS_INSTALL`.

Pour les projets acceptés par SignPath Foundation, `.github/workflows/signpath-release.yml` est la voie de signature GitHub Actions. Les secrets SignPath doivent rester dans GitHub Actions Secrets. Le workflow doit recevoir un package agent réellement présent dans la branche et ne peut valider une release si l’audit `code-audit.json` est absent ou non `PASSED`.

## SmartScreen

Il est interdit de demander au client de désactiver Defender, SmartScreen ou Smart App Control. Une signature reconnue est obligatoire pour la distribution directe. La réputation SmartScreen pouvant nécessiter du temps, les produits exigeant l'absence du message dès la distribution doivent privilégier MSIX via Microsoft Store lorsque ce canal est adapté.

## Secrets

Aucun certificat privé, clé, mot de passe, secret Azure ou secret de signature ne doit être committé dans Git. Les secrets doivent être fournis par GitHub Actions Secrets ou un coffre de secrets équivalent.

