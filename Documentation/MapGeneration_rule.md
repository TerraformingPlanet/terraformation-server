# Règles de Génération de Carte — Terraformation

> Ce document définit les règles physiques qui gouvernent la génération procédurale de la carte.  
> L'objectif est qu'une planète générée soit **cohérente** : les biomes et terrains doivent émerger  
> de paramètres physiques réalistes, pas d'un simple bruit aléatoire.

---

## 1. Philosophie — Paramètres → Propriétés → Biomes

La génération se fait en **3 passes** dans l'ordre suivant :

```
CelestialBodyData (paramètres du corps)
        ↓
Bruit fractal → Propriétés par hex (temp, eau, altitude, géologie)
        ↓
Règles de dérivation → Biome final
```

Les biomes ne sont **jamais assignés directement** par le bruit. Ils émergent des propriétés physiques.

---

## 2. Paramètres du Corps Céleste (`CelestialBodyData`)

Ces paramètres définissent les limites physiques de la planète entière.

| Paramètre | Type | Description |
|---|---|---|
| `baseTemperature` | float (°C) | Température moyenne à l'équateur surface |
| `atmosphereDensity` | 0–1 | Densité atmosphérique (0 = vacuum, 1 = dense) |
| `waterAbundance` | 0–1 | Quantité totale d'eau disponible sur la planète |
| `geologicalActivity` | 0–1 | Activité volcanique/géothermique |
| `mineralRichness` | 0–1 | Richesse minérale globale |
| `solarIntensity` | 0–1 | Énergie solaire reçue (distance étoile) |
| `toxicAtmosphere` | bool | L'atmosphère contient des toxines (Mars-like) |
| `magneticField` | bool | Protège des radiations (influence habitabilité) |

### Valeurs par type de corps

| CelestialBodyType | Temp (°C) | AtmoDensity | WaterAbundance | GeologicalActivity |
|---|---|---|---|---|
| Rocky (Mars-like) | -60 à +20 | 0.0–0.2 | 0.0–0.1 | 0.1–0.3 |
| Desert | +20 à +80 | 0.1–0.4 | 0.0–0.05 | 0.0–0.2 |
| IcyMoon | -200 à -80 | 0.0–0.1 | 0.3–0.8 (glace) | 0.0–0.5 |
| OceanWorld | -10 à +40 | 0.4–0.8 | 0.6–1.0 | 0.1–0.4 |
| Volcanic | +80 à +400 | 0.3–0.9 | 0.0–0.2 | 0.7–1.0 |
| GasGiant | — | 1.0 | — | — |

---

## 3. Propriétés par Hex (calculées à la génération)

Chaque hex possède des propriétés dérivées du bruit fractal + paramètres du corps.

### 3.1 Altitude (0–1)
- **Source** : bruit de hauteur fractal (fBm)
- Rôle : détermine si l'eau s'accumule (bas) ou s'écoule (haut)
- Influence : `-6°C par tranche de 0.1 altitude` sur la température locale

### 3.2 Température locale
```
tempLocale = baseTemperature
           + altitudePenalty(altitude)          // -60°C max en hauteur
           + latitudePenalty(row)               // pôles plus froids
           + atmosphereBonus(atmosphereDensity) // effet de serre
           + geologicalBonus(geologicalActivity) // chaleur géothermique
```

### 3.3 Ratio d'eau (0–1)
```
ratioEau = waterAbundance
         × biomeNoise                      // variation locale
         × atmosphereDensity              // eau se maintient mieux avec atmo
         × f(tempLocale)                  // freeze factor si T < -20°C
```
- Si `T < -20°C` : l'eau reste mais sous forme de **glace**
- Si `T > 80°C` : l'eau s'évapore, `ratioEau` réduit drastiquement
- Sur Mars (`toxicAtmosphere=true`, `atmosphereDensity < 0.1`) : `ratioEau ≈ 0` en surface

### 3.4 Taux de toxines
```
toxines = toxicAtmosphere ? geologicalNoise × atmosphereDensity : 0
```

---

## 4. Règles de Dérivation des Biomes (Surface)

### 4.1 Arbre de décision principal

```
altitude > 0.85 → ROCHE (sommet montagneux)
│
├── ratioEau > 0.7 → OCEAN (si layer = OceanFloor / Ocean)
│
├── tempLocale < -20°C
│   ├── ratioEau > 0.2 → GLACE
│   └── ratioEau ≤ 0.2 → ROCHE (désert polaire)
│
├── tempLocale < 10°C (tempéré froid)
│   ├── ratioEau > 0.5 → VÉGÉTATION (toundra)
│   └── ratioEau ≤ 0.5 → ROCHE
│
├── tempLocale entre 10°C et 50°C (tempéré chaud)
│   ├── ratioEau > 0.6 → VÉGÉTATION (forêt/prairie)
│   ├── ratioEau 0.2–0.6 → ROCHE (semi-aride)
│   └── ratioEau < 0.2 → ROCHE (aride)
│
└── tempLocale > 50°C (chaud)
    ├── ratioEau > 0.5 → VÉGÉTATION (tropical)
    ├── ratioEau 0.1–0.5 → ROCHE (désert chaud)
    └── ratioEau < 0.1 → ROCHE (désert brûlant)

Overlay (priorité haute) :
    toxines > 0.5        → ATMOSPHÈRE TOXIQUE (remplace tout)
    geologicalActivity > 0.7 ET altitude > 0.6 → ROCHE (zone volcanique)
    mineralRichness × geologicalNoise > 0.6    → MÉTAL (si roche + profondeur)
```

