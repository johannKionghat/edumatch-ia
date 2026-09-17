# Procédure d'audit RGAA — écran conseiller (E31, critère 4.18)

Le RGAA (Référentiel général d'amélioration de l'accessibilité) s'appuie
sur WCAG 2.1 niveau AA. Ce document décrit la procédure d'audit manuel, au
navigateur, qui couvre ce que la suite automatisée
(`tests/unit/test_ecran_accessibilite.py`) ne peut pas vérifier faute de
navigateur dans l'environnement d'exécution.

**Ce que la suite automatisée prouve déjà**, pour ne pas le rejouer ici :
structure sémantique du document (un seul `h1`, hiérarchie de titres sans
saut, repères uniques), chaque champ de saisie associé à un `<label>`,
zones dynamiques annoncées (`role="alert"`, `aria-live`), contraste
calculé exactement (formule WCAG) sur les couleurs déclarées dans
`style.css`, focus jamais supprimé sans remplacement visible, absence
d'`innerHTML` (donc pas de vecteur XSS par construction), syntaxe
JavaScript valide.

**Ce que seul un navigateur peut vérifier**, objet des points ci-dessous :
rendu réel des polices et du zoom, comportement d'un lecteur d'écran,
parcours clavier de bout en bout, perception effective par une personne
daltonienne, temps de réponse perçu.

Prérequis : lancer l'API (`make api`), ouvrir `http://localhost:8000/`
dans le navigateur audité.

---

## 1. Navigation clavier seule (souris débranchée)

- [ ] `Tab` depuis le haut de la page active d'abord le lien d'évitement
      (« Aller au contenu principal »), visible dès le premier `Tab`.
- [ ] `Entrée` sur le lien d'évitement déplace le focus dans `<main>`.
- [ ] L'ordre de tabulation suit l'ordre visuel du formulaire de recherche :
      identifiant conseiller, type de bac, boursier, type de formation,
      domaine, département, nombre de recommandations, bouton Rechercher.
- [ ] Chaque élément qui reçoit le focus affiche un contour visible
      (`outline` orange, 3 px) sur fond blanc et sur les boutons bleus.
- [ ] Après soumission du formulaire, le focus n'est pas perdu (il reste
      sur le bouton, ou se déplace vers un message d'erreur s'il y en a un).
- [ ] Sur une carte de recommandation, `Tab` atteint dans l'ordre : le
      bouton « Comprendre cette recommandation », les deux boutons radio
      « Retenir » / « Écarter », le champ de motif, le bouton d'enregistrement.
- [ ] Cliquer « Comprendre cette recommandation » au clavier (`Entrée`)
      déplace le focus dans le panneau d'explication (son titre reçoit le
      focus par programmation) — vérifier qu'aucun focus ne « disparaît ».
- [ ] `Entrée` sur « Fermer cette explication » referme le panneau et
      renvoie le focus sur le bouton « Comprendre » qui l'avait ouvert.
- [ ] Choisir « Écarter » sans remplir le motif, puis soumettre : le focus
      se déplace vers le champ de motif avec un message d'erreur explicite.
- [ ] Aucun piège au clavier : on peut toujours ressortir d'un composant
      par `Tab` ou `Échap`.

## 2. Lecteur d'écran (NVDA ou VoiceOver)

- [ ] Le titre de la page est annoncé à l'ouverture (« Écran conseiller —
      EduMatch-IA »).
- [ ] Le lecteur annonce les repères (« bannière », « navigation »,
      « contenu principal », « pied de page ») en mode navigation par
      repères.
- [ ] Chaque champ du formulaire est annoncé avec son étiquette complète,
      et les groupes de boutons radio annoncent leur légende (« Type de
      baccalauréat du candidat, obligatoire ») avant chaque option.
- [ ] Le texte d'aide du département (« Deux chiffres, trois pour l'outre-
      mer... ») est annoncé à la suite du champ, sans naviguer ailleurs
      (vérifie `aria-describedby`).
- [ ] Une erreur de recherche (ex. champs obligatoires manquants) est
      annoncée immédiatement, sans action supplémentaire de l'utilisateur
      (`role="alert"`, `aria-live="assertive"`).
- [ ] Le tableau de contributions (panneau « Comprendre ») est annoncé
      comme un tableau, avec ses en-têtes de colonne lus avant chaque
      cellule (« Variable », « Effet », « Contribution »).
- [ ] Le message de confirmation d'un écartement (« Décision écartée
      enregistrée... ») est annoncé sans que l'utilisateur ait à déplacer
      le focus (`role="status"`, `aria-live="polite"`).
- [ ] Le statut « Mesuré » / « Indisponible » des débouchés est lu en
      toutes lettres, pas seulement comme une pastille de couleur muette.

## 3. Zoom et redimensionnement

- [ ] Zoom navigateur à 200 % : aucun texte tronqué, aucun chevauchement,
      pas de défilement horizontal sur la largeur de la page.
- [ ] Fenêtre réduite à 320 px de large (équivalent mobile) : le
      formulaire et les cartes de recommandation restent utilisables et
      lisibles.

## 4. Perception des couleurs

- [ ] Simuler un daltonisme (outil navigateur ou extension) : les statuts
      « Mesuré » / « Indisponible » restent compréhensibles (texte, pas
      seulement la couleur du badge).
- [ ] Vérifier au pixel, avec l'outil d'inspection du navigateur, que les
      couleurs réellement rendues correspondent aux variables déclarées
      dans `style.css` (pas de surcharge oubliée d'une extension ou d'un
      thème sombre du système).

## 5. Formulaires et erreurs

- [ ] Soumettre le formulaire de recherche avec un département mal formé
      (ex. `7`) : l'erreur retournée par l'API (422) est lisible et ne
      contient aucune trace technique (chemin de fichier, nom de module).
- [ ] Soumettre un écartement sans motif : message d'erreur relié au champ
      concerné (pas seulement une bannière générique en haut de page).

---

## Verdict et traçabilité

Une fois les cinq sections cochées, consigner ici : date de l'audit,
navigateur et lecteur d'écran utilisés, version du commit auditée, et la
liste des écarts constatés avec leur sévérité. Un écart n'est clos que
lorsqu'il a été corrigé et revérifié par cette même procédure.

| Date | Commit | Navigateur / lecteur d'écran | Écarts constatés | Statut |
|---|---|---|---|---|
| — | — | — | — | Audit non encore réalisé |
