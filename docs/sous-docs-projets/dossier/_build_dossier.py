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
                        "estimant les chances d'admission et les débouchés territoriaux, au "
                        "service de l'orientation scolaire et professionnelle"],
    ["Certification", "Architecte en Intelligence Artificielle - Mastère 2 (AIA02)"],
    ["Date", "Septembre 2026 (version 3, régénérée contre le dépôt le 2026-09-16)"],
])
d.add_paragraph()

para("Ce document présente le projet et justifie ses choix structurants selon la forme "
     "« X plutôt que Y parce que… ». Les volumétries et les taux qui y figurent ont été "
     "vérifiés par téléchargement et recalculés à partir des fichiers sources ; ils sont "
     "reproductibles à partir des références citées.", italic=True)

d.add_page_break()

# =====================================================================
# 1. PRÉSENTATION GÉNÉRALE
# =====================================================================
h("1. Présentation générale du projet", 1)

h("1.1 Secteur et organisation", 2)
para("EduMatch est une jeune entreprise EdTech française basée en Île-de-France, en phase "
     "d'amorçage (levée de type seed de 350 000 euros). Elle édite une plateforme SaaS "
     "d'orientation scolaire et professionnelle, sur un modèle B2B2C : ses clients sont des "
     "établissements (lycées, collèges, CFA, organismes de formation) et ses utilisateurs "
     "finaux des élèves, étudiants et personnes en reconversion.")
para("Le secteur de l'orientation est doublement structurant. Il repose sur l'agrégation de "
     "données publiques de référence : les résultats d'admission Parcoursup publiés par le "
     "ministère, la base Sirene de l'INSEE qui décrit le tissu économique et donc les "
     "débouchés, les référentiels de formations et de métiers, et il est sensible et réglementé : le public combine des mineurs et des adultes, "
     "et un système qui influence l'accès à l'éducation relève des usages à haut risque au sens "
     "du règlement européen sur l'intelligence artificielle (annexe III, point 3). Ce double "
     "caractère rend les quatre blocs naturellement nécessaires.")

para("La ségrégation par le genre est le trait le plus frappant de ces données. Sur la session "
     "Parcoursup 2025, qui couvre 14 252 formations, 2 775 d'entre elles, soit 19,7 pour cent "
     "sur dénominateur non nul (les formations n'admettant aucun candidat sont exclues du "
     "calcul, sans quoi un taux nul mécanique se lirait à tort comme une extrême faible "
     "féminisation), comptent moins de 20 pour cent de femmes parmi leurs admis, et 17,9 pour "
     "cent en comptent plus de 80 pour cent ; seules 21,5 pour cent se situent dans une zone "
     "équilibrée, entre 40 et 60 pour cent. L'écart est structurel : la médiane du taux de "
     "féminisation atteint 18 pour cent en école d'ingénieur, contre 86 pour cent en institut de "
     "formation en soins infirmiers et 90 pour cent dans les formations du travail social.")
para("Il ne s'agit pas d'une sous-représentation globale : les femmes constituent 56,3 pour cent "
     "des admis, toutes formations confondues. Elles sont donc majoritaires, mais très "
     "inégalement réparties. Ce n'est pas l'accès à l'enseignement supérieur qui est en cause, "
     "c'est l'orientation qui y conduit, précisément l'objet de ce projet.")

para("À cette ségrégation s'ajoute une inégalité d'accès selon le baccalauréat d'origine. Sur "
     "la même session, 36,7 pour cent des vœux formulés par des bacheliers généraux ont donné "
     "lieu à une proposition d'admission, contre 29,5 pour cent pour les bacheliers "
     "technologiques et 26,9 pour cent pour les bacheliers professionnels : à vœu comparable, "
     "les chances d'un bachelier professionnel sont réduites de plus d'un quart.")
para("Précision de lecture : ces taux sont calculés par vœu et non par candidat : un lycéen "
     "formulant une dizaine de vœux conserve une probabilité élevée d'obtenir au moins une "
     "proposition, c'est l'accès à chaque formation prise isolément qui est inégal. Il s'agit "
     "en outre du taux agrégé sur l'ensemble des vœux, et non de la moyenne des taux formation "
     "par formation, qui accorderait le même poids à une formation recevant trente vœux et à une "
     "formation en recevant trente mille.", italic=True)
para("Ces deux phénomènes n'appellent pas la même réponse du système, et la distinction est "
     "structurante. L'inégalité d'accès selon le baccalauréat est ce que le moteur doit estimer "
     "et restituer honnêtement au candidat : c'est la réalité de la sélection, et la lui cacher "
     "serait lui nuire. La ségrégation par le genre est au contraire ce que le système ne doit "
     "en aucun cas amplifier : aucune variable de genre n'entre dans le modèle, et l'audit "
     "d'équité vérifie qu'aucune variable de substitution ne la reconstitue. Mesurer l'une, "
     "neutraliser l'autre : c'est l'exigence de conception centrale du projet.")
para("Source : ministère de l'Enseignement supérieur et de la Recherche, données ouvertes "
     "Parcoursup, session 2025 (jeu fr-esr-parcoursup, Licence Ouverte Etalab v2.0). Les valeurs "
     "ci-dessus ont été recalculées à partir du fichier source.", italic=True)

d.add_page_break()

# ---------------------------------------------------------------------
h("1.2 Problématique métier", 2)

para("Trois causes structurelles expliquent les mauvais choix d'orientation : un manque "
     "d'information sur les formations et leurs débouchés, des déterminismes sociaux et "
     "territoriaux qui orientent selon le milieu d'origine, et des stéréotypes de genre qui "
     "enferment les choix.")

para("Ces causes ont une conséquence directe sur la conception d'EduMatch : le système ne "
     "doit surtout pas les reproduire, ce qui fait de la non-discrimination et de "
     "l'explicabilité une exigence de cœur, et non un habillage réglementaire.")
para("Le score de recommandation combine trois termes, dont un seul est appris :", bold=True)
table([
    ["Terme", "Question", "Source", "Nature"],
    ["Affinité", "Cela correspond-il aux centres d'intérêt du candidat ?",
     "Intérêts déclarés dans la requête", "Règles métier, aucun apprentissage"],
    ["Accessibilité", "Le candidat a-t-il une chance d'être admis ?",
     "Parcoursup, huit millésimes bruts, six exploitables pour le label (2020-2025)",
     "MODÈLE APPRIS (LightGBM, entraîné et tracé dans MLflow), explicabilité SHAP produite "
     "(TreeSHAP, précalculée sur les 440 030 cellules) — résultat de performance défavorable en "
     "test, détaillé en section 7"],
    ["Débouchés", "La formation mène-t-elle à un emploi atteignable ?",
     "Base Sirene, référentiels métiers",
     "Agrégats de densité et de dynamique des employeurs, aucun apprentissage"],
], header=True)
para("Les trois termes sont combinés de façon multiplicative : si l'un s'annule, la "
     "recommandation disparaît. Recommander une formation accessible mais sans affinité, ou "
     "adéquate mais sans aucun employeur du secteur dans un rayon atteignable, serait une "
     "mauvaise orientation.")

para("Périmètre de la certification. Le produit EduMatch comporte plusieurs fonctionnalités, mais "
     "la certification porte sur un seul système décisionnel :", bold=True)
table([
    ["Composant", "Rôle dans la certification"],
    ["Moteur d'orientation explicable",
     "Composant central et seul modèle industrialisé de bout en bout (blocs 1 à 4). Décision "
     "automatisée à fort enjeu : c'est lui qui ancre les exigences d'explicabilité, de "
     "non-discrimination et de supervision humaine."],
    ["Chatbot fondé sur la génération augmentée par récupération (RAG)",
     "Brique secondaire. Il restitue en langue naturelle, avec citation des sources officielles, "
     "les éléments qui fondent une recommandation. Intégré et supervisé, mais non industrialisé "
     "au même niveau d'exigence."],
], header=True)
para("Le périmètre certifiant se limite à ces deux briques. L'écran de supervision destiné aux "
     "conseillers d'orientation n'est pas une fonctionnalité produit : c'est un composant de "
     "conformité, imposé par l'exigence de contrôle humain de l'AI Act, traité en section 7.",
     italic=True)

