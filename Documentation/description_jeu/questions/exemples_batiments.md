# Exemples de bâtiments

## Modèle général : Entrée → Sortie → Effets

Chaque bâtiment fonctionne selon un modèle tick-based :

```
Entrées (ressources + travailleurs + énergie)
        ↓
    Bâtiment
        ↓
Sorties (ressources produites + déchets + effets)
```

---

## Exemple : Mine de charbon

### Entrées
- Pioches (fabriquées par une usine, consommées par usure)
- Travailleurs (population locale + salariés corpo)
- Énergie (-25 par tick via le réseau)

### Sorties
- Charbon
- Déchets (s'accumulent sur la tuile si non traités)

### Effets par tick
- % de chance de perte d'un ouvrier
- Épuisement progressif de la ressource charbon de la tuile
- Consommation d'énergie sur le réseau local

### Prérequis
- Travailleurs : de 0 à 100 (100% = plein rendement, 0% = bâtiment abandonné)
  - Ratio travailleurs/max décuple les entrées/sorties/effets
- Quelques bureaucrates requis pour la gestion

---

## Travailleurs

- Issus de la **population locale** de la tuile + **salariés de la corporation**
- Les salariés corpo sont considérés comme faisant partie de la population de la tuile
- Si la corpo retire ses salariés → l'État peut décider de nationaliser le bâtiment
- Si la population locale est insuffisante → la corpo peut en importer (voyage interplanétaire possible)

---

## Réseau énergétique

- Une **centrale** produit X énergie par tick
- Le réseau est **limitrophe** : il distribue l'énergie aux tuiles adjacentes
- Un segment de réseau transporte une charge maximale de X énergie — construire plusieurs segments augmente la capacité
- Étendre le réseau coûte des ressources et du temps (comme tout bâtiment)
- L'énergie est disponible sur le marché local — une corpo peut construire une centrale via contrat avec un État pour sécuriser son approvisionnement

---

## Déchets et impact écologique

- Les déchets s'accumulent sur la tuile à chaque tick
- Sans bâtiment de traitement, ils impactent négativement la faune et la flore (moteur écologique)
- Un bâtiment de traitement des déchets est nécessaire pour neutraliser cet effet

---

## Épuisement et reconversion

- Quand une ressource de tuile est épuisée, le bâtiment devient inutile
- Options :
  - **Abandonner** : le bâtiment reste comme ruine — peut générer des événements négatifs (ex : groupe armé corrompu qui s'y installe)
  - **Reconvertir** : construire un nouveau bâtiment spécialisé par-dessus (ex : mine abandonnée → silo à missiles)
- La reconversion suit le processus normal de construction (ressources + ticks)

---

## Technologies et évolution des entrées

- Les entrées d'un bâtiment peuvent évoluer avec les technologies disponibles
- Une technologie peut **améliorer** une entrée (ex : pioche en fer → dynamite = rendement +20%, risque ouvrier +%)
- Ou **remplacer** une entrée (ex : pioche → foreuse automatique = moins de travailleurs requis)
- Les upgrades ne sont **pas automatiques** : il faut appliquer la technologie bâtiment par bâtiment
  - La dynamite devra être fabriquée par une usine avant d'être utilisée comme entrée
- Cela crée des chaînes de production : usine de dynamite → mine améliorée