---

## 5. Le Cycle de l'Eau

### 5.1 Humidité et sécheresse

Un hex a un `waterRatio` dynamique qui évolue :

| waterRatio | État |
|---|---|
| 0.0 – 0.1 | Aride — sol craquelé, pas de végétation |
| 0.1 – 0.3 | Semi-aride — roche, quelques mousses |
| 0.3 – 0.6 | Normal — végétation possible |
| 0.6 – 0.8 | Humide — forêts, marécages |
| 0.8 – 1.0 | Saturé — eau de surface, rivières, lacs |

### 5.2 Formation des Rivières

Une rivière se forme si :
- `waterRatio > 0.75` **ET** altitude entre 0.4 et 0.8
- La rivière se propage vers les **hex voisins de plus basse altitude**

Événements au cours d'une rivière :
```
À chaque hex traversé :
  10% → formation d'un LAC (waterRatio = 1.0, pause de propagation)
  30% → zone humide (waterRatio voisins +0.15)
   5% → fin dans un CANYON (hex roche + chute d'altitude)

Conditions de fin :
  - atteint un hex OCEAN           → rivière terminée, continent délimité
  - atteint un hex waterRatio > 0.8 → fusion avec plan d'eau existant
  - altitude < 0.05                → transformation en LAC ou OCÉAN
```

### 5.3 Présence d'eau dans l'atmosphère

```
atmosphericMoisture = waterAbundance × atmosphereDensity × f(tempLocale)
```

- **Mars** : `atmosphereDensity = 0.01`, `waterAbundance = 0.05` → `≈ 0` (pas de pluie)
- **Terre-like** : `atmosphereDensity = 0.8`, `waterAbundance = 0.6` → pluie, rivières actives
- **Monde Océan** : `atmosphereDensity = 0.5`, `waterAbundance = 0.9` → averse côtière permanente

Conséquences sur les voisins :
- Si `atmosphericMoisture > 0.4` → hexes adjacents aux cours d'eau : `waterRatio +0.05` par tick
- Si `atmosphericMoisture < 0.1` → rivières s'assèchent sans source

---

## 6. Composition Atmosphérique

La composition de l'atmosphère est définie **au niveau du corps céleste** et influence directement la respirabilité, la toxicité et la terraformation possible.

### 6.1 Paramètres de composition (`AtmosphericComposition`)

| Gaz | Symbole | Rôle en jeu |
|---|---|---|
| Azote | N₂ | Gaz tampon, neutre. Base d'une atmo respirable |
| Oxygène | O₂ | Requis pour respiration et végétation sans infra |
| CO₂ | CO₂ | Effet de serre → augmente `tempLocale`. Utile pour terraformer |
| Méthane | CH₄ | Effet de serre fort. Toxique. Source d'énergie potentielle |
| Gaz toxiques | toxinRatio | Proportion de composés nocifs (SO₂, NH₃…) |

Stockés comme ratios 0–1 dont la somme ≈ 1 (normalisation approximative).

### 6.2 Composition par type de corps

| CelestialBodyType | N₂ | O₂ | CO₂ | CH₄ | toxinRatio |
|---|---|---|---|---|---|
| Rocky (Mars-like) | 0.02 | 0.00 | 0.95 | 0.00 | 0.10 |
| Desert | 0.70 | 0.00 | 0.25 | 0.00 | 0.05 |
| IcyMoon | 0.90 | 0.00 | 0.05 | 0.05 | 0.00 |
| OceanWorld | 0.75 | 0.20 | 0.03 | 0.00 | 0.02 |
| Volcanic | 0.10 | 0.00 | 0.40 | 0.10 | 0.60 |
| Terre-like (cible) | 0.78 | 0.21 | 0.01 | 0.00 | 0.00 |

### 6.3 Effets sur la génération / le gameplay

```
O₂ < 0.05   → Végétation impossible sans serre pressurisée
CO₂ > 0.50  → tempLocale +20°C (effet de serre additionnel)
CH₄ > 0.10  → tempLocale +15°C + risque d'explosion si point chaud
toxinRatio > 0.30 → biome ATMOSPHÈRE TOXIQUE forcé sur les hexes exposés
```

### 6.4 Terraformation atmosphérique