para("Le projet est soumis à des contraintes qui imposent des arbitrages :")
bullets([
    "Volumétrie et hétérogénéité : cinq sources publiques dont les tailles s'échelonnent sur plus "
    "de deux ordres de grandeur, du référentiel de quelques mégaoctets à une base de 43,9 millions "
    "d'établissements. Les confondre conduirait soit à sous-dimensionner, soit à surdimensionner "
    "l'architecture (section 2).",
    "Performance et fraîcheur : la recommandation doit être calculée en latence interactive, "
    "alors que les sources se mettent à jour à des rythmes très différents : Parcoursup une fois "
    "par an à l'issue de la campagne, Sirene chaque mois, les référentiels de façon continue.",
    "Budget : structure de coûts d'une startup en amorçage, imposant un pilotage FinOps de "
    "l'inférence et un arbitrage permanent entre services managés et auto-hébergement.",
    "Conformité : traitement de données personnelles de mineurs et d'adultes. Les caractéristiques "
    "scolaires et les appétences transmises au moteur, mises en correspondance avec des "
    "formations, constituent un profilage produisant une décision automatisée au sens de "
    "l'article 22. Cela exige une base légale, le consentement, la minimisation, la transparence "
    "sur la logique et une analyse d'impact. S'y ajoutent l'explicabilité et la non-discrimination "
    "exigées par l'AI Act, et le respect des licences de réutilisation (section 3).",
])

h("1.3 Parties prenantes", 2)
table([
    ["Direction (3 associés)", "Fixent la stratégie produit et arbitrent le rapport valeur / coût "
                              "/ conformité ; sponsors du projet."],
    ["Cheffe de projet agile", "Pilote le backlog, les sprints et la coordination de l'équipe."],
    ["Architecte IA", "Conçoit l'architecture, arbitre les choix technologiques, pilote la "
                      "gouvernance des données et de l'IA et la mise en production."],
    ["DPO", "Garant de la conformité RGPD : données de mineurs et d'adultes, licéité de la "
            "réutilisation des données publiques."],
    ["Équipe de développement", "Met en œuvre les pipelines, le moteur et le RAG sous la "
                                "responsabilité de l'architecte."],
    ["Conseillers d'orientation", "Superviseurs humains des recommandations : ils revoient, "
                                  "contextualisent et peuvent écarter une recommandation."],
    ["Établissements clients et utilisateurs", "Lycées, CFA, organismes de formation ; élèves, "
                                               "étudiants, personnes en reconversion et familles."],
    ["Fournisseurs de données", "Ministère de l'Enseignement supérieur (Parcoursup) ; INSEE "
                               "(base Sirene) ; France Compétences, ONISEP, IDEO métier."],
    ["Référent accessibilité", "Garantit la conformité RGAA pour les personnes en situation de "
                               "handicap."],
])

d.add_page_break()

# =====================================================================
# 2. ENVIRONNEMENT TECHNIQUE
# =====================================================================
h("2. Environnement technique existant", 1)
para("J'ai conçu et développé moi-même la première version d'EduMatch : un MVP fonctionnel qui "
     "valide le concept et sert aujourd'hui de point de départ. Il repose sur un front Next.js et "
     "React (TypeScript, Redux) et un back FastAPI ; l'assistant RAG y enchaîne embeddings "
     "CamemBERT, recherche vectorielle FAISS, orchestration LangChain et génération Mistral-small. "
     "Ces choix ont été faits pour livrer vite et prouver la valeur du produit, non pour la "
     "production à grande échelle : l'ingestion reste semi-manuelle, sans orchestration ni "
     "contrôle qualité, l'infrastructure n'est pensée ni pour la conformité ni pour la montée en "
     "charge, et le moteur d'orientation n'est pas encore développé. Le présent projet est la "
     "suite directe de ce travail : restructurer et industrialiser cette base.")

para("Les trois sources, leur rôle et leur volumétrie.", bold=True)
para("Chaque source répond à une question précise du système : aucune n'est présente pour "
     "justifier une architecture, et aucune ne peut être retirée sans amputer une des "
     "dimensions de la décision.")
table([
    ["Source", "Ce qu'elle apporte", "Volumétrie vérifiée", "Licence"],
    ["Parcoursup, sessions 2018 à 2025 (MESR)",
     "Résultats d'admission par formation et par profil de candidat. Source du label du "
     "modèle appris.",
     "104 274 formation-années, 118 colonnes (2025), 82 Mo mesurés sur les 8 CSV posés sur "
     "disque. 77 159 cellules exploitables par millésime",
     "Licence Ouverte v2.0"],
    ["Base Sirene (INSEE)",
     "Tissu économique : activité, commune, effectifs, créations et cessations depuis 1973. "
     "Densité et dynamique des employeurs par secteur et par bassin.",
     "43 896 818 établissements et 29 922 486 unités légales ; 6,44 Go compressés (ZIP) "
     "et 4,63 Go en Parquet pour les quatre fichiers retenus, stock du 1er août 2026",
     "Licence Ouverte v2.0"],
    ["Référentiels ONISEP, IDEO et RNCP",
     "Description des formations, des métiers et des certifications ; support de la mise en "
     "correspondance entre activité économique et formation.",
     "IDÉO : 5 869 formations, 1 534 métiers, 24 278 structures (15,9 Mo). RNCP et Répertoire spécifique : 30 484 fiches dont 7 000 actives (export du 29 août 2026, republié chaque jour)",
     "ONISEP et IDÉO : ODbL — partage à l'identique obligatoire sur tout dérivé redistribué. "
     "RNCP (France Compétences) : Licence Ouverte v2.0"],
], header=True)

para("Les données présentent les trois dimensions (3V) de façon non triviale :")
bullets([
    "Volume : 43,9 millions d'établissements à joindre et agréger par secteur et par territoire, "
    "soit 25 à 30 Go décompressés, à côté d'un référentiel d'admission d'une centaine de "
    "mégaoctets.",
    "Vélocité : publications périodiques traitées en batch (Parcoursup annuel, Sirene mensuel, "
    "référentiels continus), face à des recommandations servies en latence interactive.",
    "Variété : fichiers CSV structurés, fichiers Parquet volumineux, réponses d'API, référentiels "
    "et données déclaratives des candidats. L'hétérogénéité des nomenclatures (activité NAF, "
    "métier ROME, codes de formation) est au cœur du défi de pipeline.",
])

d.add_page_break()

