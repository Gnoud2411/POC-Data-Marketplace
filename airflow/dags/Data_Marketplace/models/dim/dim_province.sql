{{ config( 
  materialized = 'view', 
  tags=['province']
    ) 
}} 

WITH province AS (
    SELECT * FROM {{ ref('stg_province') }} 
), province_name AS(
    SELECT * FROM {{ ref('Province_Name') }} 
)
SELECT
    a.province_code,
    a.province_name,
    b.province_name province_en,
    a.url
FROM province a 
LEFT JOIN province_name b
    ON (a.province_code = b.province_code)
