---
name: unity-mcp
description: Use when interacting with Unity Editor via MCP tools: create, edit, read, or delete C# scripts; manage scene hierarchy; find assets; capture screenshots; read console logs; manage GameObjects, shaders, packages; profile performance; run editor menu actions. Trigger words: Unity script, create script, edit .cs, scene, prefab, GameHUD, console errors, shader, TMP, GameObject, Unity MCP, ValidateScript, ManageScene, ManageGameObject, ReadConsole, FindProjectAssets, Unity Editor.
---

# Unity MCP — Terraformation

## Préconditions

| Opération | Requis |
|-----------|--------|
| Scripts, Assets, Scene (lecture/écriture) | Unity Editor ouvert (n'importe quel mode) |
| Capture visuelle (`Camera_Capture`, `SceneView_Capture*`) | Unity en Play Mode ou scène avec caméra |
| Console logs | Unity Editor ouvert |

## Workflow obligatoire (create / edit)

### 1. Charger les guidelines projet
```
Unity_GetUserGuidelines
```
Toujours appeler avant toute création ou modification. Donne conventions de dossiers, naming, style C#, règles Terraformation.
Peut être omis pour les opérations purement en lecture.

### 2. Lire avant d'écrire
| Objectif | Outil |
|---------|-------|
| Chercher du texte | `Unity_Grep` ou `Unity_FindInFile` |
| Trouver un asset par nom/type | `Unity_FindProjectAssets` |
| Lire un script | `Unity_ManageScript(action=read, name=...)` |
| Lire la hiérarchie scène | `Unity_ManageScene(Action=GetHierarchy)` |
| SHA pour sécurité | `Unity_GetSha(Uri=...)` |

### 3. Choisir le bon outil

| Intention | Outil préféré |
|-----------|--------------|
| Créer un script C# | `Unity_CreateScript` |
| Lire un script | `Unity_ManageScript(action=read)` |
| Edits ciblés (lignes) | `Unity_ScriptApplyEdits` ou `Unity_ApplyTextEdits` ← **préférer** |
| Réécriture complète | `Unity_ManageScript(action=update)` — seulement si structure entière change |
| Supprimer un script | `Unity_DeleteScript` |
| Valider la syntaxe | `Unity_ValidateScript` |
| Shader | `Unity_ManageShader` |
| Scène | `Unity_ManageScene` |
| GameObject | `Unity_ManageGameObject` |
| Menu editor | `Unity_ManageMenuItem` |
| Assets (move/import/delete) | `Unity_ManageAsset` |
| Import modèle 3D | `Unity_ImportExternalModel` |
| Capture game/scene view | `Unity_Camera_Capture` |
| Vue multi-angle | `Unity_SceneView_CaptureMultiAngleSceneView` |
| Console messages | `Unity_ReadConsole(Types=[Error], Count=10)` |
| Console avec stack traces | `Unity_GetConsoleLogs(includeStackTrace=true)` |
| Packages | `Unity_PackageManager_GetData` / `ExecuteAction` |
| Profiling | `Unity_Profiler_GetFrameTopTimeSam_*` |
| Commande editor | `Unity_RunCommand` |

### 4. Après chaque create / edit script

1. `Unity_ValidateScript(name=..., level=standard)` — vérifier syntaxe
2. `Unity_ReadConsole(Types=[Error], Count=10)` — confirmer pas de nouvelles erreurs compile

## Règle de sécurité (conflits)

Si le fichier peut avoir été modifié par un autre système :
1. `Unity_GetSha(Uri=...)` **avant** l'édition
2. Passer le SHA retourné comme `precondition_sha256` à `Unity_ManageScript` ou `Unity_ApplyTextEdits`

## Limitations connues — Unity_ManageGameObject

### component_properties : types primitifs seulement

`Unity_ManageGameObject` avec `action=modify` et `component_properties` fonctionne **uniquement pour les types primitifs** : `string`, `bool`, `int`, `float`.

**Ne fonctionne PAS** pour assigner des références composant (`TMP_InputField`, `Button`, `TextMeshProUGUI`, etc. vers un `SerializeField`).

Le message d'erreur est **trompeur** : `"Property 'X' not found. Did you mean: X?"` alors que le champ existe — c'est le type qui n'est pas supporté.

**Workaround** : écrire un script Editor `[MenuItem]` qui câble les références en code, exécuter via `Unity_ManageMenuItem`.

```csharp
// Assets/Editor/WireSomething.cs
using UnityEditor;
[InitializeOnLoad]
public class WireSomething
{
    [MenuItem("Terraformation/Wire SomethingPanel")]
    static void Wire() {
        var panel = GameObject.Find("SomethingPanel").GetComponent<SomethingPanel>();
        panel.inputField = GameObject.Find("InputField").GetComponent<TMP_InputField>();
        EditorUtility.SetDirty(panel);
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(panel.gameObject.scene);
    }
}
```

### instanceIDs stale

Les `instanceID` retournés par MCP **deviennent invalides après un redémarrage Unity**.
Toujours utiliser le **nom string** (`parent="Canvas"`) plutôt que l'ID numérique.

## Structure du projet Terraformation

Scripts : `Game/Assets/Scripts/`

| Dossier | Contenu |
|---------|---------|
| `Debug/` | `RuntimeDebugHttpServer.cs`, `RuntimeDebugFacade.cs` |
| `Simulation/` | Consommateurs simulation côté client |
| `Simulation/Contracts/` | `SimulationContracts.cs` — miroirs C# des modèles Python |
| `UI/` | HUD, panneaux debug (`GameHUD.cs`, `GameHUDController.cs`) |
| `Economy/` | `BuildingData.cs` ScriptableObjects |
| `Editor/` | Scripts editor (wire-ups, helpers build-time) |

Prefabs, matériaux et textures : `Game/Assets/Resources/`
Fonts TMP : `Game/Assets/Resources/Fonts/`
USS (styles UI Toolkit) : `Game/Assets/UI/Styles/`

## Dossier Game vs terraformation

Le client Unity est dans `E:\terraformation\Game\`.
Les scripts sont dans `Game/Assets/Scripts/` (chemin relatif au workspace terraformation).
Le dossier racine du projet Unity est `Game/`.

## Erreur `FindFirstObjectByType` obsolète

Dans `RuntimeDebugHttpServer.cs` (ligne ~43) :
- Remplacer `FindFirstObjectByType<T>()` → `FindAnyObjectByType<T>()`
