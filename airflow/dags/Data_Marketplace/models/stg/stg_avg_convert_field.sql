{{ config( 
  materialized = 'ephemeral', 
  tags=['Wind_Speed']
    ) 
}} 
WITH CONVERT_FIELD AS(
    SELECT 
        INPUT_DATE, PROVINCE_CODE, CITY_CODE,
        TRY_CAST("Barometric_Pressure.Local(hPa)" AS FLOAT) AS "Barometric_Pressure.Local(hPa)",
        TRY_CAST("Barometric_Pressure.Sea_Level(hPa)" AS FLOAT) AS "Barometric_Pressure.Sea_Level(hPa)",
        TRY_CAST("Precipitation(mm)" AS FLOAT) AS "Precipitation(mm)",
        TRY_CAST("Air_Temperature(°C)" AS FLOAT) AS "Air_Temperature(°C)",
        TRY_CAST("Relative_Humidity(%)" AS FLOAT) AS "Relative_Humidity(%)",
        TRY_CAST("Avg_Wind_Speed(m/s)" AS FLOAT) AS "Avg_Wind_Speed(m/s)",
        WIND_DIRECTION_AVG,
        TRY_CAST("Max_Wind_Speed(m/s)" AS FLOAT) AS "Max_Wind_Speed(m/s)",
        WIND_DIRECTION_MAX,
        TRY_CAST("Daylight_Hours(minutes)" AS FLOAT) AS "Daylight_Hours(minutes)"
    FROM {{ source('Raw', 'Weather_Data') }}
)
SELECT
    INPUT_DATE, PROVINCE_CODE, CITY_CODE,
    ROUND(AVG("Barometric_Pressure.Local(hPa)"), 2) AS "Barometric_Pressure.Local(hPa)",
    ROUND(AVG("Barometric_Pressure.Sea_Level(hPa)"), 2) AS "Barometric_Pressure.Sea_Level(hPa)",
    ROUND(AVG("Precipitation(mm)"), 2) AS "Precipitation(mm)",
    ROUND(AVG("Air_Temperature(°C)"), 2) AS "Air_Temperature(°C)",
    ROUND(AVG("Relative_Humidity(%)"), 2) AS "Relative_Humidity(%)",
    ROUND(AVG("Avg_Wind_Speed(m/s)"), 2) AS "Avg_Wind_Speed(m/s)",
    ROUND(AVG("Max_Wind_Speed(m/s)"), 2) AS "Max_Wind_Speed(m/s)",
    ROUND(AVG("Daylight_Hours(minutes)"), 2) AS "Daylight_Hours(minutes)"
FROM CONVERT_FIELD
GROUP BY INPUT_DATE, PROVINCE_CODE, CITY_CODE