"""Index de similarité lexicale (TF-IDF) sur le corpus documentaire.

## Le choix, et son seuil de bascule

Le corpus indexé aujourd'hui tient en quelques milliers de lignes (5 869
formations et 1 534 métiers IDÉO, voir `corpus.py`). Un `TfidfVectorizer`
(`scikit-learn`, dépendance déjà présente dans le projet depuis
`models/train.py`) construit et interroge cet index en quelques
millisecondes, sans modèle d'embeddings à charger ni base vectorielle à
opérer.

Un index vectoriel dense (embeddings + FAISS ou équivalent) apporterait un
gain de rappel sur des questions formulées très différemment du vocabulaire
du référentiel (synonymes, paraphrase) — mais ce gain n'est pas mesuré ici,
et son coût est réel : un modèle supplémentaire à télécharger et versionner,
une dépendance GPU/CPU plus lourde, et une base vectorielle à opérer pour un
volume qui ne l'exige pas. **Ce qui ferait reconsidérer ce choix** : un
corpus documentaire qui dépasserait l'ordre du million de lignes, ou une
mesure montrant qu'une part significative des questions réelles n'obtient
aucun résultat pertinent en similarité lexicale.

## La limite qui subsiste, mesurée

Retirer les mots vides (voir `MOTS_VIDES`) suffit à refuser une question hors
sujet, mais pas à comprendre un synonyme : « je veux travailler dans la data »
ne rapproche pas « données », et une question sur le fonctionnement du système
lui-même obtient des formations, puisque le corpus n'en parle pas. Ces deux
limites tiennent à la nature lexicale de l'index, pas à son réglage.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.sparse import spmatrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from edumatch.rag.corpus import Document


class ErreurIndexRag(RuntimeError):
    """L'index ne peut pas être construit — corpus vide, notamment."""


@dataclass(frozen=True)
class IndexDocumentaire:
    """Un vectoriseur ajusté sur le corpus, sa matrice creuse (un document par ligne), et les
    documents dans le même ordre que les lignes de la matrice."""

    vectoriseur: TfidfVectorizer
    matrice: spmatrix
    documents: tuple[Document, ...]


@dataclass(frozen=True)
class ResultatRecherche:
    document: Document
    score: float


# Mots vides du français, retirés de l'index et des questions.
#
# Mesuré avant de les retirer : la question « Quelle est la recette du gâteau au chocolat ? »,
# entièrement hors sujet, obtenait un score de 0,223 — plus élevé que « Je veux travailler dans
# la data, quelle licence choisir ? » (0,218), qui est légitime. Aucun seuil ne pouvait les
# séparer. La similarité de la question absurde venait du terme « est » (0,213 à lui seul), qui
# correspondait au « Est » de « EGC Centre Est » : un nom propre. Sans cette liste, le refus
# documenté par `assistant.py` ne se déclenchait que sur du charabia, jamais sur une phrase
# française hors sujet.
#
# Après retrait, mesuré sur le même corpus : la question absurde tombe à 0,000 (donc refusée),
# la question pertinente monte de 0,323 à 0,360. Liste explicite plutôt qu'une dépendance
# supplémentaire pour quelques dizaines de mots — et elle se lit, donc elle se discute.
MOTS_VIDES: tuple[str, ...] = (
    "a", "au", "aux", "avec", "c", "ce", "ces", "d", "dans", "de", "des", "du", "elle", "en",
    "es", "est", "et", "etait", "ete", "eux", "il", "j", "je", "l", "la", "le", "les", "leur",
    "lui", "m", "ma", "mais", "me", "meme", "mes", "moi", "mon", "n", "ne", "nos", "notre",
    "nous", "on", "ou", "par", "pas", "pour", "qu", "que", "quel", "quelle", "quelles", "quels",
    "qui", "s", "sa", "se", "ses", "soit", "son", "sont", "suis", "sur", "t", "ta", "te", "tes",
    "toi", "ton", "tu", "un", "une", "vos", "votre", "vous", "y",
)


def construire_index(documents: list[Document]) -> IndexDocumentaire:
    if not documents:
        raise ErreurIndexRag(
            "Corpus vide : impossible de construire un index (aucun document IDÉO chargé). "
            "Voir corpus.charger_corpus_depuis_settings."
        )
    # `strip_accents="unicode"` : une question posée sans accents ("formation comptabilite")
    # doit tout de même retrouver les passages accentués du référentiel. Les vecteurs TF-IDF
    # sont L2-normalisés par défaut : `linear_kernel` (produit scalaire) équivaut donc
    # exactement à la similarité cosinus, sans normalisation supplémentaire à faire ici.
    vectoriseur = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        stop_words=list(MOTS_VIDES),
    )
    matrice = vectoriseur.fit_transform([document.texte for document in documents])
    return IndexDocumentaire(vectoriseur=vectoriseur, matrice=matrice, documents=tuple(documents))


def rechercher(index: IndexDocumentaire, question: str, top_k: int) -> list[ResultatRecherche]:
    """Les `top_k` documents les plus proches de `question`, triés par score décroissant.

    Un score nul (aucun terme en commun avec le corpus) n'est jamais
    retourné : il ne représente aucune similarité réelle, seulement l'absence
    de recouvrement lexical, et laisserait croire à un passage pertinent là
    où il n'y en a aucun.
    """
    if not question or not question.strip():
        return []
    vecteur_question = index.vectoriseur.transform([question])
    scores = linear_kernel(vecteur_question, index.matrice).ravel()
    ordre = scores.argsort()[::-1][:top_k]
    return [ResultatRecherche(document=index.documents[i], score=float(scores[i])) for i in ordre if scores[i] > 0]
