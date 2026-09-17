#!/usr/bin/env bash
# Vérification de la pile locale.
#
# Interroge la sonde de chaque brique de `docker-compose.yml` et affiche un
# état lisible, une ligne par service : jamais un mur de journaux à
# déchiffrer, une commande qui dit oui ou non. Code de sortie non nul si au
# moins une sonde échoue, pour un usage en script (CI locale, démonstration).
set -uo pipefail

OK=0
KO=0

verifier() {
  local nom="$1" url="$2"
  if curl -sS -f -o /dev/null --max-time 5 "$url"; then
    printf "  [OK]  %-10s %s\n" "$nom" "$url"
    OK=$((OK + 1))
  else
    printf "  [KO]  %-10s %s\n" "$nom" "$url"
    KO=$((KO + 1))
  fi
}

echo "== État de la pile locale (docker compose) =="
verifier "api"     "http://localhost:8000/health"
verifier "mlflow"  "http://localhost:5000"
verifier "airflow" "http://localhost:8080/health"

echo
echo "== PostgreSQL (sonde interne au conteneur, pas de port applicatif à interroger) =="
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-edumatch}" >/dev/null 2>&1; then
  printf "  [OK]  %-10s pg_isready\n" "postgres"
  OK=$((OK + 1))
else
  printf "  [KO]  %-10s pg_isready\n" "postgres"
  KO=$((KO + 1))
fi

echo
echo "== Entraînement (service par lots, pas une sonde HTTP) =="
statut_train="$(docker compose ps --format '{{.Service}} {{.State}} {{.ExitCode}}' train 2>/dev/null || true)"
if [[ "$statut_train" == *"exited 0"* ]]; then
  printf "  [OK]  %-10s terminé avec succès (code 0)\n" "train"
  OK=$((OK + 1))
else
  printf "  [KO]  %-10s %s\n" "train" "${statut_train:-service introuvable}"
  KO=$((KO + 1))
fi

echo
echo "== $OK brique(s) en ordre, $KO en échec =="
[[ "$KO" -eq 0 ]]
