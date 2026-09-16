#!/usr/bin/env bash
# Démonstration filmée de l'arrêt définitif (critère 3.12, ADR 0019, section
# « 2. Arrêt définitif : contrôle qualité bloquant »).
#
# Ce script rejoue, sur des données réelles, exactement la panne que
# `tests/integration/test_pipeline_enchainement.py::test_panne_qualite_arrete_la_chaine_avant_la_transformation`
# démontre déjà sur des échantillons : la colonne `fili` — membre de la liste
# blanche `session_courante` (configs/base.yaml, protection anti-fuite) —
# disparaît du millésime Parcoursup le plus récent. `controler_qualite`
# (src/edumatch/quality/parcoursup.py) la détecte comme un manque de schéma,
# lève `ErreurQualiteBloquante` (définitive : aucune reprise, voir
# `orchestration/reprise.py`), et le DAG `edumatch_parcoursup` place toutes
# les tâches en aval en `upstream_failed` sans code supplémentaire — c'est la
# règle de déclenchement par défaut d'un opérateur Airflow (`all_success`).
#
# La panne est RÉVERSIBLE et sa réversibilité est VÉRIFIÉE, pas supposée :
# avant l'injection, l'empreinte SHA-256 du fichier est comparée à celle
# déjà enregistrée dans le manifeste d'ingestion — sans cette égalité, il n'y
# a pas d'état de départ connu à restaurer, et le script refuse d'aller plus
# loin. Après restauration, la même empreinte est recalculée et comparée à
# nouveau : la restauration n'est annoncée que si les deux empreintes
# coïncident bit à bit, jamais sur la seule foi d'une copie de fichier
# réussie.
#
# Usage :
#   scripts/demo_panne_qualite.sh declencher   # sauvegarde puis corrompt
#   scripts/demo_panne_qualite.sh restaurer    # restaure et vérifie l'empreinte
#
# Aucun secret ici, aucun chemin en dur : EDUMATCH_DATA_ROOT (par défaut,
# /srv/edumatch/data — le point de montage documenté par le cloud-init de
# l'instance Airflow, terraform/airflow.tf côté edumatch-cicd) porte le seul
# chemin variable de ce script.
set -euo pipefail

DONNEES_RACINE="${EDUMATCH_DATA_ROOT:-/srv/edumatch/data}"
DOSSIER_PARCOURSUP="${DONNEES_RACINE}/raw/parcoursup"
CHEMIN_MANIFESTE="${DOSSIER_PARCOURSUP}/manifeste.json"
DOSSIER_SAUVEGARDE="${DONNEES_RACINE}/.demo-panne-qualite"
COLONNE_RETIREE="fili"

usage() {
  cat >&2 <<USAGE
Usage : $(basename "$0") {declencher|restaurer}

  declencher   Vérifie l'état de départ contre le manifeste, sauvegarde le
               millésime Parcoursup le plus récent, puis retire la colonne
               '${COLONNE_RETIREE}' pour provoquer un échec bloquant de
               controler_qualite.

  restaurer    Remet le fichier sauvegardé en place et VÉRIFIE par empreinte
               SHA-256, contre le manifeste, que la restauration est exacte.
               Échoue bruyamment (code de sortie non nul) si ce n'est pas
               le cas — jamais un succès supposé.

Variable d'environnement lue : EDUMATCH_DATA_ROOT (par défaut /srv/edumatch/data).
USAGE
}

exiger_commande() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERREUR : commande '$1' introuvable. $2" >&2
    exit 1
  }
}

empreinte_sha256() {
  # coreutils (sha256sum) est présent par défaut sur l'image Ubuntu LTS de
  # l'instance ; pas de repli silencieux vers un autre outil qui calculerait
  # autre chose sans le dire.
  sha256sum "$1" | cut -d' ' -f1
}