# =====================================================================
# 3. CONTRAINTES RÉGLEMENTAIRES
# =====================================================================
h("3. Contraintes réglementaires", 1)
bullets([
    "RGPD et loi Informatique et Libertés. L'architecture sépare nettement deux régimes, ce qui "
    "réduit fortement la surface de risque. L'entraînement du modèle ne mobilise aucune donnée à "
    "caractère personnel : les résultats Parcoursup sont des comptages agrégés par formation et "
    "la base Sirene décrit des établissements, non des personnes. Les données "
    "personnelles n'interviennent qu'à l'inférence, lorsqu'un candidat renseigne ses "
    "caractéristiques scolaires et ses centres d'intérêt. Il ne s'agit pas d'un profil de "
    "compte "
    "alimenté par l'usage de l'application : aucune donnée de navigation, d'historique ou de "
    "comportement n'intervient, ni à l'entraînement, ni à l'inférence.",
    "Ces informations se limitent au type de baccalauréat, à la mention, au statut de boursier, "
    "au territoire et aux centres d'intérêt déclarés : c'est le strict nécessaire au "
    "calcul, en application du principe de minimisation. Le public comprenant des mineurs, la "
    "base légale repose sur le consentement, recueilli auprès du titulaire de l'autorité "
    "parentale en dessous de quinze ans. La recommandation constituant une décision individuelle "
    "automatisée au sens de l'article 22, l'utilisateur dispose d'un droit à l'information sur la "
    "logique sous-jacente : c'est la fonction des explications produites par SHAP. Les droits "
    "d'accès, de rectification, d'effacement et d'opposition au profilage sont mis en œuvre.",
    "Un arbitrage doit être explicité entre deux exigences en tension. L'article 12 du règlement "
    "sur l'IA impose la journalisation des inférences pour assurer la traçabilité des décisions ; "
    "le RGPD impose au contraire une limitation des durées de conservation. La conciliation "
    "retenue est une durée définie et documentée, au terme de laquelle les journaux sont "
    "pseudonymisés puis agrégés, de façon à conserver la capacité d'audit sans conserver "
    "l'identification. Une analyse d'impact est conduite, le profilage systématique de mineurs la "
    "rendant obligatoire.",
    "Réutilisation des données publiques : les jeux du ministère et de l'INSEE sont diffusés sous "
    "Licence Ouverte v2.0 (Etalab), qui autorise la réutilisation, y compris commerciale, sous "
    "réserve de mention de la source. Un registre des sources et de leurs "
    "conditions de réutilisation est tenu et audité au même titre que le registre des "
    "traitements.",
    "Règlement européen sur l'IA : le système relève de l'annexe III, point 3, qui vise les "
    "systèmes destinés à déterminer l'accès ou l'admission de personnes physiques à des "
    "établissements d'enseignement. Il en découle des obligations de gestion des risques, de "
    "gouvernance des données, de documentation, de journalisation, de transparence, de contrôle "
    "humain, d'exactitude et de robustesse, détaillées au bloc 1.",
    "Sécurité (ISO 27001) et souveraineté : chiffrement, moindre privilège, journalisation. "
    "L'hébergement européen est retenu comme mesure de réduction du risque lié au traitement de "
    "données de mineurs.",
])

d.add_page_break()

# =====================================================================
# 4. BLOC 1
# =====================================================================
h("4. Bloc 1 - Gouvernance des données", 1)
para("Ce que le projet rend inévitable : données personnelles de mineurs et d'adultes, "
     "réutilisation de plusieurs sources publiques aux licences distinctes, contexte multi-parties "
     "prenantes et exigence de conformité AI Act non triviale.", italic=True)
para("Le plan de gouvernance est écrit et versionné : une politique de classification des "
     "données (publiques, internes, personnelles, sensibles) et des règles d'usage associées, dont "
     "six sur sept sont aujourd'hui contrôlées automatiquement plutôt que déclarées sur le papier ; "
     "une répartition des rôles entre un Data Owner côté direction, des Data Stewards côté équipe "
     "data et un DPO garant de la conformité, chacun avec son périmètre de décision ; un registre "
     "des traitements couvrant huit traitements identifiés (T1 à T8), avec finalité, base légale, "
     "durée et destinataires, et l'état réel de chacun déclaré plutôt que supposé. La documentation "
     "des origines, schémas, fraîcheurs et lignages est produite par l'outillage du pipeline "
     "lui-même (tests de qualité et graphe de lignage généré par dbt), sans catalogue "
     "supplémentaire à exploiter.")
para("La gestion des risques couvre onze risques identifiés (R1 à R11), répartis sur quatre "
     "familles : la violation de données de mineurs (chiffrement, minimisation, hébergement "
     "européen), la discrimination des recommandations (audit d'équité, indicateurs de parité, "
     "explicabilité), la non-conformité de réutilisation (registre des licences) et l'obsolescence "
     "des données (contrôles de fraîcheur bloquants dans le pipeline).")
table([
    ["Article", "Obligation", "Mise en œuvre dans EduMatch"],
    ["9", "Gestion des risques", "Registre des onze risques, révisé à chaque campagne "
                                 "d'orientation"],
    ["10", "Gouvernance des données", "Contrôles de qualité automatisés, audit d'équité, "
                                      "registre des sources"],
    ["11", "Documentation technique", "Dossier technique et Model Card"],
    ["12", "Journalisation", "Traçabilité horodatée de chaque recommandation produite, purge "
                             "exécutable par paliers"],
    ["13", "Transparence", "Notice utilisateur — à écrire ; restitution des facteurs "
                           "déterminants par SHAP, produite"],
    ["14", "Contrôle humain", "Écran conseiller : revue, contextualisation, possibilité "
                              "d'écarter, motif obligatoire"],
    ["15", "Exactitude et robustesse", "Protocole d'évaluation temporel, seuils de performance, "
                                       "tests. Résultat mesuré défavorable au modèle appris en "
                                       "test (section 7) — reporté, non atténué"],
], header=True)
para("L'analyse d'impact (AIPD), obligatoire du fait du profilage systématique de mineurs, refait "
     "le test de nécessité une fois les mesures disponibles, et non avant. Ce test échoue sur le "
     "terme appris : une règle de dénombrement déjà construite (le taux de la session précédente) "
     "fait mieux que le modèle en précision et en calibration sur la session de test la plus "
     "récente. L'avis qui en découle est scindé plutôt que global : défavorable à la restitution, "
     "à des candidats réels, de l'estimation produite par le modèle appris ; favorable, sous "
     "réserves, au reste du dispositif (affinité, débouchés, explications SHAP, écran de "
     "supervision, journalisation et purge) ; favorable, sans réserve de fond, à l'exploitation en "
     "environnement de démonstration. Le seuil qui lèverait le premier point est écrit avant toute "
     "nouvelle mesure : un modèle réentraîné descendant sous 0,0701 de MAE pondérée et 0,0322 "
     "d'ECE sur une session de test non consultée pendant le réglage.")
para("La conformité est maintenue par une procédure d'audit écrite, calée sur le calendrier "
     "Parcoursup, avec douze points de contrôle et trois déclencheurs ; une procédure de mise à "
     "jour, déjà appliquée à trois reprises, complète le dispositif. Ce qui reste ouvert dans ce "
     "bloc n'est pas de la rédaction supplémentaire : une notice d'information lisible par un "
     "lecteur mineur, et un identifiant de corrélation pour rendre purgeable le journal de "
     "supervision, restent à écrire.")
para("À livrer à terme : présentation synthétique devant le jury. Le reste des livrables du bloc "
     "existe : plan de gouvernance des données, analyse d'impact, Model Card, registre des "
     "sources. Évaluation : lecture jury environ 15 min, présentation 15 min, questions 15 min.",
     italic=True)

d.add_page_break()

# =====================================================================
# 5. BLOC 2
# =====================================================================
h("5. Bloc 2 - Architecture de données pour l'IA", 1)
para("Ce que le projet rend inévitable : des volumétries séparées par plus de deux ordres de "
     "grandeur, une saisonnalité marquée imposant l'élasticité, et des exigences de disponibilité "
     "et de souveraineté.", italic=True)

para("Le principe structurant : deux couches distinctes.", bold=True)
para("La couche de volume traite des dizaines de gigaoctets de données publiques ne contenant "
     "aucune donnée personnelle : la base Sirene. La couche de décision traite des "
     "référentiels compacts mais sensibles, et sert l'inférence. Cette séparation sert "
     "simultanément la performance et la conformité : le périmètre soumis au RGPD est réduit au "
     "strict nécessaire, et le calcul lourd s'exécute là où le risque de violation est "
     "structurellement nul.")

para("Modélisation : un modèle relationnel normalisé sous PostgreSQL portera le transactionnel "
     "(utilisateurs, établissements, historique des recommandations) — à construire, ce périmètre "
     "n'existe pas encore. Le modèle analytique en étoile qui structure les données d'orientation, "
     "lui, est construit (E16) : la table de faits porte les cellules d'observation, avec pour "
     "dimensions la formation, le candidat, la session et le territoire. Le choix de PostgreSQL "
     "plutôt que de conserver Firestore est justifié par le besoin de cohérence relationnelle et de "
     "requêtes analytiques que le NoSQL documentaire sert mal ; le modèle en étoile est retenu pour "
     "la prédominance des lectures analytiques.")
