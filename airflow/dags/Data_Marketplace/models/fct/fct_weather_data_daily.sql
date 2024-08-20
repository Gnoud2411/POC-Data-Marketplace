{{
    config(
        materialized = 'incremental', 
        tags=['Wind_Speed'],
        on_schema_change = 'fail',
        )
}}

WITH Wind_Speed AS (
    SELECT * FROM {{ref('stg_wind_speed')}}
), AVG_Convert_Field AS(
    SELECT * FROM {{ref('stg_avg_convert_field')}}
)
SELECT 
    WEATHER_DAILY_SEQUENCE.NEXTVAL AS ID,
    a.*, b.WIND_DIRECTION_AVG, b.WIND_DIRECTION_MAX
FROM AVG_Convert_Field a 
INNER JOIN Wind_Speed b 
ON a.INPUT_DATE = b.INPUT_DATE
    AND a.PROVINCE_CODE = b.PROVINCE_CODE
    AND a.CITY_CODE = b.CITY_CODE
{% if is_incremental() %}
WHERE a.INPUT_DATE > (SELECT MAX(INPUT_DATE) FROM {{this}})
{% endif %}