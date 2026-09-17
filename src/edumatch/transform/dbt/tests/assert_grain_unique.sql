-- Test singulier dbt : le grain de silver est (session, cod_aff_form).
-- Un test dbt réussit quand la requête ne renvoie AUCUNE ligne : celle-ci
-- renvoie les couples dupliqués, hors clé manquante (2018/2019, ADR 0010),
-- une clé manquante n'étant par construction comparable à aucune autre.
--
-- Redondant avec la vérification déjà faite par
-- `edumatch.transform.reconciliation.reconcilier_dataframes` (qui lèverait
-- avant même que ce modèle ne se matérialise) : gardé malgré cette
-- redondance parce que la réconciliation exige des « tests dbt verts », pas seulement une
-- garantie côté Python invisible depuis `dbt test`.
select session, cod_aff_form, count(*) as occurrences
from {{ ref('stg_parcoursup') }}
where cod_aff_form is not null
group by session, cod_aff_form
having count(*) > 1