para("Infrastructure. Le service et l'entraînement sont conteneurisés (Docker, construction en "
     "deux étapes, exécution non-root, sonde de santé, étiquette d'image portant l'empreinte du "
     "commit) et orchestrés localement (Airflow, quatre DAG). Le code d'infrastructure cible existe "
     "dans le second dépôt : Terraform pour un cloud souverain européen (Scaleway plutôt qu'un "
     "hyperscaler hors Union européenne, arbitrage assumé au regard des données de mineurs — "
     "réseau privé, cluster Kubernetes managé, registre d'images, stockage objet, instance "
     "Airflow), manifestes Kubernetes complets (déploiement, service, autoscaling horizontal, "
     "politique réseau, budget de disruption, compte de service). "
     "**Rien de tout cela n'est déployé à ce jour** : aucun compte fournisseur n'est ouvert, "
     "aucun `apply` n'a été exécuté, et `terraform validate` lui-même n'a pas pu être lancé faute "
     "de binaire installé sur le poste de développement. C'est le point le plus exposé du projet, "
     "je le déclare comme tel plutôt que de le présenter comme fait.")
para("Sécurité, en l'état. Le cloisonnement réseau est réel : réseau privé Terraform, politique "
     "réseau Kubernetes à entrée et sortie restreintes, exécution non-root et système de fichiers "
     "en lecture seule côté conteneurs, gabarit de secret jamais commité. Le chiffrement, en "
     "revanche, n'est implémenté nulle part dans le code d'infrastructure actuel, ni au repos sur "
     "le stockage objet ni sur la base ; la gestion des accès par rôles se limite au compte de "
     "service de la supervision, sans rôle applicatif distinct — deux manques déclarés, à traiter "
     "avant tout déploiement réel. La supervision (Prometheus, Grafana, cinq alertes actionnables "
     "dont l'absence d'instrumentation elle-même) est écrite et versionnée dans le second dépôt, "
     "mais n'a jamais tourné : aucune capture, faute d'environnement où l'exécuter.")

encadre("Justification du choix : Kubernetes managé plutôt qu'un dimensionnement fixe", [
    "Le volume de données ne justifie pas à lui seul une orchestration élastique : ce serait un "
    "argument faible, et il faut le dire. La justification est ailleurs, dans la saisonnalité "
    "de l'activité.",
    "L'usage d'EduMatch suit le calendrier de l'orientation : le pic se situe de janvier à mai "
    "(formulation des vœux, salons, conseils de classe) et le creux en juillet et août. Le "
    "rapport entre charge de pointe et charge de creux est de l'ordre de 1 à 6.",
    "Un dimensionnement fixe imposerait de payer douze mois par an la capacité du pic, soit un "
    "taux d'utilisation moyen d'environ 30 pour cent. L'autoscaling permet de dimensionner à la "
    "charge réelle. Pour une startup en amorçage, cet arbitrage est un enjeu FinOps direct, et il "
    "est également plus sobre en ressources (GreenOps).",
    "Kubernetes managé est donc retenu plutôt qu'un cluster auto-géré, dont la charge "
    "d'exploitation serait excessive pour une équipe réduite, et plutôt que le PaaS actuel, qui "
    "n'offre ni autoscaling fin ni maîtrise de l'infrastructure. Les conteneurs serverless ont "
    "été envisagés puis écartés en raison des démarrages à froid, incompatibles avec la latence "
    "interactive attendue.",
])

para("À livrer à terme : infrastructure effectivement déployée sur un compte fournisseur, "
     "chiffrement et rôles applicatifs, capture de la supervision en fonctionnement, et la vidéo "
     "de l'infrastructure en production. Les diagrammes C4 (niveaux 1 et 2, Mermaid) et le code "
     "d'infrastructure as code existent d'ores et déjà. Évaluation : lecture environ 20 min, "
     "présentation 5 min, questions 15 min.", italic=True)

d.add_page_break()

# =====================================================================
# 6. BLOC 3
# =====================================================================
h("6. Bloc 3 - Pipelines de données pour l'IA", 1)
para("Ce que le projet rend inévitable : trois sources publiques de formats et de fréquences "
     "différents, des volumétries séparées par plus de deux ordres de grandeur, et la "
     "réconciliation de trois nomenclatures indépendantes.", italic=True)

para("Ingestion. Trois connecteurs, tous sur mesure, les connecteurs génériques étant "
     "inadaptés à ces sources publiques françaises :", bold=True)
table([
    ["Connecteur", "Mode d'accès", "Fréquence"],
    ["Parcoursup", "API du portail de données ouvertes du ministère, huit millésimes",
     "Annuelle, à l'issue de la campagne"],
    ["Sirene", "Catalogue data.gouv.fr, fichiers Parquet dont les adresses changent chaque mois",
     "Mensuelle"],
    ["Référentiels ONISEP, IDEO et RNCP", "Téléchargement versionné", "Sur publication"],
], header=True)
para("Les connecteurs sont idempotents et écrivent de façon atomique : un fichier déjà présent "
     "n'est pas retéléchargé, et une interruption ne laisse jamais un fichier tronqué que le "
     "pipeline croirait complet.")

para("Transformation. Deux chaînes distinctes, en cohérence avec les ordres de grandeur.",
     bold=True)
bullets([
    "Chaîne de décision, traitée en mono-nœud avec Polars puis dbt : réconciliation des huit "
    "millésimes Parcoursup dont les schémas ont évolué, nettoyage, normalisation et construction "
    "des cellules d'observation. Volumétrie de l'ordre de la centaine de mégaoctets.",
    "Chaîne de volume, agrégation de la base Sirene par commune et par secteur d'activité, "
    "calcul des dynamiques de créations et cessations sur dix ans, puis élargissement au bassin "
    "d'emploi. Volumétrie de l'ordre de la dizaine de gigaoctets. Deux moteurs implémentés et "
    "testés contre le même résultat : Polars en exécution courante, PySpark branché sur le mode "
    "cluster.",
])
para("Le nettoyage de la chaîne Sirene mérite une précision, car il conditionne la faisabilité : "
     "les 43,9 millions de lignes ne sont jamais nettoyées ligne à ligne. Le format Parquet étant "
     "orienté colonnes, seules neuf colonnes sur cinquante-quatre sont lues, et le filtrage "
     "(établissements actifs, employeurs, diffusibles) est poussé au niveau du fichier. Le volume "
     "est ainsi réduit avant toute transformation, et les contrôles qualité s'appliquent ensuite "
     "à des agrégats de quelques centaines de milliers de lignes, inspectables et testables.")

