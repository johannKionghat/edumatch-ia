# -*- coding: utf-8 -*-
"""Génère le dossier de certification EduMatch.

Conserver ce fichier : c'est lui qui produit le .docx. Pour modifier le
dossier, éditer ce script puis l'exécuter, ne pas éditer le .docx à la main.

    python _build_dossier.py
"""
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

OUT = "Projet_Certification_KIONGHAT_Johann.docx"

d = docx.Document()
st = d.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)


def h(t, lvl=1):
    return d.add_heading(t, level=lvl)


def para(t, bold=False, italic=False, align=None):
    p = d.add_paragraph()
    r = p.add_run(t)
    r.bold, r.italic = bold, italic
    if align:
        p.alignment = align
    return p


def bullets(items):
    for i in items:
        d.add_paragraph(i, style="List Bullet")


def table(rows, header=False):
    t = d.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, v in enumerate(row):
            cells[j].text = ""
            r = cells[j].paragraphs[0].add_run(str(v))
            if header and i == 0:
                r.bold = True
    return t


def encadre(titre, lignes):
    t = d.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    c.text = ""
    c.paragraphs[0].add_run(titre).bold = True
    for l in lignes:
        c.add_paragraph(l)
    d.add_paragraph()
    return t


# =====================================================================
# EN-TÊTE
# =====================================================================
p = para("PROJET DE CERTIFICATION", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
p.runs[0].font.size = Pt(18)
para("Architecte en Intelligence Artificielle (RNCP38777, Niveau 7)",
     align=WD_ALIGN_PARAGRAPH.CENTER)
p = para("EduMatch", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
p.runs[0].font.size = Pt(22)
para("Moteur de matching explicable entre candidats et formations : chances d'admission "
     "et débouchés territoriaux", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
d.add_paragraph()

table([
    ["Nom et prénom", "KIONGHAT Johann Guewol"],
    ["Titre du projet", "EduMatch : moteur de matching explicable entre candidats et formations, "
                        "estimant les chances d'admission et les débouchés territoriaux"],
    ["Certification", "Architecte en Intelligence Artificielle - Mastère 2 (AIA02)"],
    ["Date", "Septembre 2026"],
])
d.add_paragraph()

para("Ce dossier explique le projet et justifie les choix faits, sous la forme « X plutôt que "
     "Y, parce que... ». Les chiffres cités viennent des fichiers sources et se recalculent "
     "avec les commandes indiquées.", italic=True)

d.add_page_break()

# =====================================================================
# 1. PRÉSENTATION GÉNÉRALE
# =====================================================================
h("1. Présentation générale du projet", 1)

h("1.1 Secteur et organisation", 2)
para("EduMatch est une jeune entreprise EdTech basée en Île-de-France, en phase d'amorçage "
     "(levée seed de 350 000 euros). Elle édite une plateforme d'orientation scolaire en "
     "B2B2C : les clients sont des établissements (lycées, collèges, CFA, organismes de "
     "formation), les utilisateurs finaux des élèves et des personnes en reconversion.")
para("Le cas d'usage traité ici est une seule fonctionnalité de cette plateforme : le "
     "matching entre des lycéens de terminale et les formations proposées sur Parcoursup. "
     "Le modèle est appris sur les données Parcoursup, qui ne décrivent que l'accès des "
     "lycéens à l'enseignement supérieur. Les collégiens, les étudiants et les personnes en "
     "reconversion ne sont pas concernés par ce cas d'usage.", bold=True)
para("Le secteur combine deux contraintes fortes : il s'appuie sur des données publiques "
     "(Parcoursup, Sirene, référentiels de formations et de métiers), et il est sensible, car "
     "le public compte des mineurs et un système qui influence l'accès à une formation est "
     "classé à haut risque par le règlement européen sur l'IA (annexe III, point 3). C'est ce "
     "qui rend les quatre blocs de compétences nécessaires.")

para("Le trait le plus marquant de ces données est la ségrégation par le genre. Sur la "
     "session Parcoursup 2025 (14 252 formations), 2 775 d'entre elles, soit 19,7 pour cent "
     "(hors formations sans aucun admis, sinon leur taux nul fausserait la lecture), comptent "
     "moins de 20 pour cent de femmes parmi leurs admis, et 17,9 pour cent en comptent plus de "
     "80 pour cent. Seules 21,5 pour cent se situent entre 40 et 60 pour cent. L'écart est net "
     "entre filières : médiane de féminisation à 18 pour cent en école d'ingénieur, contre "
     "86 pour cent en institut de soins infirmiers et 90 pour cent dans le travail social.")
para("Ce n'est pas un problème d'accès global : les femmes sont 56,3 pour cent des admis, "
     "toutes formations confondues, donc majoritaires. Le problème est la répartition, pas "
     "l'accès. C'est l'orientation qui est en cause, exactement ce que ce projet outille.")

para("À cela s'ajoute une inégalité selon le baccalauréat d'origine : 36,7 pour cent des "
     "vœux de bacheliers généraux ont reçu une proposition en 2025, contre 29,5 pour cent pour "
     "les technologiques et 26,9 pour cent pour les professionnels — à vœu comparable, un "
     "bachelier professionnel a un quart de chances en moins.")
para("Précision : ces taux sont par vœu, pas par candidat (un lycéen formulant dix vœux garde "
     "de bonnes chances d'obtenir au moins une proposition, c'est l'accès à chaque formation "
     "prise isolément qui est inégal), et ils sont agrégés sur l'ensemble des vœux, pas moyennés "
     "formation par formation.", italic=True)
para("Ces deux phénomènes appellent des réponses opposées. L'inégalité selon le baccalauréat, "
     "le moteur doit l'estimer et la dire honnêtement : c'est la réalité de la sélection, la "
     "cacher nuirait au candidat. La ségrégation par le genre, à l'inverse, le système ne doit "
     "jamais l'amplifier : aucune variable de genre n'entre dans le modèle, et l'audit d'équité "
     "vérifie qu'aucune variable de substitution ne la reconstitue. Mesurer l'une, neutraliser "
     "l'autre : c'est le principe de conception du projet.")
para("Source : ministère de l'Enseignement supérieur et de la Recherche, données ouvertes "
     "Parcoursup, session 2025 (Licence Ouverte Etalab v2.0). Valeurs recalculées à partir du "
     "fichier source.", italic=True)

d.add_page_break()

# ---------------------------------------------------------------------
h("1.2 Problématique métier", 2)

para("Trois causes structurelles expliquent les mauvais choix d'orientation : le manque "
     "d'information sur les formations et leurs débouchés, les déterminismes sociaux et "
     "territoriaux, et les stéréotypes de genre. Le système ne doit surtout pas les "
     "reproduire, ce qui fait de la non-discrimination et de l'explicabilité une exigence de "
     "fond, pas un habillage réglementaire.")
para("Le score de recommandation combine trois termes, dont un seul est appris :", bold=True)
table([
    ["Terme", "Question", "Source", "Nature"],
    ["Affinité", "Cela correspond-il aux centres d'intérêt du candidat ?",
     "Intérêts déclarés dans la requête", "Règles métier, aucun apprentissage"],
    ["Accessibilité", "Le candidat a-t-il une chance d'être admis ?",
     "Parcoursup, huit millésimes bruts, six exploitables pour le label (2020-2025)",
     "Modèle appris (LightGBM, tracé dans MLflow), explicabilité SHAP produite (TreeSHAP, "
     "précalculée sur 440 030 cellules) — résultat de performance défavorable en test, détaillé "
     "en section 7"],
    ["Débouchés", "La formation mène-t-elle à un emploi atteignable ?",
     "Base Sirene, référentiels métiers",
     "Agrégats de densité et de dynamique des employeurs, aucun apprentissage"],
], header=True)
para("Les trois termes se multiplient : si l'un s'annule, la recommandation disparaît. "
     "Recommander une formation accessible mais sans rapport avec les goûts, ou adaptée mais "
     "sans aucun employeur du secteur à proximité, serait une mauvaise orientation.")

para("Périmètre de la certification : le produit EduMatch comporte plusieurs fonctionnalités, "
     "la certification porte sur un seul système décisionnel.", bold=True)
table([
    ["Composant", "Rôle dans la certification"],
    ["Moteur d'orientation explicable",
     "Composant central, seul modèle industrialisé de bout en bout (blocs 1 à 4)."],
    ["Chatbot RAG (génération augmentée par récupération)",
     "Brique secondaire : restitue en langue naturelle, avec citation des sources, les "
     "éléments qui fondent une recommandation. Intégré et supervisé, pas industrialisé au "
     "même niveau."],
], header=True)
para("L'écran de supervision des conseillers n'est pas une fonctionnalité produit : c'est un "
     "composant de conformité, imposé par l'exigence de contrôle humain de l'AI Act (section "
     "7).", italic=True)

para("Le projet impose de vrais arbitrages :")
bullets([
    "Volumétrie et hétérogénéité : cinq sources publiques, de quelques mégaoctets à 43,9 "
    "millions d'établissements (section 2).",
    "Performance et fraîcheur : recommandation en temps interactif, sources mises à jour à des "
    "rythmes très différents (annuel, mensuel, continu).",
    "Budget : structure de coûts d'une startup en amorçage, à surveiller côté inférence.",
    "Conformité : données de lycéens, majoritairement mineurs (17-18 ans) ; le profilage relève de l'article 22 (base "
    "légale, consentement, minimisation, transparence, analyse d'impact) et de l'AI Act "
    "(explicabilité, non-discrimination), plus le respect des licences (section 3).",
])

h("1.3 Parties prenantes", 2)
table([
    ["Direction (3 associés)", "Stratégie produit, arbitrage valeur / coût / conformité."],
    ["Cheffe de projet agile", "Pilote le backlog et les sprints."],
    ["Architecte IA", "Conçoit l'architecture, arbitre les choix, pilote la gouvernance et la "
                      "mise en production."],
    ["DPO", "Garant RGPD : lycéens majoritairement mineurs, licéité des données publiques "
            "réutilisées."],
    ["Équipe de développement", "Met en œuvre les pipelines, le moteur et le RAG."],
    ["Conseillers d'orientation", "Superviseurs humains : revoient, contextualisent, peuvent "
                                  "écarter une recommandation."],
    ["Établissements et utilisateurs", "Pour ce cas d'usage : lycées clients et leurs "
                                       "élèves de terminale. Les autres publics de la "
                                       "plateforme sont hors périmètre."],
    ["Fournisseurs de données", "MESR (Parcoursup), INSEE (Sirene), France Compétences, "
                               "ONISEP, IDEO."],
    ["Référent accessibilité", "Conformité RGAA pour les personnes en situation de handicap."],
])

d.add_page_break()

# =====================================================================
# 2. ENVIRONNEMENT TECHNIQUE
# =====================================================================
h("2. Environnement technique existant", 1)
para("J'ai conçu et développé la première version d'EduMatch, un MVP qui valide le concept et "
     "sert de point de départ : front Next.js/React (TypeScript, Redux), back FastAPI, "
     "assistant RAG en CamemBERT, FAISS, LangChain et Mistral-small. Ces choix visaient à "
     "livrer vite, pas à tenir en production : ingestion semi-manuelle sans orchestration ni "
     "contrôle qualité, infrastructure non pensée pour la conformité ni la charge, et le "
     "moteur d'orientation n'existait pas. Ce projet reprend cette base pour la restructurer et "
     "l'industrialiser.")

para("Les sources, leur rôle et leur volumétrie.", bold=True)
para("Chaque source répond à une question précise : aucune n'est là pour la forme, aucune ne "
     "peut être retirée sans amputer une dimension de la décision.")
table([
    ["Source", "Ce qu'elle apporte", "Volumétrie vérifiée", "Licence"],
    ["Parcoursup, sessions 2018-2025 (MESR)",
     "Résultats d'admission par formation et profil. Source du label du modèle appris.",
     "104 274 formation-années, 118 colonnes (2025), 82 Mo sur 8 CSV. 77 159 cellules "
     "exploitables par millésime",
     "Licence Ouverte v2.0"],
    ["Base Sirene (INSEE)",
     "Tissu économique : activité, commune, effectifs, créations et cessations depuis 1973.",
     "43 896 818 établissements, 29 922 486 unités légales ; 6,44 Go compressés, 4,63 Go en "
     "Parquet pour les quatre fichiers retenus, stock du 1er août 2026",
     "Licence Ouverte v2.0"],
    ["Référentiels ONISEP, IDEO et RNCP",
     "Description des formations, métiers et certifications ; correspondance activité / "
     "formation.",
     "IDÉO : 5 869 formations, 1 534 métiers, 24 278 structures (15,9 Mo). RNCP et Répertoire "
     "spécifique : 30 484 fiches dont 7 000 actives (export du 29 août 2026)",
     "ONISEP et IDÉO : ODbL — partage à l'identique. RNCP : Licence Ouverte v2.0"],
], header=True)

para("Les trois dimensions (3V) sont non triviales ici :")
bullets([
    "Volume : 43,9 millions d'établissements à joindre et agréger, 25 à 30 Go décompressés, "
    "face à un référentiel d'admission d'une centaine de mégaoctets.",
    "Vélocité : publications en batch à des rythmes très différents, pour des recommandations "
    "servies en temps interactif.",
    "Variété : CSV, Parquet volumineux, API, référentiels, données déclaratives. "
    "L'hétérogénéité des nomenclatures (NAF, ROME, codes de formation) est le cœur du défi.",
])

d.add_page_break()

# =====================================================================
# 3. CONTRAINTES RÉGLEMENTAIRES
# =====================================================================
h("3. Contraintes réglementaires", 1)
bullets([
    "RGPD : l'entraînement ne mobilise aucune donnée personnelle (Parcoursup = comptages "
    "agrégés, Sirene = établissements). Les données personnelles n'interviennent qu'à "
    "l'inférence, quand un candidat renseigne bac, mention, statut de boursier, territoire et "
    "centres d'intérêt — rien de plus, par minimisation. Aucune donnée de navigation ou de "
    "comportement n'intervient.",
    "Base légale et droits : le public comptant des mineurs, la base légale est le "
    "consentement du titulaire de l'autorité parentale en dessous de quinze ans. La "
    "recommandation est une décision automatisée (article 22) : droit à l'explication, assuré "
    "par SHAP. Droits d'accès, de rectification, d'effacement et d'opposition mis en œuvre.",
    "Tension conservation / traçabilité : l'article 12 de l'AI Act impose de journaliser les "
    "inférences, le RGPD impose de limiter la conservation. Solution : une durée définie, puis "
    "pseudonymisation et agrégation des journaux. Une analyse d'impact est menée, le profilage "
    "systématique de mineurs la rendant obligatoire.",
    "Réutilisation : les jeux du ministère et de l'INSEE sont en Licence Ouverte v2.0 (usage "
    "commercial autorisé, source à mentionner). Un registre des sources et licences est tenu.",
    "AI Act : le système relève de l'annexe III, point 3 (accès à l'enseignement) : gestion des "
    "risques, gouvernance des données, documentation, journalisation, transparence, contrôle "
    "humain, exactitude et robustesse (détail bloc 1).",
    "Sécurité et souveraineté : chiffrement, moindre privilège, journalisation (ISO 27001). "
    "Hébergement européen retenu pour réduire le risque lié aux données de mineurs.",
])

d.add_page_break()

# =====================================================================
# 4. BLOC 1
# =====================================================================
h("4. Bloc 1 - Gouvernance des données", 1)
para("Ce que le projet impose : données de lycéens majoritairement mineurs, plusieurs sources publiques "
     "sous des licences différentes, plusieurs parties prenantes, une conformité AI Act non "
     "triviale.", italic=True)
para("Le plan de gouvernance est écrit et versionné : classification des données (publiques, "
     "internes, personnelles, sensibles) avec des règles d'usage, dont six sur sept sont "
     "contrôlées automatiquement plutôt que déclarées sur le papier ; rôles répartis entre un "
     "Data Owner côté direction, des Data Stewards côté équipe data et un DPO ; registre de "
     "huit traitements (T1 à T8) avec finalité, base légale, durée, destinataires, chacun avec "
     "son état réel. Origines, schémas, fraîcheurs et lignages sont documentés par le pipeline "
     "lui-même (tests de qualité, lignage dbt), sans outil de catalogage séparé.")
para("La gestion des risques couvre onze risques (R1 à R11) sur quatre familles : violation de "
     "données de mineurs, discrimination des recommandations, non-conformité de réutilisation, "
     "obsolescence des données.")
table([
    ["Article", "Obligation", "Mise en œuvre dans EduMatch"],
    ["9", "Gestion des risques", "Registre des onze risques, révisé à chaque campagne"],
    ["10", "Gouvernance des données", "Contrôles qualité automatisés, audit d'équité, "
                                      "registre des sources"],
    ["11", "Documentation technique", "Dossier technique et Model Card"],
    ["12", "Journalisation", "Traçabilité horodatée de chaque recommandation, purge par "
                             "paliers"],
    ["13", "Transparence", "Notice utilisateur — à écrire ; restitution SHAP produite"],
    ["14", "Contrôle humain", "Écran conseiller : revue, contextualisation, écartement motivé"],
    ["15", "Exactitude et robustesse", "Protocole temporel, seuils, tests. Résultat mesuré "
                                       "défavorable au modèle appris en test (section 7)"],
], header=True)
para("L'analyse d'impact, obligatoire du fait du profilage de mineurs, refait le test de "
     "nécessité une fois les mesures disponibles, pas avant. Ce test échoue sur le terme "
     "appris : une règle déjà construite, le taux de la session précédente, fait mieux que le "
     "modèle en précision et en calibration sur la session la plus récente. L'avis est donc "
     "scindé : défavorable à la restitution du terme appris à des candidats réels ; favorable "
     "sous réserves au reste du dispositif ; favorable sans réserve à l'exploitation en "
     "démonstration. Le seuil qui lèverait la réserve est écrit à l'avance : un modèle "
     "réentraîné sous 0,0701 de MAE pondérée et 0,0322 d'ECE sur une session non consultée "
     "pendant le réglage.")
para("La conformité est suivie par une procédure d'audit calée sur le calendrier Parcoursup "
     "(douze points de contrôle, trois déclencheurs), déjà appliquée trois fois. Restent à "
     "écrire : une notice d'information lisible par un mineur, et un identifiant de "
     "corrélation pour rendre purgeable le journal de supervision.")
para("À livrer : présentation devant le jury. Le reste existe : plan de gouvernance, analyse "
     "d'impact, Model Card, registre des sources. Évaluation : lecture 15 min, présentation "
     "15 min, questions 15 min.", italic=True)

d.add_page_break()

# =====================================================================
# 5. BLOC 2
# =====================================================================
h("5. Bloc 2 - Architecture de données pour l'IA", 1)
para("Ce que le projet impose : des volumétries séparées par plus de deux ordres de grandeur, "
     "une saisonnalité marquée qui impose l'élasticité, des exigences de disponibilité et de "
     "souveraineté.", italic=True)

para("Le principe structurant : deux couches distinctes.", bold=True)
para("La couche de volume traite des dizaines de gigaoctets sans donnée personnelle (Sirene). "
     "La couche de décision traite des référentiels compacts mais sensibles, et sert "
     "l'inférence. Cette séparation sert la performance et la conformité en même temps : le "
     "périmètre RGPD reste réduit, et le calcul lourd s'exécute là où le risque est nul.")

para("Modélisation : le transactionnel (utilisateurs, établissements, historique) sera porté "
     "par PostgreSQL relationnel — reste à construire. Le modèle analytique en étoile pour les "
     "données d'orientation, lui, est construit : la table de faits porte les cellules "
     "d'observation, avec pour dimensions formation, candidat, session, territoire. PostgreSQL "
     "est retenu plutôt que Firestore pour la cohérence relationnelle et les requêtes "
     "analytiques ; le modèle en étoile convient à la prédominance des lectures analytiques.")
para("Infrastructure : le service et l'entraînement sont conteneurisés (Docker, deux étapes, "
     "non-root, sonde de santé, image étiquetée par le commit) et orchestrés en local (Airflow, "
     "quatre DAG). Le code cible existe dans le second dépôt : Terraform pour un cloud "
     "souverain européen (Scaleway plutôt qu'un hyperscaler hors Union européenne, à cause des "
     "données de mineurs) et des manifestes Kubernetes complets. Rien n'est déployé à ce jour : "
     "aucun compte fournisseur ouvert, aucun apply exécuté, terraform validate lui-même n'a pas "
     "pu tourner faute de binaire installé sur mon poste. C'est le point le plus exposé du "
     "projet, je le déclare comme tel.")
para("Sécurité, en l'état : le cloisonnement réseau est réel (réseau privé Terraform, "
     "politique réseau Kubernetes restrictive, conteneurs non-root en lecture seule, aucun "
     "secret commité). Le chiffrement, lui, n'est implémenté nulle part dans le code "
     "d'infrastructure actuel, et la gestion des accès par rôle se limite au compte de service "
     "de la supervision — deux manques à traiter avant tout déploiement réel. La supervision "
     "(Prometheus, Grafana, cinq alertes) est écrite dans le second dépôt mais n'a jamais "
     "tourné, faute d'environnement.")

encadre("Justification du choix : Kubernetes managé plutôt qu'un dimensionnement fixe", [
    "Le volume seul ne justifie pas une orchestration élastique. La vraie raison est la "
    "saisonnalité : pic de janvier à mai, creux en juillet-août, rapport de charge de l'ordre "
    "de 1 à 6.",
    "Un dimensionnement fixe ferait payer toute l'année la capacité du pic, pour un taux "
    "d'utilisation moyen d'environ 30 pour cent. L'autoscaling dimensionne à la charge réelle — "
    "un enjeu de coûts direct pour une startup en amorçage.",
    "Je retiens Kubernetes managé plutôt qu'un cluster auto-géré (trop lourd à exploiter pour "
    "une petite équipe) ou le PaaS actuel (pas d'autoscaling fin). Le serverless a été écarté "
    "pour ses démarrages à froid, incompatibles avec la latence interactive attendue.",
])

para("À livrer : infrastructure déployée, chiffrement et rôles applicatifs, capture de la "
     "supervision, vidéo de l'infrastructure en production. Les diagrammes C4 et le code "
     "d'infrastructure existent déjà. Évaluation : lecture 20 min, présentation 5 min, "
     "questions 15 min.", italic=True)

d.add_page_break()

# =====================================================================
# 6. BLOC 3
# =====================================================================
h("6. Bloc 3 - Pipelines de données pour l'IA", 1)
para("Ce que le projet impose : trois sources publiques de formats et de fréquences "
     "différents, des volumétries séparées par plus de deux ordres de grandeur, la "
     "réconciliation de trois nomenclatures indépendantes.", italic=True)

para("Ingestion : trois connecteurs sur mesure, les connecteurs génériques étant inadaptés à "
     "ces sources publiques françaises.", bold=True)
table([
    ["Connecteur", "Mode d'accès", "Fréquence"],
    ["Parcoursup", "API du portail de données ouvertes, huit millésimes",
     "Annuelle, fin de campagne"],
    ["Sirene", "Catalogue data.gouv.fr, fichiers Parquet dont les adresses changent chaque "
               "mois", "Mensuelle"],
    ["Référentiels ONISEP, IDEO, RNCP", "Téléchargement versionné", "Sur publication"],
], header=True)
para("Les connecteurs sont idempotents et écrivent de façon atomique : un fichier déjà "
     "présent n'est pas retéléchargé, une interruption ne laisse jamais un fichier tronqué que "
     "le pipeline croirait complet.")

para("Transformation : deux chaînes distinctes, en cohérence avec les ordres de grandeur.",
     bold=True)
bullets([
    "Chaîne de décision, mono-nœud (Polars puis dbt) : réconciliation des huit millésimes "
    "Parcoursup, nettoyage, construction des cellules d'observation. De l'ordre de la centaine "
    "de mégaoctets.",
    "Chaîne de volume, agrégation Sirene par commune et secteur, dynamique des créations et "
    "cessations sur dix ans, élargissement au bassin d'emploi. De l'ordre de la dizaine de "
    "gigaoctets. Deux moteurs testés contre le même résultat : Polars en usage courant, "
    "PySpark branché en mode cluster.",
])
para("Le nettoyage de Sirene conditionne la faisabilité : les 43,9 millions de lignes ne sont "
     "jamais nettoyées ligne à ligne. Le format Parquet range les données par colonne ; je "
     "n'en lis que neuf sur cinquante-quatre, et le filtre (actifs, employeurs, diffusibles) "
     "s'applique dès la lecture du fichier. Le volume est réduit avant toute transformation, "
     "et les contrôles qualité portent ensuite sur des agrégats de quelques centaines de "
     "milliers de lignes, inspectables.")

encadre("Justification du choix : mesurer avant de choisir le moteur de la chaîne de volume", [
    "Quelques dizaines de milliers de formations (82 Mo sur disque) ne justifient pas un "
    "cluster distribué : la chaîne de décision reste en mono-nœud, sans débat.",
    "Pour la chaîne de volume, j'ai mesuré plutôt que décidé par principe. Sur Sirene complet "
    "(43 896 818 lignes, 54 colonnes réduites à 9), même filtre, même regroupement en "
    "1 929 179 cellules : Polars traite le fichier en 18,2 secondes, PySpark en 87,0 secondes "
    "(JVM comprise) — Spark est 4,8 fois plus lent, pour un résultat identique.",
    "Un des quatre fichiers Sirene retenus, l'historique des établissements, compte à lui seul "
    "95 865 102 lignes, republié chaque mois : une fusion future changerait d'ordre de "
    "grandeur. Le job Spark est donc implémenté, testé (même résultat que Polars) et branché en "
    "mode cluster, prêt sans réécriture. Seuil de bascule : fusion de plusieurs fichiers "
    "Sirene, ou calcul qui ne tiendrait plus en mémoire sur un poste de développement. Tant "
    "que ce seuil n'est pas franchi, Polars reste le chemin réel.",
])

para("Réconciliation des nomenclatures : le cœur de la difficulté technique. Trois "
     "nomenclatures indépendantes à mettre en correspondance.", bold=True)
table([
    ["Nomenclature", "Origine", "Rôle"],
    ["NAF", "Sirene (INSEE)", "Activité économique des établissements"],
    ["ROME", "Référentiels métiers français", "Métier"],
    ["Codes formation", "Parcoursup, RNCP, ONISEP", "Offre de formation"],
], header=True)
para("Cette table conditionne la qualité du terme de débouchés : sans elle, impossible de "
     "savoir s'il existe des employeurs du secteur en face d'une formation. Elle est "
     "construite, versionnée, testée. Sa couverture, jusqu'à la NAF, est mesurée : 61,4 % des "
     "formations ONISEP portant un code RNCP sont rattachées à une division NAF. Mais aucun "
     "des huit millésimes Parcoursup ne porte de code RNCP, NSF ou ROME : la chaîne relie "
     "ONISEP à la NAF, pas les formations Parcoursup elles-mêmes. Le seul rapprochement mesuré "
     "entre les deux, un appariement textuel des libellés, ne couvre que 7 libellés sur 712, "
     "soit 6 017 lignes sur 440 030 (1,4 %) — sept diplômes d'État très normés, relus à la "
     "main. Pour les 98,6 % restants, le terme de débouchés est marqué indisponible, jamais "
     "mis à zéro en silence.")

para("Automatisation, qualité et supervision.", bold=True)
para("Les contrôles qualité portent sur le schéma, la complétude et la cohérence (schémas "
     "Pandera pour Parcoursup, compteurs écrits à la main pour Sirene et les référentiels — "
     "Great Expectations écarté après mesure de son coût, inutile ici) : un taux hors "
     "intervalle, un effectif incohérent ou un millésime manquant bloquent la mise à jour, "
     "vérifié par une exécution réelle et un scénario de panne rejouable. Sans ce blocage, une "
     "donnée corrompue se propage jusqu'au modèle sans que personne ne le voie. La couche de "
     "volume ne contient par construction aucune donnée personnelle.")
para("Airflow orchestre la chaîne : quatre DAG, un par cadence réelle (annuelle, mensuelle, "
     "quotidienne, plus un DAG de purge), treize tâches au total. La reprise sur erreur est "
     "décidée en code plutôt que confiée au retry natif d'Airflow (désactivé) : erreur "
     "transitoire ou définitive, temporisation croissante, deux scénarios de panne rejouables. "
     "Le réentraînement et l'évaluation du modèle sont dans le graphe : le DAG annuel se "
     "termine par ces deux tâches, déclenchées après détection de dérive, derrière le même "
     "contrôle qualité bloquant. Une porte de promotion refuse de publier un modèle réentraîné "
     "qui ne bat pas strictement le plancher en test — à ce jour, elle refuse, pour la raison "
     "détaillée au bloc 4. La supervision du pipeline lui-même reste à ajouter ; les alertes "
     "écrites aujourd'hui portent sur le service d'inférence.")

para("À livrer : capture vidéo du pipeline en production, avec panne et reprise. Le diagramme "
     "et le code sont déjà sur le dépôt. Évaluation : lecture 20 min, présentation 5 min, "
     "questions 15 min.", italic=True)

d.add_page_break()

# =====================================================================
# 7. BLOC 4
# =====================================================================
h("7. Bloc 4 - Déploiement de la solution IA", 1)
para("Ce que le projet impose : une décision automatisée à fort enjeu, une explicabilité de "
     "droit et non de confort, des données sujettes à dérive, un environnement de "
     "production.", italic=True)

para("Composition du score et rôle de chaque source.", bold=True)
para("La recommandation combine trois termes. Un seul est appris ; les deux autres reposent "
     "sur des règles et des agrégats. C'est un choix d'architecte : je n'apprends que ce qui "
     "ne peut pas être établi autrement.")
table([
    ["Terme", "Question", "Source", "Nature du calcul"],
    ["Affinité", "Cela correspond-il aux centres d'intérêt du candidat ?",
     "Intérêts déclarés, référentiels de domaines",
     "Règles et pondérations métier. Aucun apprentissage, aucune donnée stockée."],
    ["Accessibilité", "Le candidat a-t-il une chance d'être admis ?",
     "Parcoursup, huit millésimes bruts, six exploitables (2020-2025)",
     "Modèle appris (LightGBM, tracé dans MLflow). Explicabilité SHAP produite, mais le "
     "modèle ne bat pas son plancher en test (détail plus bas)."],
    ["Débouchés", "La formation mène-t-elle à un emploi atteignable ?",
     "Base Sirene, référentiels métiers",
     "Agrégats de densité et de dynamique des employeurs. Aucun apprentissage."],
], header=True)
para("Les trois termes se multiplient, module testé : un terme nul supprime la recommandation, "
     "vérifié pour les trois termes séparément. Une somme pondérée ne donnerait pas cette "
     "garantie.")
para("Le terme de débouchés répond à la première cause identifiée en 1.2, le manque "
     "d'information sur les débouchés : ce n'est pas une variable ajoutée, c'est une dimension "
     "de la décision. Sa couverture réelle est faible et mesurée : 6 017 lignes sur 440 030 "
     "(1,4 %) seulement ont un appariement vérifié entre une formation Parcoursup et une "
     "activité économique, faute de code RNCP, NSF ou ROME porté par Parcoursup lui-même "
     "(section 6). Pour les autres lignes, le terme est marqué indisponible. Pour la même "
     "raison, les variables Sirene n'ont jamais pu entrer dans le modèle d'accessibilité : "
     "l'hypothèse d'un effet de la densité d'employeurs sur la sélectivité reste non testée, "
     "pas infirmée. Voir l'ablation en fin de section.")

encadre("Justification du choix : n'apprendre qu'un seul composant", [
    "L'affinité est une préférence exprimée par le candidat lui-même : rien à prédire, la "
    "valeur est dans la requête, la pondération relève de règles arbitrées avec des "
    "conseillers d'orientation.",
    "Les débouchés sont un dénombrement : la densité d'employeurs d'un secteur se calcule "
    "exactement depuis Sirene ; en faire une prédiction n'ajouterait rien et retirerait de la "
    "transparence.",
    "L'accessibilité, elle, doit être apprise : elle dépend d'une combinaison de facteurs "
    "(sélectivité historique, capacité, tension, territoire, profil du candidat) qu'aucune "
    "table ne décrit. C'est le seul endroit où un modèle apporte ce qu'une règle ne peut pas "
    "produire.",
])

para("Algorithme : le modèle d'accessibilité est un gradient boosting (LightGBM) entraîné sur "
     "les résultats d'admission publiés, tracé dans MLflow. Je le préfère à un réseau de "
     "neurones : les variables sont tabulaires, l'inférence doit rester légère, et les valeurs "
     "de Shapley y sont exactes. Il est couplé à SHAP, qui donne pour chaque recommandation "
     "les facteurs déterminants — exigé par l'AI Act et le droit à explication du RGPD. "
     "L'axiome d'efficacité de SHAP est vérifié à 2,1 × 10⁻¹⁵ près sur le modèle réel et par un "
     "test indépendant sur un modèle jouet ; le précalcul complet (440 030 cellules, "
     "8,3 minutes, 99,8 Mo) alimente la route /explain de l'API.")

encadre("Justification du choix : apprendre sur les données publiques plutôt que sur le "
        "comportement des utilisateurs", [
    "EduMatch démarre et n'a aucun historique d'usage : c'est le problème classique du "
    "démarrage à froid, impossible d'apprendre sur un comportement qui n'existe pas encore.",
    "La réponse retenue : apprendre la partie prédictive sur des données publiques déjà là, et "
    "traiter le reste par des règles et des taux observés. Les résultats Parcoursup donnent "
    "exactement l'information recherchée, publiée chaque année depuis 2018.",
    "Conséquence favorable : le seul composant appris repose sur un label observé et "
    "vérifiable, pas sur un indicateur de substitution — le modèle est évaluable honnêtement "
    "dès la première campagne.",
])

para("Le chatbot RAG, brique secondaire, est réécrit pour ce projet plutôt que repris du MVP : "
     "il restitue en langue naturelle, avec citation des sources officielles, ce qui fonde une "
     "recommandation, sans faire partie du dispositif de réentraînement du modèle "
     "d'accessibilité. Le corpus (7 403 documents ONISEP) est indexé par recherche lexicale "
     "(TF-IDF) plutôt que par embeddings et base vectorielle, écartés faute de volume qui en "
     "justifierait le coût ; la citation est garantie par construction, puisque la liste des "
     "sources vient des documents retrouvés avant l'appel au modèle de langage, jamais de ce "
     "que celui-ci prétend avoir lu. Les briques du MVP (CamemBERT, FAISS, LangChain, "
     "Mistral-small) ne sont pas reprises.")

para("Cible, protocole et équité du modèle d'accessibilité.", bold=True)
para("L'unité d'observation est la cellule : formation × session × type de bac × statut de "
     "boursier. La cible est le taux d'admission observé de cette cellule, rapport entre "
     "propositions d'admission et vœux en phase principale — deux grandeurs publiées.")
table([
    ["Élément", "Valeur retenue"],
    ["Cible", "Taux d'admission observé, dans [0, 1]. Mesuré et publié, ni simulé ni dérivé "
              "d'un indicateur de substitution"],
    ["Volumétrie", "77 159 cellules pour la session 2025 ; 440 030 observations sur les six "
                   "sessions où le label est calculable (2020-2025)"],
    ["Pondération", "Chaque observation pondérée par l'effectif de la cellule : une cellule de "
                    "trois candidats porte un taux bruité, une cellule de cinq cents une "
                    "information fiable"],
    ["Séparation", "Strictement temporelle : entraînement 2020-2023 (286 463 cellules), "
                   "validation 2024 (76 408), test 2025 (77 159). Bornée aux six sessions où le "
                   "label existe (le numérateur par type de bac n'est pas publié en 2018-2019). "
                   "Une séparation aléatoire placerait la même formation de part et d'autre et "
                   "produirait une fuite d'information"],
    ["Référence obligatoire", "Taux d'admission de la même cellule à la session précédente. Si "
                              "le modèle ne bat pas cette référence, cela est rapporté"],
], header=True)
para("Résultat, rapporté tel quel : le modèle appris ne bat pas son plancher en test.",
     bold=True)
table([
    ["Métrique", "Modèle (test 2025)", "Plancher — taux session précédente (test 2025)",
     "Verdict"],
    ["MAE pondérée par l'effectif", "0,0758", "0,0701", "le modèle perd"],
    ["Erreur de calibration attendue (ECE, 10 tranches)", "0,0371", "0,0322", "le modèle perd"],
], header=True)
para("En validation 2024, le modèle passait devant (0,0690 contre 0,0727 de MAE pondérée, "
     "0,0030 contre 0,0141 d'ECE) ; en test 2025 il repasse derrière sur les deux métriques. "
     "La courbe d'apprentissage (10, 25, 50, 100 % du volume : 0,0758, 0,0723, 0,0705, 0,0698 "
     "de MAE pondérée en validation) montre que ce n'est pas un manque de données — le gain "
     "marginal se divise par deux à chaque doublement du volume — mais une dérive entre les "
     "sessions d'entraînement (2020-2023) et le test (2025). Le seuil à battre (0,0701 de MAE "
     "pondérée) a été écrit avant l'entraînement, et le résultat est rapporté tel qu'il est "
     "sorti. C'est ce résultat qui fonde l'avis défavorable du délégué à la protection des "
     "données sur la restitution de cette estimation à des candidats réels (section 4).")
para("Restitution : l'estimation est présentée comme une fréquence observée, pas une "
     "prédiction individuelle : « sur cent candidats avec votre profil ayant demandé cette "
     "formation, tel nombre a reçu une proposition ». Le modèle ne connaît ni les notes, ni "
     "les appréciations, ni la lettre de motivation, alors que la sélection s'appuie sur tout "
     "le dossier. Cette formulation figure dans l'écran de supervision et dans l'API, avec la "
     "mise en garde issue du résultat ci-dessus attachée à chaque score.")

encadre("Justification du choix : exclure le genre du modèle, et pourquoi cela ne coûte rien", [
    "Aucune variable de genre n'entre dans le modèle ; elle sert seulement à l'audit d'équité "
    "a posteriori. Les substituts possibles (établissement d'origine, académie) sont testés "
    "pour corrélation résiduelle.",
    "On objecte souvent qu'exclure une variable prédictive coûte de la précision. La mesure "
    "montre que non ici : sur les 11 099 formations recevant au moins trente vœux de chaque "
    "sexe, l'écart médian de taux d'admission entre femmes et hommes est nul, la moyenne "
    "inférieure à un demi-point, et il reste sous cinq points dans 83,8 pour cent des cas.",
    "La sélection s'appuie sur le dossier scolaire, pas sur le sexe : le genre agit sur le "
    "choix des formations demandées, pas sur la probabilité d'être admis une fois le vœu "
    "formulé. Même si un écart existait, l'utiliser serait exclu : ce serait une "
    "discrimination directe, et le système amplifierait la ségrégation en boucle.",
])

para("Audit d'équité, sur les prédictions réelles du modèle, sur quatre dimensions : type de "
     "baccalauréat, statut de boursier, genre, territoire. La définition retenue — la "
     "calibration par groupe, un taux prédit de 60 % doit correspondre à un taux observé de "
     "60 % dans chaque groupe — est déclarée avant la mesure, car elle est incompatible avec "
     "la parité démographique dès que les taux de base diffèrent entre groupes : un théorème "
     "d'impossibilité, pas un arbitrage de goût.")
table([
    ["Indicateur", "Formations à plus de 80 % de candidates femmes", "Autres formations"],
    ["Ratio d'impact disparate (modèle)", "0,76 — sous le seuil des quatre cinquièmes (0,80)",
     "—"],
    ["Ratio d'impact disparate (plancher)", "0,63", "—"],
    ["Erreur de calibration attendue (ECE)", "0,066", "0,032 à 0,034"],
], header=True)
para("Le système n'est pas équitable sur cette dimension, et ce résultat n'est pas atténué : "
     "il fait mieux que le plancher sur la sélection (0,76 contre 0,63) mais moins bien sur la "
     "calibration, où il sur-annonce les chances sur les formations très féminisées. "
     "L'établissement d'origine (28,9 % net d'information mutuelle) et la filière (19,5 % net) "
     "sont les substituts du genre les plus puissants : l'établissement est exclu du modèle "
     "pour cette raison et pour sa cardinalité, la filière est conservée car sa suppression "
     "détruirait la capacité du modèle à distinguer les formations. L'audit confirme "
     "qu'exclure des variables à l'entrée ne suffit pas : le dispositif repose sur trois "
     "niveaux — exclusion du genre, mesure des substituts, audit a posteriori. La dimension "
     "territoriale reste, à ce stade, non pénalisante.")

encadre("Justification du choix : l'apport de chaque source est mesuré, non postulé", [
    "Une étude d'ablation à sept variantes mesure ce que chaque bloc de variables apporte, sur "
    "la validation 2024. Retirer les 35 variables décalées (dont le taux de la session "
    "précédente) fait passer la MAE pondérée de 0,0698 à 0,1120 (+0,0422) — l'essentiel de la "
    "performance vient de connaître ce taux.",
    "Retirer les quatre substituts du genre encore présents (filière, sélectivité, "
    "département, académie) coûte seulement +0,0006 et ne répare pas l'équité : le ratio "
    "d'impact disparate du groupe le plus féminisé se dégrade légèrement (0,66 à 0,62), ce qui "
    "confirme que l'information sur le genre est diffuse, pas concentrée dans ces colonnes.",
    "L'apport de Sirene n'a pas pu être mesuré : la chaîne de nomenclatures ne relie aucune "
    "formation Parcoursup à une activité NAF par une clé fiable, Sirene n'est donc jamais "
    "entré dans la table de variables. Ce n'est pas un apport nul mesuré, c'est une limite du "
    "dispositif, déclarée plutôt que déguisée en mesure.",
])

para("Intégration : le modèle est exposé par une API FastAPI conteneurisée (gestion des "
     "erreurs, authentification, limitation de débit, en-têtes de sécurité). Les "
     "recommandations alimentent l'écran de supervision des conseillers, qui répond à "
     "l'exigence de contrôle humain de l'article 14 : le conseiller revoit chaque "
     "recommandation, la contextualise avec le dossier réel de l'élève que le modèle ne "
     "connaît pas, et peut l'écarter en motivant sa décision — écartement bloqué côté client "
     "et côté serveur, vérifié par test. L'accessibilité RGAA de cet écran est couverte par "
     "des tests unitaires (structure sémantique, contraste WCAG, focus jamais supprimé) et par "
     "une procédure d'audit navigateur écrite, mais pas encore déroulée : aucun rapport "
     "d'audit n'existe à ce jour.")
para("CI/CD : trois workflows GitHub Actions sont écrits dans le second dépôt (intégration, "
     "construction et publication d'images étiquetées par le commit, déploiement délibéré et "
     "non automatique). Aucun n'a encore été exécuté : une première exécution reste à "
     "déclencher pour voir ce qu'un YAML jamais testé cache toujours. Le suivi d'expériences "
     "MLflow est en service (cinq exécutions tracées), et le registre de modèles porte une "
     "version (edumatch-accessibilite v1), sans stade ni alias : l'étiquette posée dessus "
     "déclare en clair qu'elle ne bat pas le plancher en test. Deux dépôts de code distincts "
     "existent, sans recouvrement : la solution IA et l'intégration-déploiement (36 fichiers : "
     "workflows, Terraform, manifestes Kubernetes, monitoring).")
para("Dérive, mesurée sur les données réelles : l'indice de stabilité de population (PSI) et "
     "le test de Kolmogorov-Smirnov sont calculés sur les six sessions où le label existe "
     "(2020-2025), pour trois familles — variables, cible, prédictions. Evidently a été "
     "écarté, conflit de dépendance avec un paquet dont FastAPI dépend déjà. Le seuil de 0,20 "
     "s'applique à la médiane du PSI plutôt qu'à son maximum, pour ne pas déclencher en "
     "permanence sur des colonnes instables sans rapport avec la performance. C'est l'un des "
     "quatre résultats défavorables du projet : à ce seuil, le PSI n'aurait pas signalé la "
     "dégradation observée entre validation et test — c'est une dérive du concept, la relation "
     "entre les variables et la cible change alors que la distribution des entrées bouge à "
     "peine, à laquelle un indice qui ne compare que des distributions marginales est aveugle "
     "par construction. Le réentraînement automatique reste à construire : la détection "
     "journalise un avertissement mais ne déclenche encore rien. Le monitoring en production "
     "(Prometheus, Grafana, SLO sur la latence p95 et la disponibilité) est écrit dans le "
     "second dépôt, mais n'a jamais tourné en production.")
para("À livrer : rapport d'audit RGAA exécuté, première exécution de la chaîne d'intégration "
     "capturée, un réentraînement qui bat le plancher pour que la porte de promotion publie "
     "une version, capture vidéo de la solution en production. La présentation, le dépôt n°1 "
     "(solution IA) et le dépôt n°2 (intégration et déploiement continus) existent déjà, avec "
     "du code réel et distinct.", italic=True)

d.add_page_break()

# =====================================================================
# 8. SYNTHÈSE
# =====================================================================
h("8. Synthèse des livrables et soutenance", 1)
table([
    ["Bloc", "Livrables principaux", "Évaluation"],
    ["Bloc 1", "Plan de gouvernance, analyse d'impact, Model Card, registre des sources, slides",
     "Lecture 15 min, présentation 15 min, questions 15 min"],
    ["Bloc 2", "Diagrammes C4, code d'infrastructure, vidéo",
     "Lecture 20 min, présentation 5 min, questions 15 min"],
    ["Bloc 3", "Diagramme de pipeline, code, vidéo",
     "Lecture 20 min, présentation 5 min, questions 15 min"],
    ["Bloc 4", "Slides, dépôt n°1, dépôt n°2, vidéo", "Présentation et questions devant le jury"],
], header=True)
para("Fil conducteur de la soutenance : partir des constats mesurés dans les données "
     "publiques — la ségrégation par le genre est massive alors que les femmes sont "
     "majoritaires parmi les admis, et l'accès reste inégal selon le baccalauréat. Puis "
     "dérouler la chaîne complète, de la gouvernance à la solution, en montrant que chaque "
     "source répond à une question précise et qu'un seul composant est appris, défendu par "
     "« X plutôt que Y parce que... ». Quatre résultats défavorables, mesurés et non atténués, "
     "structurent une part importante de cette défense : le modèle ne bat pas le taux de la "
     "session précédente en test (MAE pondérée 0,0758 contre 0,0701, ECE 0,0371 contre "
     "0,0322), le ratio d'impact disparate sur les formations très féminisées est à 0,76, sous "
     "le seuil légal de 0,80, la couverture du terme de débouchés n'atteint que 1,4 % des "
     "lignes, et l'avis du délégué à la protection des données est scindé, défavorable à la "
     "restitution du terme appris à des candidats réels tant qu'il n'aura pas été corrigé. "
     "Chacun de ces résultats est mesuré, documenté et assumé, ce que je présente comme une "
     "garantie de rigueur plutôt qu'une faiblesse à minimiser.")

# =====================================================================
# 9. RELECTURE AVANT REMISE
# =====================================================================
h("9. Relecture avant remise", 1)
para("Avant de remettre ce dossier, j'ai relu chaque section pour vérifier que ce qui y est "
     "affirmé se retrouve dans le dépôt. La problématique s'appuie sur des chiffres recalculés "
     "à partir du fichier source. Chaque choix technique important est justifié sous la forme "
     "« X plutôt que Y parce que... », avec au moins une alternative écartée. Aucune donnée "
     "n'est simulée : toutes les sources sont publiques, réelles et sous licence vérifiée. Les "
     "quatre résultats défavorables du projet figurent dans le corps du texte, pas en annexe : "
     "la performance du modèle sous son plancher en test, le ratio d'impact disparate sous le "
     "seuil légal, la couverture du terme de débouchés à 1,4 %, l'avis scindé et défavorable "
     "du délégué à la protection des données sur le terme appris. Ce qui n'existe pas encore "
     "est écrit au futur : déploiement cloud réel, exécution de la chaîne d'intégration, panne "
     "filmée, vidéos de production.")

d.save(OUT)
print("OK ->", OUT)
