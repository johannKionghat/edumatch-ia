#!/usr/bin/env bash
# Vérification des métadonnées des sources — E03.
#
# Interroge uniquement les catalogues (API opendatasoft, API data.gouv), ne
# télécharge jamais les fichiers volumineux (8 CSV Parcoursup, 11 Go Sirene).
# Les référentiels (quelques Mo) sont téléchargés en entier dans $TMP,
# entièrement nettoyé en fin d'exécution (trap) : c'est le seul moyen
# d'obtenir un nombre de lignes exact à cette taille de fichier.
#
# Sortie : un résumé, une ligne par chiffre annoncé dans sources.md.
#
# ⚠️ Le nombre de fiches RNCP/RS (section C) varie d'un jour sur l'autre :
# l'export est republié chaque jour. La commande est stable et reproductible,
# mais son résultat exact est daté du jour d'exécution — il ne "reproduit" pas
# le chiffre figé dans sources.md, il en reproduit la MÉTHODE.
set -euo pipefail

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "== A. Parcoursup — 8 millésimes (API opendatasoft) =="
for id in fr-esr-parcoursup fr-esr-parcoursup_2024 fr-esr-parcoursup_2023 \
          fr-esr-parcoursup_2022 fr-esr-parcoursup_2021 fr-esr-parcoursup_2020 \
          fr-esr-parcoursup-2019 fr-esr-parcoursup-2018; do
  curl -sS "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/$id" \
    -o "$TMP/$id.json"
  python - "$TMP/$id.json" "$id" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
meta = d.get("metas", {}).get("default", {})
print(f"  {sys.argv[2]:28s} records={meta.get('records_count'):6d}  "
      f"champs={len(d.get('fields', [])):3d}  licence={meta.get('license')}  "
      f"modifie={meta.get('modified')}")
PY
done

echo
echo "== Champs communs entre les millésimes (schéma) =="
python - "$TMP" <<'PY'
import json, glob, os, sys
tmp = sys.argv[1]
sets = {}
for f in glob.glob(os.path.join(tmp, "fr-esr-parcoursup*.json")):
    d = json.load(open(f, encoding="utf-8"))
    sets[d["dataset_id"]] = {fld["name"] for fld in d.get("fields", [])}
common_2020_2025 = sets["fr-esr-parcoursup_2020"] & sets["fr-esr-parcoursup"]
common_all = set.intersection(*sets.values())
print(f"  Champs communs 2020<->2025 : {len(common_2020_2025)}")
print(f"  Champs communs sur les 8 sessions : {len(common_all)}")
PY

echo
echo "== B. Sirene — catalogue data.gouv (aucun téléchargement du fichier) =="
curl -sS "https://www.data.gouv.fr/api/1/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/" \
  -o "$TMP/sirene.json"
python - "$TMP/sirene.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"  frequence={d.get('frequency')}  derniere_publication={d.get('last_update')}  licence={d.get('license')}")
retenus4 = 0
tous_zip = 0
tous_parquet = 0
for r in d.get("resources", []):
    title = (r.get("title") or "").lower()
    size = r.get("filesize") or 0
    fmt = r.get("format")
    if "stock" in title and fmt == "zip":
        tous_zip += size
    if "stock" in title and fmt == "parquet":
        tous_parquet += size
        if any(s in title.replace(" ", "") for s in
               ("stocketablissement-", "stocketablissementhistorique",
                "stockunitelegale-", "stockunitelegalehistorique")):
            retenus4 += size
print(f"  Somme zip (6 fichiers stock)     : {tous_zip/1e9:.2f} Go decimal")
print(f"  Somme parquet (6 fichiers stock) : {tous_parquet/1e9:.2f} Go decimal")
print(f"  Somme parquet (4 fichiers retenus, hors succession/doublons) : {retenus4/1e9:.2f} Go decimal")
PY

echo
echo "== C. Référentiels ONISEP — téléchargement complet (15,9 Mo, dans \$TMP) =="
for pair in \
  "ideo-formations|https://api.opendata.onisep.fr/downloads/5fa591127f501/5fa591127f501.csv" \
  "ideo-metiers|https://api.opendata.onisep.fr/downloads/5fa5949243f97/5fa5949243f97.csv" \
  "ideo-structures-secondaire|https://api.opendata.onisep.fr/downloads/5fa5816ac6a6e/5fa5816ac6a6e.csv" \
  "ideo-structures-superieur|https://api.opendata.onisep.fr/downloads/5fa586da5c4b6/5fa586da5c4b6.csv" \
  ; do
  name="${pair%%|*}"; url="${pair##*|}"
  out="$TMP/$name.csv"
  curl -sS "$url" -o "$out"
  lignes=$(($(wc -l < "$out") - 1))
  colonnes=$(head -1 "$out" | tr ';' '\n' | wc -l)
  echo "  $name : $lignes lignes de données, $colonnes colonnes"
done

echo
echo "== C. RNCP/RS — résolution dynamique de l'export du jour (aucune date en dur) =="
curl -sS "https://www.data.gouv.fr/api/1/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique/" \
  -o "$TMP/rncp.json"
python - "$TMP/rncp.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"  RNCP/RS  frequence={d.get('frequency')}  licence={d.get('license')}  "
      f"nb_ressources={len(d.get('resources', []))} (un export quotidien horodate)")
PY

# Résout l'URL de la ressource "export-fiches-csv-*.zip" la plus récente,
# sans jamais coder la date du jour en dur : c'est l'API qui la donne.
RNCP_URL=$(python - "$TMP/rncp.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
candidates = [
    r for r in d.get("resources", [])
    if (r.get("title") or "").startswith("export-fiches-csv-") and r.get("format") == "zip"
]
candidates.sort(key=lambda r: r.get("last_modified") or "", reverse=True)
print(candidates[0]["url"] if candidates else "")
PY
)

if [ -z "$RNCP_URL" ]; then
  echo "  Aucune ressource export-fiches-csv-*.zip trouvée aujourd'hui — export RNCP non vérifiable."
else
  echo "  Ressource résolue aujourd'hui : $RNCP_URL"
  curl -sS "$RNCP_URL" -o "$TMP/rncp_csv.zip"
  unzip -o -q "$TMP/rncp_csv.zip" -d "$TMP/rncp_csv"
  STANDARD=$(ls "$TMP"/rncp_csv/export_fiches_CSV_Standard_*.csv 2>/dev/null | head -1)
  if [ -z "$STANDARD" ]; then
    echo "  Fichier export_fiches_CSV_Standard_*.csv introuvable dans l'archive du jour."
  else
    total=$(($(wc -l < "$STANDARD") - 1))
    actives=$(grep -c '"ACTIVE"' "$STANDARD")
    colonnes=$(head -1 "$STANDARD" | tr ';' '\n' | wc -l)
    echo "  Fichier : $(basename "$STANDARD")"
    echo "  $total fiches au total, $actives actives, $colonnes colonnes"
    echo "  ⚠️ Ce chiffre est daté du jour d'exécution — l'export RNCP/RS est republié"
    echo "     chaque jour, le nombre de fiches variera d'une exécution à l'autre."
  fi
fi

echo
echo "Vérification terminée. Comparer ces chiffres à docs/sous-docs-projets/01-donnees/sources.md."
