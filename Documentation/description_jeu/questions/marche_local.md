# Marché local : fonctionnement

## Structure hiérarchique

Les marchés suivent la hiérarchie H3 du monde :

```
Tuile → Planète → Système stellaire → Marché global (inter-étatique, optionnel)
```

Deux tuiles connectées par une route voient leurs prix s'influencer mutuellement.

---

## Prix : offre et demande dynamique

- Les prix sont déterminés par l'offre et la demande à chaque tick
- La population locale **consomme** passivement les ressources du marché local
- L'État possède des tuiles avec des bâtiments de production (fermes, usines…) qui alimentent le marché
- Les corporations produisent et vendent sur le marché local via leurs bâtiments

### Propagation des prix
- L'impact se propage **à chaque tick** entre tuiles connectées, **atténué par la distance**
  - Exemple : pénurie sur tuile A → -50% sur A, -30% sur tuile B reliée (1 saut), -10% sur C (2 sauts)
- Sans route entre deux tuiles, aucune propagation

---

## Population et niveaux de richesse

- La population d'une tuile est distribuée en **catégories sociales** (pauvres, classes moyennes, riches, etc.)
- Chaque catégorie a des besoins différents :
  - Pauvres → nourriture, vêtements de base
  - Classes moyennes → biens manufacturés, confort
  - Riches → luxe, tourisme, voyages interplanétaires
- La richesse d'un individu **évolue dans le temps** :
  - Un ouvrier de mine (mal payé) qui trouve un poste en usine (mieux payé) voit son niveau de vie augmenter
  - Après un certain nombre de ticks à un niveau supérieur, il change de catégorie sociale
  - Une partie de la catégorie supérieure peut progresser encore vers la suivante

### Mobilité sociale et migrations
- Si une corporation construit des usines et recrute massivement, la richesse locale augmente
- En cas de manque de main-d'œuvre sur une tuile, des **migrations** peuvent se produire depuis des tuiles voisines (événement déclenché)
- Les populations peuvent se déplacer vers des tuiles plus attractives (emploi, conditions de vie)

---

## Routes commerciales

- Une route doit être **explorée puis construite**
- Processus :
  1. Un État ou une corporation lance une **expédition d'exploration** entre deux tuiles éloignées
  2. Les explorateurs trouvent un chemin — sa durée de trajet est calculée selon le terrain
     - Exemple : montagne → +10 ticks de trajet par case traversée
  3. Une fois le chemin trouvé, on peut construire la route/chemin physique
- Sans route construite, les deux tuiles ne se voient pas sur le marché

### Routes spatiales
- Fonctionnent sur le même principe mais entre planètes/systèmes
- Nécessitent probablement une infrastructure dédiée (spatioport) — à préciser

---

## Régulation des marchés

### Marché national
- Régulé par l'État via taxes et quotas
- Le niveau de corruption de l'État influence l'efficacité de cette régulation
- Une corporation peut corrompre l'État pour ignorer les taxes ou obtenir des avantages commerciaux

### Marché global (inter-étatique)
- N'existe pas par défaut — se crée via un **organisme inter-étatique**
- Formation :
  - **A)** Événement aléatoire si plusieurs États ont un niveau de relation suffisant
  - **B)** Un État ou un joueur déclenche activement une "convention internationale" (action coûteuse)
  - **C)** Les deux selon le contexte — peut aussi être initié par un agent LLM
- Les corporations peuvent tenter de **corrompre cet organisme** pour influencer les règles commerciales mondiales
- Si complètement corrompu → devient une façade au service des corporations (objectif de fin de partie possible)
