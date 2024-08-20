{{ config( 
  materialized = 'view', 
  tags=['city']
    ) 
}} 

WITH city AS (
    SELECT * FROM {{ ref('stg_city') }} 
), city_name AS(
    SELECT * FROM {{ ref('City_Name') }}
)
SELECT
    a.city_code,
    a.city_name,
    b.city_name city_en,
    a.province_code,
    a.URL
FROM city a 
LEFT JOIN city_name b
    ON (a.city_code = b.city_code)