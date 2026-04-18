# SimulationCore

Ce dossier est la destination du coeur métier partagé hors Unity.

## Rôle cible

- structures d'état métier
- logique de tick autoritaire
- génération et hydrologie hors moteur
- terraformation et progression
- commandes et événements partagés
- sérialisation de snapshots réutilisable par le client, le serveur et le MCP

## Pourquoi ce dossier est indispensable

Sans `SimulationCore/`, le client Unity et le serveur dédié finiraient par dupliquer les règles.

Le but est que :

- `Game/` consomme le métier
- `DedicatedServer/` exécute le métier
- `Mcp/` observe ou orchestre autour du métier

## État actuel

Un premier noyau Python partagé existe maintenant dans `SimulationCore/terraformation_sim/`.

Il contient déjà :

- les modèles de contrats partagés (`WorldState`, `RegionState`, `ProjectionState`, `ClientSnapshot`, `SimulationCommand`, `SimulationEvent`)
- les enums métier alignés sur Unity
- un runtime mémoire minimal (`InMemorySimulationRuntime`) utilisé par `DedicatedServer/`
- les définitions d'actions de terraformation exposables côté serveur (`TerraformActionDefinition`)

Ce n'est pas encore l'extraction complète du gameplay Unity, mais ce n'est plus un dossier vide ni purement documentaire.

Les prochains candidats naturels sont :

- progression d'habitabilité réellement partagée
- session de terraformation réellement partagée
- systèmes de génération qui ne dépendent pas de `MonoBehaviour`
- réduction progressive des duplications entre contrats C# et contrats Python
- bascule du client Unity vers des définitions d'actions venant du serveur autoritaire