empreinte_attendue_manifeste() {
  local millesime="$1"
  python3 - "$CHEMIN_MANIFESTE" "$millesime" <<'PY'
import json
import sys

chemin_manifeste, millesime = sys.argv[1], sys.argv[2]
with open(chemin_manifeste, encoding="utf-8") as flux:
    manifeste = json.load(flux)
entree = manifeste.get(millesime)
if entree is None or "empreinte_sha256" not in entree:
    print(f"ERREUR : aucune entree '{millesime}' avec empreinte_sha256 dans {chemin_manifeste}.", file=sys.stderr)
    sys.exit(1)
print(entree["empreinte_sha256"])
PY
}

millesime_le_plus_recent() {
  # shellcheck disable=SC2012
  ls "${DOSSIER_PARCOURSUP}"/parcoursup_*.csv 2>/dev/null \
    | sed -E 's/.*parcoursup_([0-9]{4})\.csv$/\1/' \
    | sort -n | tail -n1
}

declencher() {
  exiger_commande sha256sum "requis pour vérifier l'intégrité avant/après injection."
  exiger_commande python3 "requis pour lire le manifeste JSON et retirer la colonne de façon fiable (respect du quotage CSV, comme csv.DictReader)."

  [[ -f "$CHEMIN_MANIFESTE" ]] || {
    echo "ERREUR : manifeste introuvable ($CHEMIN_MANIFESTE). L'ingestion Parcoursup a-t-elle tourné (DAG edumatch_parcoursup, tâche ingerer_parcoursup) ?" >&2
    exit 1
  }

  local millesime fichier attendue actuelle
  millesime="$(millesime_le_plus_recent)"
  [[ -n "$millesime" ]] || {
    echo "ERREUR : aucun fichier parcoursup_*.csv sous $DOSSIER_PARCOURSUP." >&2
    exit 1
  }
  fichier="${DOSSIER_PARCOURSUP}/parcoursup_${millesime}.csv"

  if [[ -f "${DOSSIER_SAUVEGARDE}/millesime_courant" ]]; then
    echo "ERREUR : une sauvegarde existe déjà (${DOSSIER_SAUVEGARDE}). Une panne est-elle déjà en cours ? Lancer 'restaurer' avant de rejouer 'declencher'." >&2
    exit 1
  fi

  attendue="$(empreinte_attendue_manifeste "$millesime")"
  actuelle="$(empreinte_sha256 "$fichier")"
  if [[ "$actuelle" != "$attendue" ]]; then
    echo "ERREUR : $fichier ne correspond pas au manifeste AVANT toute injection (actuelle=$actuelle, attendue=$attendue)." >&2
    echo "Abandon volontaire : sans un état de départ connu, la restauration ne pourrait pas être prouvée. Rien n'a été modifié." >&2
    exit 1
  fi

  mkdir -p "$DOSSIER_SAUVEGARDE"
  cp -p "$fichier" "${DOSSIER_SAUVEGARDE}/parcoursup_${millesime}.csv.original"
  printf '%s' "$millesime" > "${DOSSIER_SAUVEGARDE}/millesime_courant"
  printf '%s' "$attendue" > "${DOSSIER_SAUVEGARDE}/empreinte_originale"

  # Retire la colonne de la liste blanche via le module csv (pas un
  # découpage naïf sur ';' : plusieurs colonnes Parcoursup contiennent du
  # texte libre qui peut lui-même porter des points-virgules entre
  # guillemets — un découpage naïf couperait ces lignes au mauvais endroit).
  python3 - "$fichier" "$COLONNE_RETIREE" <<'PY'
import csv
import sys

chemin, colonne = sys.argv[1], sys.argv[2]
with open(chemin, "r", encoding="utf-8-sig", newline="") as flux:
    lignes = list(csv.DictReader(flux, delimiter=";"))
if not lignes:
    print(f"ERREUR : {chemin} est vide, rien à corrompre.", file=sys.stderr)
    sys.exit(1)
if colonne not in lignes[0]:
    print(f"ERREUR : colonne '{colonne}' absente de l'entête de {chemin}.", file=sys.stderr)
    sys.exit(1)
colonnes_restantes = [c for c in lignes[0].keys() if c != colonne]
with open(chemin, "w", encoding="utf-8-sig", newline="") as flux:
    ecrivain = csv.DictWriter(flux, fieldnames=colonnes_restantes, delimiter=";", extrasaction="ignore")
    ecrivain.writeheader()
    ecrivain.writerows(lignes)
PY

  echo "Injection faite : colonne '${COLONNE_RETIREE}' retirée de ${fichier} (millésime ${millesime})."
  echo "Sauvegarde conservée sous ${DOSSIER_SAUVEGARDE}/ en vue de 'restaurer'."
  echo
  echo "Déclencher maintenant le DAG edumatch_parcoursup, par exemple :"
  echo "  docker compose -f docker-compose.prod.yml exec airflow-scheduler airflow dags trigger edumatch_parcoursup"
  echo "La tâche controler_qualite doit échouer sans reprise (ErreurQualiteBloquante, journal de la tâche) ;"
  echo "transformer_silver, construire_gold et construire_variables doivent apparaître en upstream_failed."
}

