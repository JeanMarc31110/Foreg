# Standard FEWURA Windows pour tous les agents

Ce standard s'applique à tout agent Windows créé par Forge et destiné à un client ou utilisateur final.

## Règle de livraison

Une build n'est pas une release client tant que les contrôles suivants ne sont pas tous validés :

1. tests métier et techniques ;
2. compilation du vrai EXE Windows ;
3. test du vrai EXE compilé ;
4. données modifiables hors de `Program Files` ;
5. signature Authenticode de l'EXE applicatif ;
6. vérification de la signature ;
7. création du Setup contenant l'EXE signé ;
8. signature Authenticode du Setup ;
9. vérification de la signature du Setup ;
10. installation réelle du Setup sur Windows ;
11. test de l'application installée ;
12. vérification de la signature après installation ;
13. publication uniquement si toute la chaîne est verte.

## Signature

Pour une distribution directe, FEWURA doit utiliser une identité de signature publique reconnue. Azure Artifact Signing est le mécanisme CI/CD privilégié lorsque l'organisation et le produit sont éligibles.

Les builds non signés sont réservés au développement/QA. Ils ne doivent jamais être envoyés comme installateurs client.

## SmartScreen

Il est interdit de demander au client de désactiver Defender, SmartScreen ou Smart App Control. Une signature reconnue est obligatoire pour la distribution directe. La réputation SmartScreen pouvant nécessiter du temps, les produits exigeant l'absence du message dès la distribution doivent privilégier MSIX via Microsoft Store lorsque ce canal est adapté.

## Secrets

Aucun certificat privé, clé, mot de passe, secret Azure ou secret de signature ne doit être committé dans Git. Les secrets doivent être fournis par GitHub Actions Secrets ou un coffre de secrets équivalent.