encadre("Justification du choix : mesurer avant de choisir le moteur de la chaîne de volume", [
    "Quelques dizaines de milliers de formations, soit 82 Mo mesurés sur disque, ne justifient en "
    "aucun cas un cluster distribué. La chaîne de décision est donc traitée en mono-nœud avec "
    "Polars et dbt : ce point-là ne fait pas débat.",
    "Pour la chaîne de volume, la question a été tranchée par la mesure et non par principe. "
    "Sur le fichier Sirene complet (43 896 818 lignes, 54 colonnes, réduites à 9 colonnes utiles), "
    "même filtre, même regroupement en 1 929 179 cellules : Polars traite le fichier en 18,2 "
    "secondes, PySpark en 87,0 secondes (démarrage de la JVM inclus) — Spark est 4,8 fois plus "
    "lent que Polars sur ce volume, pour un résultat rigoureusement identique. La conclusion "
    "n'est pas que Spark est inutile, mais qu'il n'apporte rien tant que le calcul tient sur un "
    "seul nœud.",
    "Ce qui empêche d'écarter Spark pour autant : l'une des quatre sources Sirene retenues, "
    "l'historique des établissements, compte à elle seule 95 865 102 lignes, et le stock est "
    "republié chaque mois. Une fusion future de plusieurs de ces fichiers change d'ordre de "
    "grandeur. Le job Spark est donc implémenté, testé (même résultat que Polars, vérifié ligne "
    "à ligne sur un échantillon commun) et branché sur le mode cluster de la configuration "
    "(`execution.moteur_volume`) — prêt à prendre le relais sans réécriture, mais pas employé par "
    "défaut faute de bénéfice mesuré aujourd'hui.",
    "Le seuil qui ferait basculer l'exécution courante vers Spark : la fusion de plusieurs des "
    "quatre fichiers Sirene retenus, ou tout calcul intermédiaire qui ne tiendrait plus dans la "
    "mémoire d'un poste de développement. Tant que ce seuil n'est pas franchi, Polars reste le "
    "chemin de production réel, et le choix contraire — imposer Spark par principe — serait "
    "pénalisable au titre des critères d'arbitrage, de FinOps et de GreenOps.",
])

para("Réconciliation des nomenclatures. C'est le cœur de la difficulté technique du pipeline. "
     "Trois nomenclatures indépendantes doivent être mises en correspondance :", bold=True)
table([
    ["Nomenclature", "Origine", "Rôle"],
    ["NAF", "Sirene (INSEE)", "Activité économique des établissements"],
    ["ROME", "Référentiels métiers français", "Métier"],
    ["Codes formation", "Parcoursup, RNCP, ONISEP", "Offre de formation"],
], header=True)
para("Cette table de correspondance conditionne la qualité du terme de débouchés : sans elle, "
     "l'existence d'employeurs du secteur correspondant à une formation ne peut être établie. "
     "Elle est construite, versionnée, testée et documentée comme un actif de données à part "
     "entière. Son taux de couverture, jusqu'à la NAF, est mesuré : 61,4 % des formations du "
     "référentiel ONISEP portant un code RNCP renseigné sont rattachées à une division NAF. "
     "**Mais aucun des huit millésimes Parcoursup ne porte de code RNCP, NSF ou ROME** : la "
     "chaîne relie le référentiel ONISEP à la NAF, pas les formations Parcoursup elles-mêmes. Le "
     "seul rapprochement mesuré entre les deux est un appariement textuel des libellés de "
     "formation, et il ne couvre que **7 libellés distincts sur 712, soit 6 017 lignes sur "
     "440 030 (1,4 %)** — les sept correspondances ont été relues à la main, ce sont des diplômes "
     "d'État très normés dont l'intitulé varie peu d'une source à l'autre. Pour les 98,6 % de "
     "lignes restantes, le terme de débouchés du score de matching (section 7) est marqué "
     "explicitement indisponible, jamais mis à zéro en silence.")

para("Automatisation, qualité et supervision.", bold=True)
para("Les contrôles qualité (E14) portent sur le schéma, la complétude et la cohérence, au moyen "
     "de contrôles versionnés (schémas Pandera pour Parcoursup, compteurs écrits à la main pour "
     "Sirene et les référentiels, retenus après mesure du coût de Great Expectations sur ce "
     "volume — inutile ici) : un taux hors de l'intervalle admissible, un effectif incohérent ou "
     "un millésime manquant bloquent la mise à jour, vérifié par une exécution réelle qui sort en "
     "échec sur les données du dépôt et par un scénario de panne rejouable par une commande. Ce "
     "blocage n'est pas une précaution facultative : sans lui, une donnée corrompue se propage "
     "jusqu'au modèle sans que personne ne le constate. La conformité RGPD est assurée par la "
     "minimisation et la traçabilité, la couche de volume ne contenant par construction aucune "
     "donnée à caractère personnel.")
para("Apache Airflow orchestre la chaîne : quatre DAG, un par cadence réelle de source (annuelle "
     "pour Parcoursup, mensuelle pour Sirene, quotidienne pour les référentiels, et un DAG de "
     "purge), couvrant ingestion, qualité, silver, gold, variables, agrégats et réconciliation des "
     "nomenclatures. La reprise sur erreur est décidée en code, pas confiée au retry natif "
     "d'Airflow (désactivé) : un vocabulaire d'erreur transitoire contre définitive, une "
     "temporisation croissante, deux scénarios de panne rejouables. **Ce qui manque encore à la "
     "chaîne** : l'entraînement et l'évaluation du modèle n'y figurent pas — ils s'exécutent "
     "encore par des commandes lancées à la main, hors du graphe. La supervision (volumétrie "
     "traitée, taux d'échec, durée d'exécution) reste à ajouter au pipeline lui-même ; les alertes "
     "aujourd'hui écrites portent sur le service d'inférence, pas sur le pipeline.")

para("À livrer à terme : capture vidéo du pipeline en production, avec panne et reprise. Le "
     "diagramme du pipeline et le code sont déjà sur le dépôt. Évaluation : lecture environ "
     "20 min, présentation 5 min, questions 15 min.",
     italic=True)

d.add_page_break()

# =====================================================================
# 7. BLOC 4
# =====================================================================
h("7. Bloc 4 - Déploiement de la solution IA", 1)
para("Ce que le projet rend inévitable : une décision automatisée à fort enjeu, une exigence "
     "d'explicabilité de droit et non de confort, des données sujettes à dérive, et un "
     "environnement de production.", italic=True)

para("Composition du score et rôle de chaque source.", bold=True)
para("La recommandation combine trois termes. Un seul composant est appris ; les deux autres "
     "reposent sur des règles métier et des agrégats calculés. Cette répartition est un choix "
     "d'architecte : on n'apprend que ce qui ne peut pas être établi autrement.")
table([
    ["Terme", "Question", "Source", "Nature du calcul"],
    ["Affinité", "Cela correspond-il aux centres d'intérêt du candidat ?",
     "Intérêts déclarés dans la requête, référentiels de domaines",
     "Règles et pondérations métier. Aucun apprentissage, aucune donnée stockée : la valeur est "
     "fournie dans l'appel."],
    ["Accessibilité", "Le candidat a-t-il une chance d'être admis ?",
     "Parcoursup, huit millésimes bruts ; six exploitables pour l'entraînement (2020-2025), le "
     "numérateur du label n'étant pas publié en 2018-2019",
     "MODÈLE APPRIS (LightGBM, entraîné et tracé dans MLflow). C'est le composant "
     "d'intelligence artificielle du système ; l'explicabilité SHAP est produite (TreeSHAP), "
     "mais le modèle ne bat pas son plancher en test (détail plus bas)."],
    ["Débouchés", "La formation mène-t-elle à un emploi atteignable ?",
     "Base Sirene, référentiels métiers",
     "Agrégats de densité et de dynamique des employeurs du secteur dans le bassin de vie. "
     "Aucun apprentissage."],
], header=True)
para("Les trois termes sont combinés de façon multiplicative, module écrit et testé "
     "(`matching/score.py`, `affinite.py`, `debouches.py`, E28) : un terme nul supprime la "
     "recommandation, propriété vérifiée séparément pour les trois termes. Si l'affinité est "
     "nulle, la formation ne correspond pas ; si l'accessibilité est nulle, elle est hors de "
     "portée ; si les débouchés sont nuls ou indisponibles, elle ne mène nulle part démontrable. "
     "Une somme pondérée ne le permettrait pas.")
