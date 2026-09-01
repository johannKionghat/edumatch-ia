"""Index de similarité lexicale (TF-IDF) sur le corpus documentaire (E32).

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
    vectoriseur = TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2))
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
