---
name: unity-mcp
description: 'Use when interacting with the Unity Editor via MCP tools. Trigger words: create script, edit script, read script, manage scene, find asset, capture screenshot, console errors, validate C#, shader, import model, manage GameObject, profiler, packages. Covers all Unity MCP operations: scripts, scenes, assets, GameObjects, shaders, visual capture, console, menu, profiling, packages. Requires Unity Editor to be open (not necessarily in Play Mode, unless visual capture is needed).'
argument-hint: 'Describe the Unity operation: e.g. "read RuntimeDebugHttpServer.cs", "add a field to PlayerController", "capture current scene view"'
---

# Unity MCP — Terraformation

## When to Use

- Creating, reading, editing, or deleting C# scripts in `Game/Assets/Scripts/`
- Navigating or modifying the Unity scene hierarchy
- Finding assets or searching code inside the Unity project
- Capturing screenshots or multi-angle scene views
- Reading Unity console logs (errors, warnings)
- Managing shaders, materials, GameObjects
- Running editor menu actions, managing packages
- Profiling Unity runtime performance

## Preconditions

| Tool family | Requirement |
|-------------|-------------|
| Script/Asset CRUD, scene ops | Unity Editor open (any mode) |
| Visual capture (`Camera_Capture`, `SceneView_Capture*`) | Unity in Play Mode or scene loaded with camera |
| Console logs (`ReadConsole`, `GetConsoleLogs`) | Unity Editor open |

## Procedure

### Step 1 — Load project context (mandatory before create/edit)

Always call `Unity_GetUserGuidelines` before any create or edit operation.
This returns project conventions: folder structure, naming, C# style, ScriptableObject patterns, Terraformation-specific rules.
Skip only for pure read or search operations where no file is being modified.

### Step 2 — Read before write

Before creating or modifying anything, read the relevant existing state:

| Goal | Tool |
|------|------|
| Search code text | `Unity_Grep` or `Unity_FindInFile` |
| Find assets by name or type | `Unity_FindProjectAssets` |
| Read a specific script | `Unity_ManageScript(action=read, name=...)` |
| Read scene hierarchy | `Unity_ManageScene(Action=GetHierarchy)` |
| Get script SHA (conflict safety) | `Unity_GetSha(Uri=...)` |

### Step 3 — Choose the right tool by intent

| Intent | Preferred tool |
|--------|----------------|
| Create a new C# script | `Unity_CreateScript` |
| Read an existing script | `Unity_ManageScript(action=read)` |
| Apply targeted line edits | `Unity_ScriptApplyEdits` or `Unity_ApplyTextEdits` ← prefer over full rewrite |
| Full script rewrite | `Unity_ManageScript(action=update)` — only when structure changes completely |
| Delete a script | `Unity_DeleteScript` |
| Validate a script for errors | `Unity_ValidateScript` |
| Create / update a shader | `Unity_ManageShader` |
| Manage a scene (load/save/hierarchy) | `Unity_ManageScene` |
| Manage GameObjects (add/remove/modify) | `Unity_ManageGameObject` |
| Run a menu item | `Unity_ManageMenuItem` |
| Manage assets (move/import/delete) | `Unity_ManageAsset` |
| Import a 3D model | `Unity_ImportExternalModel` |
| Generate an AI asset (sprite, mesh, material) | `Unity_AssetGeneration_GenerateAsset` |
| Capture game/scene view | `Unity_Camera_Capture` |
| Capture multi-angle scene view | `Unity_SceneView_CaptureMultiAngleSceneView` |
| Read console messages | `Unity_ReadConsole` (with `Types` and `FilterText`) |
| Get console logs with stack traces | `Unity_GetConsoleLogs(includeStackTrace=true)` |
| Query packages | `Unity_PackageManager_GetData` |
| Modify packages | `Unity_PackageManager_ExecuteAction` |
| Profile performance | `Unity_Profiler_GetFrameTopTimeSam_*`, `Unity_Profiler_GetOverallGcAlloca_*`, etc. |
| Run editor command | `Unity_RunCommand` |

### Step 4 — After every script create or edit

1. Call `Unity_ValidateScript(name=..., level=standard)` — verify no syntax errors
2. Call `Unity_ReadConsole(Types=[Error], Count=10)` — confirm no new compile errors appeared
3. If the script is a known file already tracked, call `Unity_GetSha` and compare with precondition SHA

### Conflict safety rule

If patching a file that another system may have modified (e.g., generated scripts, auto-imported assets):
- Call `Unity_GetSha(Uri=...)` before applying edits
- Pass the returned SHA as `precondition_sha256` to `Unity_ManageScript` or `Unity_ApplyTextEdits`

## Known Limitations — Unity_ManageGameObject

### component_properties : types primitifs uniquement

`Unity_ManageGameObject` avec `action=modify` et `component_properties` fonctionne **uniquement pour les types primitifs** (string, bool, int, float).

**Ne fonctionne PAS** pour assigner des références composant (`TMP_InputField`, `Button`, `TextMeshProUGUI`, etc.) à un SerializeField.

Le message d'erreur est **trompeur** : `"Property 'X' not found. Did you mean: X?"` — le champ existe bien mais le type n'est pas supporté.

**Workaround** : écrire un `Editor` script `[MenuItem]` ou un `[ExecuteInEditMode]` MonoBehaviour qui câble les références en code, puis l'exécuter via `Unity_ManageMenuItem` ou `Unity_RunCommand`.

Exemple :
```csharp
// Assets/Editor/WireLoginPanel.cs
[MenuItem("Terraformation/Wire LoginPanel")]
static void WireLoginPanel() {
    var panel = GameObject.Find("LoginPanel").GetComponent<LoginPanel>();
    panel.usernameField = GameObject.Find("UsernameInput").GetComponent<TMP_InputField>();
    // ...
    UnityEditor.EditorUtility.SetDirty(panel);
    UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(panel.gameObject.scene);
}
```

### instanceIDs stale après redémarrage

Les `instanceID` renvoyés par MCP **deviennent invalides après un redémarrage Unity**. Toujours utiliser le **nom string** (`parent="Canvas"`) plutôt que l'ID numérique dans les appels inter-sessions.

## Terraformation Project Conventions

Scripts live in `Game/Assets/Scripts/`. Key folders:
- `Debug/` — runtime debug bridge (`RuntimeDebugHttpServer.cs`, `RuntimeDebugFacade.cs`)
- `Simulation/` — client-side simulation consumers
- `UI/` — HUD, debug panels (`TerraformHUD`, `DebugHydrologyPanel`)
- `Views/` — view management (`ViewManager`)
- `Generation/` — terrain gen client components (`PlanetaryHexGrid`, `PlanetTextureGenerator`)
- `Water/` — hydrology client (`WaterSystem`, `HydrologySystem`, `WaterClassificationSystem`, `RiverSystem`)
- `AI/Skills/` — local Unity AI Assistant SKILL.md files (separate skill format for the Unity AI Assistant package)

When editing `RuntimeDebugHttpServer.cs`:
- Do NOT use `FindFirstObjectByType<T>()` → use `FindAnyObjectByType<T>()` (obsolete warning)
- The bridge is on port 48621 and sets `Application.runInBackground = true` for its full lifecycle
