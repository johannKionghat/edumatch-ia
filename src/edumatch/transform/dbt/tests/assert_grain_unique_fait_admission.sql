-- Test singulier dbt : le grain de fait_admission est (session, sk_formation, sk_profil),
-- reflet de (session, cod_aff_form, type_bac, boursier) une fois les dimensions résolues.
-- Un test dbt réussit quand la requête ne renvoie AUCUNE ligne.
--
-- Redondant avec la vérification déjà faite par
-- `edumatch.transform.etoile.construire_fait_admission` (qui lèverait
-- `ErreurEtoile` avant même que ce modèle ne se matérialise) : gardé pour la
-- même raison que `assert_grain_unique.sql` côté silver — le modèle en étoile exige un
-- lignage et des tests dbt verts, pas seulement une garantie invisible
-- depuis `dbt test`.
select session, sk_formation, sk_profil, count(*) as occurrences
from {{ ref('fait_admission') }}
group by session, sk_formation, sk_profil
having count(*) > 1
