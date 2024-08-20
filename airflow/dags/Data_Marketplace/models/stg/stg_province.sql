{{ config( 
  materialized = 'ephemeral', 
  tags=['province']
    ) 
}} 

WITH scr_province AS(
    SELECT * FROM {{ source('Raw', 'Province') }}
)
SELECT 
    *
FROM scr_province