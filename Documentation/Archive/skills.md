Les skills Unity AI Assistant peuvent etre charges depuis deux emplacements:

- projet: `Assets`
- utilisateur: `C:\Users\wafhi\AppData\Roaming\Unity\AIAssistantSkills`

Format verifie dans `com.unity.ai.assistant@2.5.0-pre.2`:

- chaque skill est un fichier `SKILL.md`
- le fichier doit commencer par un frontmatter YAML delimite par `---`
- champs supportes: `name`, `description`, `required_packages`, `tools`, `metadata`, `enabled`, `required_editor_version`
- `name` et `description` sont obligatoires
- le body du fichier est en markdown classique

Convention projet ajoutee:

- `Assets/AI/Skills/TerraformationPresetDebug/SKILL.md`
- `Assets/AI/Skills/TerraformationHydrologyDiagnosis/SKILL.md`
- `Assets/AI/Skills/TerraformationRuntimeBridgeOps/SKILL.md`