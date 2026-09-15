# C4 niveau 1 — le contexte

**Étape** : E45 · **Blocs servis** : 2, critères 2.2 (diagrammes C4 niveaux 1
et 2) et 2.9 (documentation d'architecture accessible) · **Suite** :
[`c4-conteneurs.md`](c4-conteneurs.md)

Ce document répond à une seule question : **à quoi sert EduMatch-IA, pour qui,
et de quoi dépend-il ?** Il se lit sans connaître le projet. L'intérieur du
système est au niveau 2 ; il n'apparaît pas ici, volontairement.

> **La règle que je me suis imposée sur ces diagrammes** : ils décrivent le
> dépôt tel qu'il est aujourd'hui, pas une cible. Tout élément non construit
> porte la mention `(prévu)` dans son libellé — pas seulement une couleur, pour
> qu'un lecteur en noir et blanc ne s'y trompe pas. J'ai vérifié chaque brique
> dans le dépôt avant de la dessiner.

---

## Le diagramme

```mermaid
flowchart TB
    CONSEILLER["<b>Conseiller d'orientation</b><br/><i>[Personne]</i><br/>Accompagne un lycéen.<br/>Seul utilisateur direct du système :<br/>il décide, le système propose."]
    CANDIDAT["<b>Lycéen / candidat</b><br/><i>[Personne concernée]</i><br/>N'accède pas au système.<br/>Ses données servent à l'apprendre,<br/>agrégées, jamais nominatives."]
    EXPLOITANT["<b>Exploitant de la solution</b><br/><i>[Personne]</i><br/>Régénère les données, réentraîne,<br/>surveille la dérive, purge le journal."]

    SYSTEME["<b>EduMatch-IA</b><br/><i>[Système logiciel]</i><br/>Recommande des formations à un profil de candidat<br/>et explique chaque recommandation.<br/><br/>score = affinité x accessibilité x débouchés<br/>règles x modèle appris x dénombrement"]

    subgraph SOURCES["Producteurs de données publiques"]
        direction TB
        MESR["<b>Portail de données du MESR</b><br/><i>[Système externe]</i><br/>Parcoursup, 8 millésimes 2018-2025<br/>Licence Ouverte v2.0"]
        INSEE["<b>Base Sirene — INSEE</b><br/><i>[Système externe]</i><br/>Établissements, stock republié chaque mois<br/>Licence Ouverte v2.0"]
        ONISEP["<b>ONISEP — IDÉO</b><br/><i>[Système externe]</i><br/>Formations et métiers<br/><b>ODbL</b> : partage à l'identique"]
        RNCP["<b>France Compétences — RNCP</b><br/><i>[Système externe]</i><br/>Fiches de certification, RNCP vers ROME<br/>Licence Ouverte v2.0"]
        FT["<b>France Travail</b><br/><i>[Système externe]</i><br/>Table de correspondance ROME vers NAF<br/>Licence Ouverte v2.0"]
    end

    MISTRAL["<b>API de modèle de langage</b><br/><i>[Système externe — optionnel]</i><br/>Reformule la réponse de l'assistant.<br/>Sans clé : le mode extractif fonctionne<br/>seul, sans dégradation muette."]

    CONSEILLER -->|"consulte, comprend, et écarte<br/>une recommandation avec motif<br/>[HTTPS]"| SYSTEME
    SYSTEME -->|"recommandations expliquées,<br/>jamais une décision automatisée"| CONSEILLER
    CANDIDAT -.->|"est accompagné par"| CONSEILLER
    EXPLOITANT -->|"déclenche et surveille<br/>les chaînes de traitement"| SYSTEME

    SYSTEME -->|"télécharge les exports CSV<br/>[HTTPS, cadence annuelle]"| MESR
    SYSTEME -->|"résout le catalogue, puis<br/>télécharge le stock<br/>[HTTPS, cadence mensuelle]"| INSEE
    SYSTEME -->|"télécharge 4 jeux CSV<br/>[HTTPS, cadence quotidienne]"| ONISEP
    SYSTEME -->|"télécharge l'export du jour<br/>[HTTPS, cadence quotidienne]"| RNCP
    SYSTEME -->|"télécharge la table ROME/NAF<br/>[HTTPS, cadence quotidienne]"| FT
    SYSTEME -.->|"reformule un extrait<br/>[HTTPS, seulement si clé fournie]"| MISTRAL

    classDef personne fill:#f4f4f4,stroke:#333,stroke-width:1px,color:#111
    classDef systeme fill:#1168bd,stroke:#0b4884,stroke-width:2px,color:#fff
    classDef externe fill:#8a8a8a,stroke:#5c5c5c,color:#fff
    classDef optionnel fill:#d9d9d9,stroke:#5c5c5c,color:#111,stroke-dasharray: 5 3
    class CONSEILLER,CANDIDAT,EXPLOITANT personne
    class SYSTEME systeme
    class MESR,INSEE,ONISEP,RNCP,FT externe
    class MISTRAL optionnel
```

---

## Ce que le diagramme dit, et qu'il faut lire explicitement

### Le conseiller est le seul utilisateur, et c'est une décision de conformité

Le candidat n'a pas d'accès. Ce n'est pas un manque de temps : le système
produit un profilage qui porte sur des mineurs, et le règlement européen sur
l'IA impose un contrôle humain effectif (article 14) sur un usage que son
annexe III classe à haut risque — l'accès à l'éducation. Interposer un
professionnel qui peut **écarter une recommandation en motivant son écart**
est ce qui rend ce contrôle réel plutôt que déclaratif : le motif est
enregistré, il devient une trace vérifiable.

Conséquence assumée : aucune décision n'est prise par le système. Il classe et
il explique. L'article 22 du RGPD, qui encadre la décision entièrement
automatisée, n'est donc pas la base du dispositif — c'est le sens du « le
système propose » inscrit dans la boîte du conseiller.

### Cinq producteurs, pas quatre

Le projet a longtemps été présenté avec quatre sources. Il en compte cinq
aujourd'hui : **France Travail** s'est ajouté en construisant la chaîne
NAF ↔ ROME ↔ formation, parce qu'il porte la seule table publique reliant
directement un code ROME à la nomenclature NAF (ADR 0017). Le diagramme dit
cinq, parce que le dépôt en ingère cinq — un connecteur par producteur dans
`src/edumatch/ingestion/`.

### Deux régimes de licence, qui ne se confondent pas

Quatre sources sont sous Licence Ouverte v2.0. **IDÉO est sous ODbL**, qui
impose le partage à l'identique de toute base dérivée redistribuée, et une
attribution portant le producteur et la date de la donnée réutilisée. C'est la
raison pour laquelle l'assistant documentaire rattache une citation à **chaque
ligne** indexée, et non au fichier entier. La distinction est portée jusque
dans la configuration : un champ `licence` par jeu dans `configs/base.yaml`.

### Le modèle de langage est optionnel, et son absence est visible

L'assistant documentaire répond en mode extractif : recherche par similarité
sur le corpus IDÉO, restitution des passages avec leurs sources. Une clé d'API
activerait en plus une reformulation, contrainte par une instruction qui lui
interdit d'ajouter quoi que ce soit hors des extraits fournis. Sans clé, le
client de génération vaut `None` et le mode extractif s'exécute seul. Le trait
pointillé du diagramme dit exactement cela : une dépendance réelle mais
facultative, dont l'absence est un comportement documenté et testé, pas un
plantage ni un silence.

### Les cadences ne sont pas les mêmes, et l'architecture en tient compte

Parcoursup publie une campagne par an, Sirene republie son stock chaque mois,
les référentiels sont republiés chaque jour. Le système n'a donc pas une
horloge mais quatre — le détail est dans le [diagramme du
pipeline](../03-pipeline/diagramme-pipeline.md).

---

## Les décisions que ce diagramme matérialise

| Ce que le diagramme montre | Décision correspondante |
|---|---|
| Le système télécharge d'abord, transforme ensuite | [ADR 0001](../adr/0001-elt-plutot-que-etl.md) — ELT plutôt qu'ETL |
| Aucune URL de fichier Sirene en configuration, seulement un identifiant de jeu | [ADR 0005](../adr/0005-resolution-dynamique-url-sirene.md) — résolution dynamique par le catalogue |
| Un export RNCP par date de publication, jamais un fichier écrasé | [ADR 0007](../adr/0007-datation-quotidienne-export-rncp.md) |
| Cinq producteurs, dont France Travail | [ADR 0017](../adr/0017-chaine-naf-rome-formation-trois-sources-manque-parcoursup-declare.md) |
| Un seul composant appris sur les trois termes du score | Détaillé au [niveau 2](c4-conteneurs.md) |

---

## Ce que ce niveau ne montre pas, volontairement

- **L'intérieur du système** : c'est l'objet du niveau 2.
- **L'hébergement** : aucune infrastructure cloud n'est déployée à ce jour. Le
  système s'exécute en conteneurs sur un poste. L'écrire ici reviendrait à
  dessiner une cible ; le niveau 2 le dit sans détour, à sa place.
- **Les rôles de gouvernance** (responsable de traitement, délégué à la
  protection des données) : ils relèvent du plan de gouvernance, pas d'un
  diagramme de contexte logiciel.

---
*Étape E45 · vérifié le 2026-09-15 contre l'état du dépôt : cinq connecteurs
d'ingestion présents dans `src/edumatch/ingestion/`, licences relevées dans
`configs/base.yaml`.*
