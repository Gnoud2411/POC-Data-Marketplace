{% snapshot scd_city %}

{{
    config(
        target_schema='DWH', 
        tags=['city'],
        unique_key='CITY_CODE',    
        strategy='check',        
        check_cols=['CITY_NAME','PROVINCE_CODE', 'URL'],
        invalidate_hard_deletes=True
    )
}}

WITH city AS (
    SELECT * FROM {{ ref('dim_city') }} 
)
SELECT
    CITY_SEQUENCE.NEXTVAL AS id,
    a.CITY_CODE,
    a.CITY_NAME,
    a.CITY_EN,
    a.PROVINCE_CODE,
    a.url
FROM city a

{% endsnapshot %}