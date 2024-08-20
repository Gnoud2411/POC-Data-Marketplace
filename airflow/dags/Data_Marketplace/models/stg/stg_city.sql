{{ config( 
  materialized = 'ephemeral', 
  tags=['city']
    ) 
}} 

WITH scr_province AS(
    SELECT DISTINCT *
    FROM {{ source('Raw', 'City') }}
    WHERE city_code <> 'N/A'
        AND city_code <> '00'
        AND CITY_CODE <> '47639'
)
SELECT 
    *
FROM scr_province