para("Le terme de débouchés répond directement à la première cause identifiée en section 1.2, le "
     "manque d'information sur les débouchés, et il n'est donc pas une variable ajoutée mais une "
     "dimension constitutive de la décision. **Sa couverture réelle est faible et mesurée** : "
     "seules 6 017 lignes sur 440 030 (1,4 %) disposent d'un appariement vérifié entre une "
     "formation Parcoursup et une activité économique, faute de code RNCP, NSF ou ROME porté par "
     "le fichier Parcoursup lui-même (détail en section 6). Pour les autres lignes, le terme est "
     "marqué explicitement indisponible plutôt que mis à zéro en silence. Les variables issues de "
     "Sirene n'ont, pour la même raison, jamais pu entrer dans la table de variables du modèle "
     "d'accessibilité : l'hypothèse d'un effet de la densité d'employeurs sur la sélectivité "
     "reste non testée, faute de rattachement, et non infirmée par une mesure. Voir l'étude "
     "d'ablation en fin de section.")

encadre("Justification du choix : n'apprendre qu'un seul composant", [
    "Il serait tentant d'apprendre les trois termes. Ce serait une erreur d'architecture.",
    "L'affinité est une préférence exprimée par le candidat lui-même. Rien n'est à prédire : la "
    "valeur est déclarée dans la requête, et la pondération par domaine relève de règles métier "
    "arbitrées avec les conseillers d'orientation. Y substituer un modèle reviendrait à prétendre "
    "deviner un goût que l'utilisateur vient d'énoncer.",
    "Les débouchés sont un dénombrement. La densité d'employeurs d'un secteur dans un bassin se "
    "calcule exactement à partir de la base Sirene ; la transformer en prédiction n'apporterait "
    "aucune information et retirerait de la transparence, puisque le chiffre exact est "
    "disponible.",
    "L'accessibilité, en revanche, doit être apprise. Elle dépend d'une combinaison de facteurs "
    "(sélectivité historique, capacité, tension, territoire, caractéristiques du candidat) dont "
    "l'interaction n'est décrite par aucune table. C'est le seul endroit où un modèle apporte "
    "quelque chose qu'une règle ne saurait produire.",
])

para("Algorithme. Le modèle d'accessibilité est entraîné par gradient boosting (LightGBM) sur les "
     "résultats d'admission publiés, entraînement tracé dans MLflow (paramètres, métriques, "
     "artefact du modèle). Le gradient boosting est retenu plutôt qu'un réseau de neurones : "
     "les variables sont tabulaires, le coût d'inférence doit rester faible, et l'explicabilité "
     "par valeurs de Shapley y est exacte et directement applicable. Il est couplé à SHAP "
     "(`models/explain.py`), qui fournit pour chaque recommandation les facteurs déterminants, "
     "exigence directe de l'AI Act et du droit à explication du RGPD : l'axiome d'efficacité de "
     "SHAP est vérifié à 2,1 × 10⁻¹⁵ près sur le modèle réel et par un test indépendant sur un "
     "modèle jouet, le précalcul complet est mesuré (440 030 cellules, 8,3 minutes, 99,8 Mo), et "
     "la route `/explain` de l'API le sert.")

encadre("Justification du choix : apprendre sur les données publiques plutôt que sur le "
        "comportement des utilisateurs", [
    "EduMatch est en phase d'amorçage et ne dispose d'aucun historique d'usage. C'est la situation "
    "du démarrage à froid, problème classique des systèmes de recommandation : il est impossible "
    "d'apprendre sur un comportement qui n'existe pas encore.",
    "La réponse retenue est celle qui fait référence dans le domaine : apprendre la partie "
    "prédictive sur des données publiques déjà disponibles, et traiter le reste par des règles et "
    "des taux observés. Les résultats d'admission de Parcoursup contiennent précisément "
    "l'information recherchée, la sélectivité effective d'une formation pour un type de candidat "
    "donné, et ils sont publiés chaque année depuis 2018.",
    "Cette décomposition a une conséquence favorable : le seul composant appris repose sur un "
    "label observé et vérifiable, et non sur un indicateur de substitution construit à partir "
    "d'un comportement supposé. Le modèle est donc évaluable de façon honnête dès la première "
    "campagne.",
])

para("Le chatbot RAG, brique secondaire, est construit et réécrit pour ce projet plutôt que "
     "repris du MVP décrit en section 2 (`src/edumatch/rag/`) : il restitue en langue naturelle, "
     "avec citation des sources officielles, les éléments qui fondent une recommandation, sans "
     "faire l'objet du dispositif de réentraînement et de détection de dérive du modèle "
     "d'accessibilité. Le corpus (7 403 documents issus des référentiels ONISEP) est indexé par "
     "recherche lexicale (TF-IDF) plutôt que par embeddings et base vectorielle, écartés faute de "
     "volume qui en justifierait le coût ; la citation est garantie par construction, puisque la "
     "liste des sources est bâtie à partir des documents retrouvés avant l'appel au modèle de "
     "langage, jamais depuis ce que ce dernier prétend avoir consulté. Les briques du MVP "
     "(CamemBERT, FAISS, LangChain, Mistral-small) n'ont donc pas été reprises : la sobriété "
     "technique est ici la réponse d'architecte à un composant hors du périmètre certifiant "
     "principal.")

para("Cible, protocole et équité du modèle d'accessibilité.", bold=True)
para("L'unité d'observation est la cellule, croisement d'une formation, d'une session, d'un type "
     "de baccalauréat et d'un statut de boursier. La cible est le taux d'admission observé de "
     "cette cellule, rapport entre les propositions d'admission et les vœux formulés en phase "
     "principale, deux grandeurs publiées.")
table([
    ["Élément", "Valeur retenue"],
    ["Cible", "Taux d'admission observé de la cellule, dans l'intervalle [0, 1]. Label mesuré et "
              "publié : ni simulé, ni dérivé d'un indicateur de substitution"],
    ["Volumétrie", "77 159 cellules exploitables pour la session 2025 ; 440 030 observations "
                   "sur les six sessions où le label est calculable (2020-2025)"],
    ["Pondération", "Chaque observation est pondérée par l'effectif de la cellule : une cellule "
                    "de trois candidats porte un taux très bruité, une cellule de cinq cents une "
                    "information fiable"],
    ["Séparation", "Strictement temporelle : entraînement 2020-2023 (286 463 cellules), "
                   "validation 2024 (76 408), test 2025 (77 159). Bornée aux six sessions où le "
                   "label existe réellement (le numérateur ventilé par type de baccalauréat n'est "
                   "pas publié en 2018-2019) : y inclure ces deux millésimes aurait placé une "
                   "cible absente dans l'entraînement. Une séparation aléatoire, elle, placerait "
                   "la même formation de part et d'autre et produirait une fuite d'information"],
    ["Référence obligatoire", "Taux d'admission de la même cellule à la session précédente. Si le "
                              "modèle ne bat pas cette référence, cela est rapporté"],
], header=True)
para("Résultat, rapporté tel quel : le modèle appris ne bat pas son plancher en test.", bold=True)
table([
    ["Métrique", "Modèle (test 2025)", "Plancher — taux de la session précédente (test 2025)",
     "Verdict"],
    ["MAE pondérée par l'effectif", "0,0758", "0,0701", "le modèle perd"],
    ["Erreur de calibration attendue (ECE, 10 tranches)", "0,0371", "0,0322", "le modèle perd"],
], header=True)
para("En validation 2024, le modèle passait devant (0,0690 contre 0,0727 de MAE pondérée, 0,0030 "
     "contre 0,0141 d'ECE) ; en test 2025 il repasse derrière sur les deux métriques à la fois. La "
     "courbe d'apprentissage (10, 25, 50 et 100 % du volume d'entraînement : 0,0758, 0,0723, "
     "0,0705, 0,0698 de MAE pondérée en validation) établit que ce n'est pas un manque de "
     "données — le gain marginal se divise par deux à chaque doublement du volume — mais une "
     "dérive temporelle entre les sessions d'entraînement (2020-2023) et la session de test "
     "(2025). Le protocole d'évaluation n'a pas été retouché après ce résultat pour le faire "
     "passer : le seuil que le modèle devait battre (0,0701 de MAE pondérée, à couverture égale) "
     "a été écrit avant l'entraînement, dans le document d'évaluation, et le résultat est rapporté "
     "tel qu'il est sorti. C'est ce résultat qui fonde l'avis du délégué à la protection des "
     "données, défavorable à la restitution de cette estimation à des candidats réels tant qu'il "
     "n'est pas corrigé (section 4).")
