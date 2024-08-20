{{
    config(
        materialized = 'incremental', 
        tags=['Weather_Data'],
        on_schema_change = 'fail',
        )
}}

WITH Weather_Data AS (
    SELECT * FROM {{ref('stg_weather_data')}}
)
SELECT 
    WEATHER_SEQUENCE.NEXTVAL AS id,
    *
FROM Weather_Data
{% if is_incremental() %}
    WHERE INPUT_DATE > (SELECT MAX(INPUT_DATE) FROM {{this}})
{% endif %}