restaurer() {
  exiger_commande sha256sum "requis pour vérifier l'intégrité de la restauration."
  exiger_commande python3 "requis pour relire le manifeste JSON."

  [[ -f "${DOSSIER_SAUVEGARDE}/millesime_courant" ]] || {
    echo "ERREUR : aucune sauvegarde trouvée sous ${DOSSIER_SAUVEGARDE}. Rien à restaurer (la panne a-t-elle été déclenchée avec 'declencher') ?" >&2
    exit 1
  }

  local millesime attendue_sauvegarde attendue_manifeste fichier sauvegarde actuelle
  millesime="$(cat "${DOSSIER_SAUVEGARDE}/millesime_courant")"
  attendue_sauvegarde="$(cat "${DOSSIER_SAUVEGARDE}/empreinte_originale")"
  fichier="${DOSSIER_PARCOURSUP}/parcoursup_${millesime}.csv"
  sauvegarde="${DOSSIER_SAUVEGARDE}/parcoursup_${millesime}.csv.original"

  [[ -f "$sauvegarde" ]] || {
    echo "ERREUR : fichier de sauvegarde introuvable ($sauvegarde). Restauration impossible depuis ce script." >&2
    exit 1
  }

  cp -p "$sauvegarde" "$fichier"
  actuelle="$(empreinte_sha256 "$fichier")"
  attendue_manifeste="$(empreinte_attendue_manifeste "$millesime")"

  if [[ "$actuelle" != "$attendue_sauvegarde" || "$actuelle" != "$attendue_manifeste" ]]; then
    echo "ERREUR : restauration NON vérifiée." >&2
    echo "  empreinte obtenue      : $actuelle" >&2
    echo "  attendue (sauvegarde)  : $attendue_sauvegarde" >&2
    echo "  attendue (manifeste)   : $attendue_manifeste" >&2
    echo "Ne pas considérer la démonstration comme terminée. Le fichier de sauvegarde est conservé pour investigation." >&2
    exit 1
  fi

  rm -f "$sauvegarde" "${DOSSIER_SAUVEGARDE}/millesime_courant" "${DOSSIER_SAUVEGARDE}/empreinte_originale"
  echo "Restauration VÉRIFIÉE : ${fichier} identique octet pour octet à l'état déclaré dans le manifeste (SHA-256 ${actuelle})."
  echo "Relancer la chaîne (par exemple 'airflow dags trigger edumatch_parcoursup', ou 'Clear' sur l'exécution en échec) : elle doit désormais aller jusqu'au bout."
}

case "${1:-}" in
  declencher) declencher ;;
  restaurer) restaurer ;;
  *) usage; exit 1 ;;
esac
