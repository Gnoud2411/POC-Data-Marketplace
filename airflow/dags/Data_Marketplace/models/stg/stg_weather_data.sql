{{ config( 
  materialized = 'ephemeral', 
  tags=['Weather_Data']
    ) 
}} 

WITH scr_weather_data AS(
    SELECT * FROM {{ source('Raw', 'Weather_Data') }}
)
SELECT 
    *
FROM scr_weather_data