para("Restitution. L'estimation est présentée comme une fréquence observée et non comme une "
     "prédiction individuelle : « sur cent candidats ayant vos caractéristiques scolaires et "
     "ayant demandé cette formation, tel nombre a reçu une proposition ». Le modèle ne connaît ni "
     "les notes exactes, ni les appréciations, ni la lettre de motivation, alors que la sélection "
     "s'appuie sur l'ensemble du dossier. Cette formulation est écrite dans l'écran de supervision "
     "et servie par l'API (`src/edumatch/api/`, dix-neuf modules, huit fichiers de tests) ; elle "
     "porte en outre la mise en garde issue du résultat ci-dessus, attachée à chaque score produit "
     "plutôt que documentée à part.")

encadre("Justification du choix : exclure le genre du modèle, et pourquoi cela ne coûte rien", [
    "Aucune variable de genre n'entre dans le modèle. Elle est conservée exclusivement pour "
    "l'audit d'équité a posteriori, et les variables susceptibles d'agir comme substituts "
    "(établissement d'origine, académie) sont testées pour corrélation résiduelle.",
    "L'objection habituelle est qu'exclure une variable prédictive dégrade la précision. La "
    "mesure montre qu'il n'en est rien ici. Sur les 11 099 formations recevant au moins trente "
    "vœux de chaque sexe, l'écart médian de taux d'admission entre femmes et hommes est nul, sa "
    "moyenne est de moins d'un demi-point, et il reste inférieur à cinq points dans 83,8 pour "
    "cent des cas.",
    "L'explication est structurelle : la sélection s'appuie sur le dossier scolaire, non sur le "
    "sexe. Le genre agit massivement sur le choix des formations demandées, la ségrégation "
    "décrite en section 1.1, mais quasiment pas sur la probabilité d'être admis une fois le vœu "
    "formulé. L'information est donc déjà portée par la formation demandée et le dossier.",
    "Même si un écart existait, l'utiliser serait exclu. D'une part il s'agirait d'une "
    "discrimination directe dans l'accès à l'éducation. D'autre part le système deviendrait un "
    "amplificateur de ségrégation par effet de boucle : annoncer à un garçon qu'il a moins de "
    "chances dans une filière féminisée le dissuaderait de postuler, renforçant la ségrégation "
    "que le modèle apprendrait l'année suivante.",
])

para("Audit d'équité, conduit sur les prédictions réelles du modèle entraîné "
     "(`models/fairness.py`, E26), sur quatre dimensions : type de baccalauréat, statut de "
     "boursier, genre et territoire. La définition d'équité privilégiée — la calibration par "
     "groupe, un taux prédit de 60 % doit correspondre à un taux observé de 60 % dans chaque "
     "groupe — est déclarée avant la mesure, parce qu'elle est incompatible avec la parité "
     "démographique et les cotes égalisées dès que les taux de base diffèrent entre groupes : "
     "c'est un théorème d'impossibilité, pas un arbitrage de goût.")
table([
    ["Indicateur", "Formations à plus de 80 % de candidates femmes", "Autres formations"],
    ["Ratio d'impact disparate (modèle)", "0,76 — sous le seuil des quatre cinquièmes (0,80)",
     "—"],
    ["Ratio d'impact disparate (plancher)", "0,63", "—"],
    ["Erreur de calibration attendue (ECE)", "0,066", "0,032 à 0,034"],
], header=True)
para("**Le système n'est pas équitable sur cette dimension**, et ce résultat n'est pas atténué : "
     "il fait mieux que le plancher sur la sélection (0,76 contre 0,63) mais moins bien sur la "
     "calibration, où il sur-annonce les chances d'admission sur les formations très féminisées "
     "avec une erreur presque deux fois supérieure à celle mesurée ailleurs. Le travail exploratoire "
     "en amont (section 1.1) avait déjà mesuré que l'établissement d'origine (28,9 % net "
     "d'information mutuelle, corrigée de la cardinalité) et la filière (19,5 % net) sont les "
     "substituts du genre les plus puissants parmi les variables candidates : l'établissement est "
     "exclu du modèle pour cette raison et pour sa cardinalité, la filière est conservée car sa "
     "suppression détruirait la capacité du modèle à distinguer les formations entre elles. "
     "L'audit confirme que l'exclusion de variables à l'entrée ne suffit pas : le dispositif "
     "d'équité du projet repose sur trois niveaux — exclusion du genre à l'entrée, mesure des "
     "substituts, audit a posteriori sur les prédictions — et non sur le seul retrait de "
     "colonnes. La dimension territoriale reste, à ce stade, non pénalisante dans les mesures "
     "conduites ; elle répond à la deuxième cause structurelle identifiée en section 1.2.")

encadre("Justification du choix : l'apport de chaque source est mesuré, non postulé", [
    "Une source de données qui n'est pas réellement utilisée par le modèle finit par paraître "
    "ajoutée artificiellement. Une étude d'ablation à sept variantes (`models/ablation.py`, E27) "
    "mesure ce que chaque bloc de variables apporte réellement, sur la validation 2024.",
    "Le résultat dominant : retirer les 35 variables décalées (dont le taux de la session "
    "précédente) fait passer la MAE pondérée de validation de 0,0698 à 0,1120 (+0,0422) — "
    "l'essentiel de la performance du modèle vient de connaître ce taux, les 45 autres variables "
    "affinent la prédiction sans la porter. Retirer les quatre substituts du genre encore "
    "présents (filière, sélectivité, département, académie) ne coûte que +0,0006 et ne répare "
    "pas l'équité : le ratio d'impact disparate du groupe le plus féminisé se dégrade légèrement "
    "(0,66 à 0,62) plutôt que de s'améliorer, ce qui confirme que l'information reconstituant le "
    "genre est diffuse dans les variables décalées, pas concentrée dans ces quatre colonnes.",
    "**L'apport de Sirene, en revanche, n'a pas pu être mesuré.** La chaîne de nomenclatures "
    "(section 6) ne relie aucune formation Parcoursup à une activité NAF par une clé fiable : "
    "Sirene n'est donc jamais entré dans la table de variables du modèle d'accessibilité, et il "
    "n'existe rien à retirer d'un modèle où cette source n'est pas entrée. Ce n'est pas un "
    "résultat d'apport nul — celui-là a été mesuré, pour les mentions et pour l'établissement "
    "d'origine, et rapporté comme tel — c'est une limite du dispositif, déclarée plutôt que "
    "déguisée en mesure. Le critère d'apport mesuré est donc rempli pour toutes les sources sauf "
    "Sirene, conditionné au rattachement effectif de la chaîne de nomenclatures.",
])

para("Intégration. Le modèle est exposé par une API FastAPI conteneurisée (`src/edumatch/api/`, "
     "dix-neuf modules, huit fichiers de tests dont un consacré à la sécurité) : gestion des "
     "erreurs dédiée, authentification, limitation de débit, en-têtes de sécurité. Les "
     "recommandations alimentent l'écran de supervision consulté par les conseillers "
     "d'orientation, qui matérialise l'exigence de contrôle humain posée par l'article 14 du "
     "règlement sur l'IA : le conseiller y revoit chaque recommandation, la contextualise à "
     "partir du dossier réel de l'élève que le modèle ne connaît pas, et peut l'écarter en "
     "motivant sa décision — écartement bloqué côté client et côté serveur, vérifié par test. "
     "L'accessibilité RGAA de cet écran est couverte par des tests unitaires (structure "
     "sémantique, contraste calculé par la formule WCAG, focus jamais supprimé) et par une "
     "procédure d'audit navigateur écrite ; **cette procédure n'a pas encore été déroulée**, "
     "aucun rapport d'audit n'existe à ce jour.")