L'objectif d'une corpo peut être de modifier progressivement la composition :
- **Planter** → `O₂ += 0.001` par tick (à l'échelle globale si assez de végétation)
- **Brûler méthane** → `CH₄ -= X`, `CO₂ += X/2` (moins toxique, plus chaud)
- **Neutraliseurs chimiques** → `toxinRatio -= X` (coûteux en ressources)

---

## 7. Composition des Sols (`SoilProfile`)

Chaque hex de surface possède un profil de sol calculé à la génération.

### 7.1 Propriétés du sol par hex

| Propriété | Type | Description |
|---|---|---|
| `rockHardness` | 0–1 | Dureté du substrat (0 = sable/sédiment, 1 = roche massive) |
| `organicContent` | 0–1 | Matière organique présente (nécessaire pour végétation avancée) |
| `porosity` | 0–1 | Capacité à retenir l'eau (sable = haute, roche = basse) |
| `mineralDensity` | 0–1 | Concentration en minéraux extractibles |
| `toxicSoil` | bool | Sol contaminé (retarde ou empêche certaines constructions) |
| `thermalConductivity` | 0–1 | Transmets la chaleur (géothermie) ou isole (glace) |

### 7.2 Dérivation depuis les paramètres

```
rockHardness     = 1 - porosity_noise × (1 - geologicalActivity)
organicContent   = 0  si terraformation nulle
                   (augmente progressivement avec biome Végétation voisin)
porosity         = f(biomeNoise) — sable/alluvion si bas, roche si haut
mineralDensity   = mineralRichness × (geologicalNoise + 0.2)   clampé 0–1
toxicSoil        = toxicAtmosphere ET toxinRatio > 0.4
thermalConductivity = geologicalActivity × 0.7 + f(altitude)
```

### 7.3 Influence sur le gameplay

| Propriété | Seuil | Effet |
|---|---|---|
| `rockHardness > 0.8` | Construction | Coût de défrichage +50% |
| `porosity > 0.6` | Irrigation | Eau perdue (irrigation coûte +30%) |
| `porosity < 0.2` | Irrigation | Sol imperméable → ruissellement vers hex voisins bas |
| `organicContent > 0.3` | Végétation | Boost de production O₂ +20% |
| `organicContent < 0.05` | Végétation | Impossible sans serre avec substrat artificiel |
| `toxicSoil = true` | Construction | Dépollution obligatoire avant toute construction |
| `thermalConductivity > 0.6` | Géothermie | Centrale géothermique rentable |
| `mineralDensity > 0.7` | Mine | Rendement minier x2 |

### 7.4 Évolution du sol

Le sol évolue pendant la partie :
- **Végétation active** → `organicContent += 0.001/tick` (pédogenèse lente)
- **Déforestation / Évènement acide** → `organicContent -= 0.005/tick`
- **Irrigation prolongée** (waterRatio > 0.8 sur 10 ticks) → `porosity` tend vers 0.4 (lessivage)
- **Terraformation géothermique** → `thermalConductivity` augmente

---

## 8. Vents et Position sur la Planète

La portion de planète représentée par la carte est localisée par des **coordonnées planétaires**. Cette position détermine les patrons de vent dominants.

### 8.1 Paramètres de localisation (`MapRegion`)

Ajoutés à `MapGenParameters` :

| Paramètre | Type | Description |
|---|---|---|
| `latitude` | 0–1 | 0 = pôle sud, 0.5 = équateur, 1 = pôle nord |
| `longitude` | 0–1 | Position est-ouest sur la planète |
| `tidallyLocked` | bool | Corps en rotation synchrone (une face toujours vers l'étoile) |
| `rotationSpeed` | 0–1 | Vitesse de rotation (affecte la force de Coriolis) |
| `axialTilt` | float (°) | Inclinaison axiale (saisons si > 10°) |

### 8.2 Zones de vent par latitude

Sur une planète avec rotation normale :

```
latitude 0.0–0.2 (pôle sud)
  → Vents polaires EST (faibles, froids)
  → Tempêtes de poussière fréquentes si sol sec

latitude 0.2–0.3 (subpolaire)
  → Vents d'ouest dominants (dépressions fréquentes)

latitude 0.3–0.45 (tempéré)
  → Vents d'ouest forts (vent dominant : Ouest→Est)
  → Ombre pluviométrique à l'EST des reliefs

latitude 0.45–0.55 (équateur ±5°)
  → Alizés convergents (ITCZ — Inter-Tropical Convergence Zone)
  → Calmes équatoriaux + orages convectifs
  → Précipitations maximales si waterAbundance/atmosphereDensity élevés

latitude 0.55–0.8 (tempéré nord)
  → Vents d'ouest (symétrique tempéré sud)

latitude 0.8–1.0 (pôle nord)
  → Vents polaires EST
```

### 8.3 Corps en rotation synchrone (`tidallyLocked = true`)

```
longitude 0.4–0.6 (face jour)
  → Tempêtes convectives permanentes (thermique intense)
  → Vent centrifuge depuis point subsolaire vers les bords
  → Température +30 à +80°C vs moyenne

longitude 0.0–0.2 / 0.8–1.0 (zone crépusculaire)
  → Vents violents Est-Ouest (différentiel thermique maximal)
  → Zone habitable optimale (ni trop chaud ni trop froid)

longitude < 0.15 ou > 0.85 (face nuit)
  → Froid extrême (-100°C ou pire)
  → Atmosphère peut se condenser / geler sur ce côté
  → Vent entrant (aspiration depuis face jour)
```

### 8.4 Effets des vents sur les hexes

**Ombre pluviométrique** (rainshadow) :
```
Si altitude > 0.65 ET vent dominant arrive de l'ouest :
  hexes à l'EST de la montagne : waterRatio × 0.5 (sec)
  hexes à l'OUEST de la montagne : waterRatio × 1.3 (pluvieux)
```

**Transport de matières** :
```
windSpeed × (1 - porosity) > 0.5 → érosion éolienne
  → mineralDensity des hexes sous le vent +0.05 (dépôt)
  → mineralDensity des hexes sources -0.03
  
Si toxinRatio > 0.3 ET windSpeed > 0.5 → propagation toxique
  → toxicSoil peut s'étendre aux hexes voisins sous le vent
```

**`windSpeed` par hex** :
```
windSpeed = baseWindSpeed(latitude)
          × (1 + altitude × 0.8)        // plus fort en hauteur
          × (1 - terrainRoughness × 0.4) // atténué par relief densément vallonné
```

### 8.5 Valeurs indicatives de `baseWindSpeed` par latitude

| Zone | baseWindSpeed (0–1) |
|---|---|
| Équateur (0.45–0.55) | 0.2 (alizés doux) ou 0.9 (ITCZ orageux) |
| Tempéré (0.3–0.45 / 0.55–0.7) | 0.5–0.7 |
| Subpolaire (0.2–0.3 / 0.7–0.8) | 0.7–0.9 |
| Polaire (0.0–0.2 / 0.8–1.0) | 0.3–0.5 (polaire calme) |
| Face nuit (tidallyLocked) | 0.6–1.0 (aspiration thermique) |
| Point subsolaire (tidallyLocked) | 0.8–1.0 (convection intense) |

---

## 9. Sous-sol (`Underground`)

Les règles souterraines sont indépendantes de la surface.

```
geologicalNoise > 0.7          → MÉTAL (filons riches)
geologicalNoise 0.4–0.7        → ROCHE + mineralRichness influence le type
altitude souterraine < 0.2     → cavernes possibles (waterRatio élevé = lac souterrain)
geologicalActivity > 0.6       → géothermie (chaleur → bonus énergie)
```

---

## 10. Couches (`WorldLayer`) et leurs contraintes

| Layer | Règles spécifiques |
|---|---|
| Underground | Roche, Métal dominant. Pas de végétation. Eau = rivières souterraines |
| OceanFloor | Toujours Eau ou Roche. Jamais Végétation. Métal possible (nœuds polymétalliques) |
| Ocean | Toujours Eau. Profondeur variable |
| Surface | Toutes les règles ci-dessus s'appliquent |
| Atmosphere | Roche absente. Glace rare (altitude extrême). Toxines ou Atmo saine |
| Space | Roche (astéroïdes), Métal, Vide |

---

## 11. Influence de la Terraformation sur la Génération

Les actions de terraformation **modifient les propriétés physiques** → les règles ci-dessus recalculent le biome :

| Action | Propriété modifiée | Changement de biome possible |
|---|---|---|
| Chauffer l'atmosphère | `tempLocale +X°C` | Glace → Eau ou Roche selon waterRatio |
| Irriguer | `waterRatio +X` | Roche aride → Végétation |
| Planter | `atmosphericMoisture +X` | Voisins gagnent de l'humidité |
| Neutraliser toxines | `toxines -X` | Atmo toxique → Roche ou Végétation |
| Bomber géothermique | `geologicalActivity +X` | Roche → Métal ou Volcanique |

---

## 12. Paramètres de Bruit (`MapGenParameters`)

| Paramètre | Rôle |
|---|---|
| `seed` | Graine de génération reproductible |
| `heightScale` | Fréquence du bruit de hauteur (relief plus ou moins plat) |
| `biomeScale` | Fréquence du bruit biome (zones plus ou moins grandes) |
| `octaves` | Nombre de passes fractales (détail) |
| `persistence` | Amplitude décroissante par octave |
| `lacunarity` | Fréquence croissante par octave |
| `waterLevel` | Seuil d'altitude sous lequel → zone aquatique |
| `mountainLevel` | Seuil d'altitude au-dessus duquel → roche montagne |

---

## 13. Checklist de Cohérence (validation post-génération)

- [ ] Un hex `OceanFloor` ne peut pas avoir le biome `Végétation`
- [ ] Un hex avec `ratioEau > 0.8` ET `tempLocale > -20°C` → toujours `Eau` ou `Végétation`
- [ ] Pas de rivière sur un corps avec `waterAbundance < 0.05`
- [ ] Pas de `Végétation` si `toxines > 0.5` ET `organicContent < 0.05`
- [ ] Les hexes `Métal` sont plus fréquents dans `Underground` que `Surface`
- [ ] La proportion de biomes sur `Surface` respecte les `maxHeight` de la `CelestialBodyData`
- [ ] Pas de végétation si `oxygenRatio < 0.05` (sans infrastructure)
- [ ] Ombre pluviométrique active : hexes sous le vent d'altitude > 0.7 → `waterRatio` réduit
- [ ] Corps tidally locked : `latitude ≈ 0.5` → glace permanente côté nuit

---

## 14. Architecture C# — Modèle Objet

> Ce chapitre est la **référence de conception** avant d'implémenter quoi que ce soit.  
> Règle absolue : les couches ne doivent pas se mélanger.

---

### 14.0 — Vue d'ensemble : 4 niveaux

```
┌─────────────────────────────────────────────────────┐
│  NIVEAU 0 — SYSTÈME SOLAIRE                         │
│  SolarSystemData (ScriptableObject)                 │
│  StarData (struct)                                  │
│  OrbitalSlot[] → corps + paramètres orbitaux        │
│  → solarIntensity calculé par loi inverse du carré  │
│  → transit entre corps = gameplay de colonisation   │
├─────────────────────────────────────────────────────┤
│  NIVEAU 1 — CORPS CÉLESTE                           │
│  CelestialBodyData (ScriptableObject)               │
│  → données permanentes, éditables dans l'Inspector  │
│  → solarIntensity dérivé de l'orbite (non manuelle) │
├─────────────────────────────────────────────────────┤
│  NIVEAU 2 — RÉGION / CARTE                          │
│  MapRegion (ScriptableObject)                       │
│  → où la carte se situe sur la planète              │
│  PlanetaryWeatherState (classe runtime)             │
│  → météo déduite de la planète + région             │
├─────────────────────────────────────────────────────┤
│  NIVEAU 3 — HEX                                     │
│  HexCell (classe runtime)                           │
│  HexPhysicalState (struct runtime)                  │
│  SoilProfile (struct runtime)                       │
│  → état physique calculé hex par hex à la génération│
└─────────────────────────────────────────────────────┘
```

---

### 14.1 Niveau 0 — `SolarSystemData` + `StarData` + `OrbitalParameters`

#### L'étoile — `StarData`

La classe des étoiles (spectrale) détermine la luminosité et la zone habitable du système.

```csharp
public enum StarType { M, K, G, F, A, Neutron, Binary }

[Serializable]
public struct StarData
{
    public string name;                   // ex: "Kepler-442"
    public StarType spectralType;         // M = naine rouge, G = type solaire, F = chaude

    [Range(0.001f, 20f)]
    public float luminosity;              // relative au Soleil (1.0 = Soleil, 0.3 = K-type)

    [Range(0.1f, 10f)]
    public float mass;                    // masses solaires (influe sur locked tidally)

    // Zone habitable calculée depuis la luminosité :
    // habitableZoneMin ≈ sqrt(luminosity / 1.1)  AU
    // habitableZoneMax ≈ sqrt(luminosity / 0.53) AU
    public float habitableZoneMin;        // AU
    public float habitableZoneMax;        // AU
}
```

| StarType | Luminosité | Zone habitable | Remarque |
|---|---|---|---|
| M (naine rouge) | 0.001–0.08 | 0.03–0.25 AU | Corps souvent tidally locked |
| K | 0.08–0.6 | 0.25–0.7 AU | Stable, longévité max |
| G (type Soleil) | 0.6–1.5 | 0.7–1.4 AU | Référence |
| F | 1.5–5.0 | 1.4–2.5 AU | Vie courte, UV intense |
| A | 5–25 | 2.5–8 AU | Rayonnement fort, peu propice |

#### Paramètres orbitaux — `OrbitalParameters`

```csharp
[Serializable]
public struct OrbitalParameters
{
    [Tooltip("Demi-grand axe en Unités Astronomiques (1.0 = Terre-Soleil)")]
    public float semiMajorAxis;          // AU — détermine solarIntensity

    [Range(0f, 0.95f)]
    [Tooltip("0 = orbite circulaire, 0.9 = très elliptique (comète)")]
    public float eccentricity;           // ex: Terre = 0.017, Mars = 0.093

    public float orbitalPeriodDays;      // jours terrestres par orbite complète

    [Range(0f, 180f)]
    public float orbitalInclination;     // ° par rapport au plan écliptique

    [Range(0f, 1f)]
    [Tooltip("Position actuelle sur l'orbite — 0 = périhélie, 0.5 = aphélie")]
    public float currentOrbitalPosition;

    // --- Propriétés calculées (ne pas assigner manuellement) ---
    // solarIntensity = star.luminosity / (semiMajorAxis²)  — loi inverse du carré
    // tidallyLocked  = semiMajorAxis < TidalLockThreshold(star.mass)
}
```

**Loi inverse du carré :**
```
solarIntensity = star.luminosity / (semiMajorAxis × semiMajorAxis)

Exemples :
  Terre   (G, 1.0 AU)  → 1.0 / 1.0²  = 1.00  (référence)
  Mars    (G, 1.52 AU) → 1.0 / 2.31  = 0.43
  Vénus   (G, 0.72 AU) → 1.0 / 0.52  = 1.92
  Kepler-442b (K, 0.41 AU, lum=0.21) → 0.21 / 0.168 ≈ 1.25 (zone habitable)
```

**Seuil de verrouillage tidal :**
```
tidallyLocked ≈ true  si  semiMajorAxis < 0.5 × cbrt(star.mass)  AU
  → naine rouge M + orbite < 0.2 AU → presque toujours synchrone
  → étoile G + orbite > 0.8 AU  → libre
```

#### Le système — `SolarSystemData`

```csharp
[Serializable]
public class OrbitalSlot
{
    public CelestialBodyData body;       // la planète / lune / astéroïde
    public OrbitalParameters orbit;      // ses paramètres orbitaux
    public OrbitalSlot[]     moons;      // lunes en orbite autour de ce corps

    // État de colonisation (progression gameplay)
    public bool isDiscovered;
    public bool isColonized;
    public int  colonizationProgress;    // 0–100 %, mis à jour par TickManager
}

[CreateAssetMenu(menuName = "Terraformation/SolarSystem", fileName = "NewSolarSystem")]
public class SolarSystemData : ScriptableObject
{
    [Header("Identité")]
    public string systemName;            // ex: "Kepler-442"
    public float  distanceLY;           // années-lumière depuis la Terre (contexte narratif)

    [Header("Étoile(s)")]
    public StarData primaryStar;
    public StarData[] companionStars;    // systèmes binaires / triples (optionnel)

    [Header("Corps en orbite")]
    public OrbitalSlot[] orbitalSlots;   // triés par semiMajorAxis croissant

    // --- API ---

    /// <summary>Calcule l'intensité solaire reçue à une distance donnée.</summary>
    public float ComputeSolarIntensity(float semiMajorAxisAU)
        => primaryStar.luminosity / (semiMajorAxisAU * semiMajorAxisAU);

    /// <summary>Détermine si un corps est probablement en verrouillage tidal.</summary>
    public bool IsTidallyLocked(float semiMajorAxisAU)
        => semiMajorAxisAU < 0.5f * Mathf.Pow(primaryStar.mass, 1f / 3f);

    /// <summary>Retourne la distance orbitale actuelle (AU) en tenant compte de l'excentricité.</summary>
    public float CurrentOrbitalDistance(OrbitalParameters orbit)
    {
        float angle = orbit.currentOrbitalPosition * 2f * Mathf.PI;
        // r = a(1 - e²) / (1 + e·cos(θ))   — équation de l'orbite elliptique
        return orbit.semiMajorAxis * (1f - orbit.eccentricity * orbit.eccentricity)
               / (1f + orbit.eccentricity * Mathf.Cos(angle));
    }
}
```

#### Temps de transit entre corps (gameplay)

Le temps pour voyager entre deux corps détermine la vitesse d'expansion dans le système :

```
transitDays = 258 × sqrt(((rTarget + rOrigin) / 2)³ / star.mass)  × techSpeedMultiplier
// formule de Hohmann simplifiée, rX = semiMajorAxis en AU
// techSpeedMultiplier : réduit par la recherche (tech de propulsion)

Exemples (étoile G, techMultiplier = 1.0) :
  Terre → Mars (1.0 → 1.52 AU)  ≈ 260 jours
  Kepler interne (0.4 → 1.0 AU) ≈ 130 jours
```

L'objectif long terme est qu'une corpo qui a terraformé sa planète de départ puisse envoyer des **vaisseaux colonisateurs** vers les autres corps du système — avec un coût en ressources et un délai de transit dépendant des orbites réelles.

---

### 14.2 (ex-14.1) — `CelestialBodyData`

> Identique à la version précédente. **`solarIntensity` n'est plus saisi manuellement** — il est calculé depuis `OrbitalParameters.semiMajorAxis` via `SolarSystemData.ComputeSolarIntensity()` au moment de la génération.

---

### 14.2 Niveau 1 — `CelestialBodyData` (ScriptableObject)

---

### 14.2 Niveau 1 — `CelestialBodyData` (ScriptableObject)

Contient **toutes les constantes physiques de la planète**. Ne change pas pendant une partie (sauf terraformation globale).

```csharp
// Structs imbriqués —  [Serializable] pour l'Inspector

[Serializable]
public struct PlanetaryPhysics
{
    [Tooltip("Température moyenne à l'équateur en surface (°C)")]
    public float baseEquatorTemperature;    // ex: -60 (Mars), +15 (Terre), +300 (Volcanique)

    [Range(0f, 1f)]
    public float solarIntensity;            // énergie solaire reçue

    [Range(0f, 1f)]
    public float rotationSpeed;             // 0 = synchrone, 1 = rotation rapide (Coriolis fort)

    [Range(0f, 90f)]
    public float axialTilt;                 // inclinaison axiale (°) — > 10° = saisons

    public bool tidallyLocked;              // une face toujours vers l'étoile
}

[Serializable]
public struct AtmosphericComposition
{
    [Range(0f,1f)] public float density;       // 0 = vide, 1 = dense
    [Range(0f,1f)] public float n2Ratio;       // azote (gaz tampon, neutre)
    [Range(0f,1f)] public float o2Ratio;       // oxygène (respiration, végétation)
    [Range(0f,1f)] public float co2Ratio;      // CO₂ (effet de serre → +temp)
    [Range(0f,1f)] public float ch4Ratio;      // méthane (effet de serre fort, toxique)
    [Range(0f,1f)] public float toxinRatio;    // composés nocifs (SO₂, NH₃…)
}

[Serializable]
public struct GeologicalProfile
{
    [Range(0f,1f)] public float waterAbundance;       // eau totale sur la planète
    [Range(0f,1f)] public float geologicalActivity;   // activité volcanique/géothermique
    [Range(0f,1f)] public float mineralRichness;      // richesse minérale globale
    public bool magneticField;                         // protège des radiations
}

// Dans CelestialBodyData :
public PlanetaryPhysics    physics;
public AtmosphericComposition atmosphere;
public GeologicalProfile   geology;
```

**Règles dérivées depuis AtmosphericComposition :**
```
co2Ratio > 0.50  → tempOffset += 20°C
ch4Ratio > 0.10  → tempOffset += 15°C + risque explosion
toxinRatio > 0.30 → forcer biome ATMOSPHÈRE TOXIQUE sur hexes exposés
o2Ratio < 0.05   → végétation impossible sans infrastructure
```

---

### 14.3 Niveau 2 — `MapRegion` (ScriptableObject)

Décrit **où** se trouve la carte sur la planète. Un seul asset par partie (ou un par zone si multi-régions plus tard).

```csharp
[CreateAssetMenu(menuName = "Terraformation/MapRegion")]
public class MapRegion : ScriptableObject
{
    public CelestialBodyData planet;    // la planète hôte
    public MapGenParameters  genParams; // paramètres de bruit pour cette région

    [Header("Position planétaire")]
    [Range(0f, 1f)]
    [Tooltip("0 = pôle sud · 0.5 = équateur · 1 = pôle nord")]
    public float latitude  = 0.5f;

    [Range(0f, 1f)]
    [Tooltip("0–1 : position est-ouest (crucial pour tidallyLocked)")]
    public float longitude = 0.5f;
}
```

---

### 14.4 Niveau 2 — `PlanetaryWeatherState` (classe runtime, non-serialisée)

Calculée **une seule fois** au début de la génération à partir de `CelestialBodyData` + `MapRegion`.  
Elle fournit les **modificateurs météo** qui s'appliquent à tous les hexes de la région.

```csharp
public class PlanetaryWeatherState
{
    // Vent dominant pour cette région (direction normalisée sur le plan XZ)
    public Vector2 prevailingWindDir;

    // Force du vent de base (0–1) — multipliée par l'altitude de chaque hex
    public float   prevailingWindSpeed;

    // Précipitations potentielles (0–1), modulées par waterRatio local de chaque hex
    public float   precipitationRate;

    // Décalage de température dû à la latitude + longitude (tidallyLocked)
    public float   temperatureOffset;

    // Saison actuelle si axialTilt > 10° — modifie temperatureOffset par tick
    public float   seasonalModifier;

    /// <summary>
    /// Calcule la météo régionale depuis les données planétaires et la position.
    /// Appelé une fois au début de MapGenerator.Populate().
    /// </summary>
    public static PlanetaryWeatherState Compute(CelestialBodyData body, MapRegion region)
    {
        // Voir §8 du doc règles pour les formules lat/lon/tidallyLocked
        ...
    }
}
```

**Formules de `Compute()` (résumé depuis §8) :**
```
// Décalage de température par latitude
float latFactor = Mathf.Abs(region.latitude - 0.5f) * 2f;   // 0 = équateur, 1 = pôle
temperatureOffset = -latFactor * 80f;                         // jusqu'à -80°C aux pôles

// Cas tidallyLocked
if (body.physics.tidallyLocked)
{
    float lonFactor = Mathf.Abs(region.longitude - 0.5f) * 2f; // 0 = subsolaire, 1 = nuit
    temperatureOffset += Mathf.Lerp(+50f, -120f, lonFactor);
}

// Vent dominant depuis latitude (voir tableau §8.5)
prevailingWindDir   = ComputeWindDir(region.latitude, body.physics.tidallyLocked, ...);
prevailingWindSpeed = ComputeWindSpeed(region.latitude, body.physics.tidallyLocked, ...);

// Précipitations = eau × densité atmo
precipitationRate = body.geology.waterAbundance * body.atmosphere.density;
```

---

### 14.5 Niveau 3 — `HexPhysicalState` + `SoilProfile` (structs runtime)

Calculées **par hex** pendant la génération. Stockées dans `HexCell`.

```csharp
[Serializable]
public struct SoilProfile
{
    public float rockHardness;      // 0 = sable, 1 = roche massive
    public float organicContent;    // 0–1 (augmente avec végétation au fil du temps)
    public float porosity;          // capacité à retenir l'eau
    public float mineralDensity;    // concentration en minéraux extractibles
    public bool  toxicSoil;         // sol contaminé
    public float thermalConductivity; // géothermie ou isolation (glace)
}

[Serializable]
public struct HexPhysicalState
{
    public float      altitude;     // 0–1, issu du bruit de hauteur
    public float      tempLocale;   // °C calculée (baseTemp + offsets)
    public float      waterRatio;   // 0–1
    public float      toxinLevel;   // 0–1
    public Vector2    windVector;   // direction + magnitude sur ce hex
    public float      windSpeed;    // amplifié par altitude
    public SoilProfile soil;
}

// Dans HexCell — ajout :
public HexPhysicalState state;
```

---

### 14.6 Pipeline de génération — `MapGenerator.Populate()`

```
MapGenerator.Populate(HexCell[] cells, MapRegion region)
│
├── 1. PlanetaryWeatherState weather = PlanetaryWeatherState.Compute(region.planet, region)
│
├── 2. Pour chaque HexCell :
│   ├── a. altitude   ← FractalNoise(heightScale)
│   ├── b. tempLocale ← ComputeTemp(body.physics.baseEquatorTemperature,
│   │                               weather.temperatureOffset,
│   │                               altitude, CO₂/CH₄ offsets)
│   ├── c. waterRatio ← ComputeWater(body.geology.waterAbundance,
│   │                                weather.precipitationRate,
│   │                                biomeNoise, tempLocale)
│   ├── d. toxinLevel ← f(body.atmosphere.toxinRatio, geologicalNoise)
│   ├── e. windVector ← weather.prevailingWindDir × f(altitude)
│   ├── f. SoilProfile ← ComputeSoil(geologicalNoise, body.geology, tempLocale)
│   ├── g. cell.state ← { altitude, tempLocale, waterRatio, toxinLevel, wind, soil }
│   └── h. cell.terrain + cell.layer ← ArbreDécisionBiome(cell.state, body)
│
└── 3. Passe rivières (propagation descendante sur altitude)
    └── 4. Passe validation (checklist §13)
```

---

### 14.7 Séparation des responsabilités

| Classe / Struct | Niveau | Responsabilité unique | Qui crée |
|---|---|---|---|
| `SolarSystemData` | 0 | Contient l'étoile + tous les corps + orbites | Designer |
| `StarData` | 0 | Luminosité, masse, zone habitable | Designer |
| `OrbitalParameters` | 0 | Orbite d'un corps (axe, excentricité, période) | Designer |
| `OrbitalSlot` | 0 | Association corps ↔ orbite + état colonisation | Designer |
| `CelestialBodyData` | 1 | Constantes physiques du corps | Designer |
| `AtmosphericComposition` | 1 | Composition gazeuse | Designer |
| `GeologicalProfile` | 1 | Géologie + eau | Designer |
| `PlanetaryPhysics` | 1 | Rotation, tilt (solarIntensity = calculé) | Designer |
| `MapRegion` | 2 | Position lat/lon de la carte sur la planète | Designer |
| `MapGenParameters` | 2 | Paramètres du bruit de Perlin | Designer |
| `PlanetaryWeatherState` | 2 | Météo régionale dérivée | `MapGenerator` |
| `HexPhysicalState` | 3 | État physique local par hex | `MapGenerator` |
| `SoilProfile` | 3 | Profil de sol par hex | `MapGenerator` |
| `HexCell` | 3 | Conteneur hex (coords + état) | `HexGrid` |
| `TerrainData` | 3 | Biome (couleur, nom, règles) | Designer |
| `MapGenerator` | — | Orchestre toute la génération | appelé par `HexGrid` |

> **Règles d'évolution** :
> - Nouvelle règle de biome → modifier `MapGenerator` seulement
> - Nouveau paramètre planétaire → modifier structs dans `CelestialBodyData`
> - Nouveau type de corps → ajouter un `OrbitalSlot` dans `SolarSystemData`
> - Jamais de logique dans les ScriptableObjects
> - `solarIntensity` n'est **jamais saisi manuellement** → toujours calculé depuis l'orbite

---

## À Implémenter (prochaines étapes)

**Niveau 0 — Système Solaire**
- [ ] Créer `StarData` struct (`spectralType`, `luminosity`, `mass`, `habitableZoneMin/Max`)
- [ ] Créer `OrbitalParameters` struct (`semiMajorAxis`, `eccentricity`, `orbitalPeriodDays`, `currentOrbitalPosition`)
- [ ] Créer `OrbitalSlot` class (`body`, `orbit`, `moons[]`, `isDiscovered`, `isColonized`)
- [ ] Créer `SolarSystemData` ScriptableObject (`primaryStar`, `orbitalSlots[]`, `ComputeSolarIntensity()`, `IsTidallyLocked()`, `CurrentOrbitalDistance()`)
- [ ] Asset `Kepler-442-System.asset` : étoile K + Kepler-442b à 0.41 AU

**Niveau 1 — Corps céleste**
- [ ] Refactorer `CelestialBodyData` — supprimer `solarIntensity` manuel, ajouter structs `PlanetaryPhysics`, `AtmosphericComposition`, `GeologicalProfile`
- [ ] `solarIntensity` devient propriété calculée depuis `SolarSystemData.ComputeSolarIntensity(orbit.semiMajorAxis)`
- [ ] `tidallyLocked` devient calculé depuis `SolarSystemData.IsTidallyLocked(orbit.semiMajorAxis)`

**Niveau 2 — Région**
- [ ] Créer `MapRegion` ScriptableObject (`planet`, `genParams`, `latitude`, `longitude`)
- [ ] Créer `PlanetaryWeatherState` classe runtime avec `Compute(body, region)`
- [ ] `MapGenerator.Populate()` reçoit `MapRegion` au lieu de `CelestialBodyData` directement

**Niveau 3 — Génération hex**
- [ ] Remplacer l'assignation directe par bruit → calcul de `tempLocale` + `waterRatio` par hex
- [ ] Ajouter `HexPhysicalState` struct dans `HexCell`
- [ ] Ajouter calcul `SoilProfile` par hex
- [ ] Calculer `windVector` + `windSpeed` depuis `PlanetaryWeatherState` + altitude
- [ ] Appliquer l'ombre pluviométrique (hexes sous le vent des montagnes)
- [ ] Implémenter l'arbre de décision biome dans `MapGenerator`
- [ ] Passe de rivières post-génération (propagation descendante par altitude)
- [ ] Passe de validation post-génération (checklist §13)

