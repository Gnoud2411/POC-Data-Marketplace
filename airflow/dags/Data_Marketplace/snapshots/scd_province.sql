{% snapshot scd_province %}

{{
    config(
        target_schema='DWH', 
        tags=['province'],
        unique_key='PROVINCE_CODE',    
        strategy='check',        
        check_cols=['PROVINCE_NAME', 'URL'],
        invalidate_hard_deletes=True
    )
}}

WITH province AS (
    SELECT * FROM {{ ref('dim_province') }} 
)
SELECT
    PROVINCE_SEQUENCE.NEXTVAL AS id,
    a.province_code,
    a.province_name,
    a.province_en,
    a.url
FROM province a

{% endsnapshot %}