para("CI/CD. Trois workflows GitHub Actions sont écrits dans le second dépôt "
     "(`edumatch-cicd`) : intégration (lint et tests), construction et publication d'images "
     "étiquetées par l'empreinte du commit, déploiement délibéré et non automatique. "
     "**Aucun de ces workflows n'a encore été exécuté** : une première exécution reste à "
     "déclencher pour révéler ce qu'un YAML non testé cache toujours. Le suivi d'expériences "
     "avec MLflow est en service (cinq exécutions tracées, paramètres et métriques), mais le "
     "registre de modèles proprement dit est vide à ce jour — aucune version n'y est encore "
     "enregistrée. Deux dépôts de code distincts existent, sans recouvrement : la solution IA "
     "(ce dépôt) et l'intégration-déploiement (36 fichiers : workflows, Terraform, manifestes "
     "Kubernetes, monitoring).")
para("Dérive, mesurée sur des données réelles (E34) : l'indice de stabilité de population "
     "(PSI) et le test de Kolmogorov-Smirnov sont calculés directement sur les six sessions où "
     "le label existe (2020-2025), pour trois familles distinctes — variables, cible, "
     "prédictions du modèle. Evidently a été écarté : sa dernière version compatible avec le "
     "reste du projet entraîne un conflit de dépendance transitive avec le paquet dont FastAPI "
     "dépend déjà, reproduit et non contourné (ADR 0018). Le seuil de 0,20 s'applique à la "
     "médiane du PSI des variables plutôt qu'à leur maximum, pour ne pas déclencher en "
     "permanence sur deux colonnes de nomenclature instable sans rapport avec la performance du "
     "modèle. Ce que cette mesure ne permet pas de conclure est écrit dans la décision, et c'est "
     "l'un des quatre résultats défavorables du projet à retenir : **le PSI à ce seuil n'aurait "
     "pas signalé la dégradation pourtant observée entre validation et test.** Il s'agit d'une "
     "dérive du concept — la relation entre les variables et la cible change alors que la "
     "distribution des entrées bouge à peine — à laquelle un indice de stabilité de population, "
     "qui ne compare que des distributions marginales, est aveugle par construction. "
     "Réentraînement, à construire : la détection journalise un avertissement mais ne déclenche "
     "encore rien, l'automatisation reste à coupler à l'orchestrateur. Le monitoring en "
     "production (Prometheus, Grafana, SLO déclaré sur la latence p95 et la disponibilité) est "
     "écrit et versionné dans le second dépôt, mais rien n'en a jamais tourné en production.")
para("À livrer à terme : rapport d'audit RGAA exécuté, première exécution de la chaîne "
     "d'intégration capturée, entraînement ajouté au graphe d'orchestration, modèle enregistré au "
     "registre, et capture vidéo de la solution en production. Présentation de la solution, dépôt "
     "n°1 (développement de la solution IA) et dépôt n°2 (intégration et déploiement continus) "
     "existent déjà, avec du code réel et distinct.", italic=True)

d.add_page_break()

# =====================================================================
# 8. SYNTHÈSE
# =====================================================================
h("8. Synthèse des livrables et soutenance", 1)
table([
    ["Bloc", "Livrables principaux", "Évaluation"],
    ["Bloc 1", "Plan de gouvernance, analyse d'impact, Model Card, registre des sources, slides",
     "Lecture environ 15 min, présentation 15 min, questions 15 min"],
    ["Bloc 2", "Diagrammes C4, code d'infrastructure, vidéo",
     "Lecture environ 20 min, présentation 5 min, questions 15 min"],
    ["Bloc 3", "Diagramme de pipeline, code, vidéo",
     "Lecture environ 20 min, présentation 5 min, questions 15 min"],
    ["Bloc 4", "Slides, dépôt n°1, dépôt n°2, vidéo", "Présentation et questions devant le jury"],
], header=True)
para("Fil conducteur de la soutenance : partir des constats mesurés dans les données publiques. "
     "La ségrégation par le genre est massive alors même que les femmes sont majoritaires parmi "
     "les admis, et l'accès reste inégal selon le baccalauréat d'origine. Puis dérouler la chaîne "
     "complète, de la gouvernance à la solution, en montrant que chaque source répond à une "
     "question précise et qu'un seul composant est appris. Chaque choix est défendu par « X "
     "plutôt que Y parce que… ». Quatre résultats défavorables, mesurés et non atténués, "
     "structurent une part importante de cette défense : le modèle appris ne bat pas le taux de "
     "la session précédente en test (MAE pondérée 0,0758 contre 0,0701, ECE 0,0371 contre 0,0322), "
     "le ratio d'impact disparate sur les formations très féminisées est à 0,76, sous le seuil "
     "légal de 0,80, la couverture du terme de débouchés n'atteint que 1,4 % des lignes, et "
     "l'avis du délégué à la protection des données est scindé, défavorable à la restitution du "
     "terme appris à des candidats réels tant qu'il n'aura pas été corrigé. Chacun de ces "
     "résultats est mesuré, documenté et assumé plutôt que dissimulé, ce qui est présenté comme "
     "une garantie de rigueur plutôt que comme une faiblesse à minimiser.")

# =====================================================================
# 9. AUTOCONTRÔLE
# =====================================================================
h("9. Autocontrôle avant dépôt", 1)
bullets([
    "Le secteur et l'organisation sont décrits : EdTech, startup en amorçage, Île-de-France.",
    "La problématique est établie par la mesure, non par l'intuition : ségrégation de genre "
    "chiffrée et écart d'accès selon le baccalauréat, recalculés sur le fichier source.",
    "Les contraintes forcent de vrais arbitrages : volumétrie, fraîcheur, budget, conformité.",
    "L'environnement technique présente les 3V de façon non triviale, avec trois sources dont les "
    "volumétries sont vérifiées.",
    "Des données personnelles, dont celles de mineurs, sont impliquées avec un enjeu RGPD réel, et "
    "la séparation entraînement / inférence est explicite.",
    "Les parties prenantes sont nommées, dont le DPO et le superviseur humain.",
    "Bloc 1 : gouvernance, rôles, risques, correspondance avec les obligations de l'AI Act, audits.",
    "Bloc 2 : architecture séparée en deux couches, infrastructure, sécurisation, supervision.",
    "Bloc 3 : trois connecteurs, deux chaînes dimensionnées séparément, réconciliation de trois "
    "nomenclatures, automatisation, qualité, supervision.",
    "Bloc 4 : un seul modèle industrialisé, rôle de chaque source explicité, cible et protocole "
    "définis, calibration, courbe d'apprentissage, ablation, équité sur quatre dimensions, CI/CD "
    "écrit, dérive mesurée, deux dépôts de code réel et distinct.",
    "Chaque choix important est justifié selon la forme « X plutôt que Y parce que… ».",
    "Aucune donnée n'est simulée : toutes les sources sont publiques, réelles et sous licence "
    "vérifiée.",
    "Les quatre résultats défavorables du projet sont présents dans le corps du dossier, avec "
    "leurs chiffres et leur diagnostic, et non tus ou relégués en annexe : performance du modèle "
    "sous son plancher en test, ratio d'impact disparate sous le seuil légal, couverture du terme "
    "de débouchés à 1,4 %, avis scindé et défavorable du délégué à la protection des données sur "
    "le terme appris.",
    "Ce qui n'existe pas encore est écrit au futur, sans ambiguïté : déploiement cloud réel, "
    "exécution de la chaîne d'intégration, panne filmée, trois vidéos de production.",
    "Les limites du dispositif sont déclarées, notamment sur la granularité disponible pour "
    "l'audit de genre et sur la portée d'une estimation fondée sur des caractéristiques agrégées.",
    "Forme : document structuré en chapitres, en français, fichier nommé « KIONGHAT Johann ».",
])

d.save(OUT)
print("OK ->", OUT)
