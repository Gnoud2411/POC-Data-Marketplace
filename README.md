# POC-Data-Marketplace
## Build a data pipeline to extract weather data and create a temperature prediction model for the next 3 days
![Architectural Description](documents/POC_Data_Marketplace-Architect_vr2.drawio.png)

# Overview of the Data Pipeline for Weather Data Extraction and Temperature Prediction Model

In this article, I will provide an overview of the process for implementing a Data Pipeline that extracts weather data and creates a model to predict temperatures for the next three days. The weather data I process is updated daily from a specific website at the end of each day. Therefore, I use Batch Processing to collect this data.

Since the processing flow involves multiple steps, I have split it into two separate DAG files for coordination.

## First DAG - Extraction_Weather_Data: Data Collection and Processing

The first DAG is responsible for the following tasks:

1. **Calling REST API:** Using the POST method of AWS API Gateway to send a request to a Lambda Function. In this Lambda function, I use the Requests library to send a GET request to retrieve weather data for a specified day. I then use AWS SDK (boto3) to create a new session, employ the StringIO library to store the file in RAM, and subsequently upload it to Amazon S3. For simplicity, the Lambda function is granted S3FullAccess.

2. **File Existence Check:** Since the timeout for calling the Lambda function via AWS API Gateway is only 29 seconds, I added a task using an AWS Sensor to check if the file has been processed by the Lambda Function and is available in Amazon S3. The sensor checks every 30 seconds with a timeout of 600 seconds. The subsequent tasks are executed only if the file exists.

3. **Data Transformation:** The data is processed in Snowflake, where I use three schemas:
    - **Schema RAW:** Stores raw data in the Staging layer.
    - **Schema DWH:** Stores normalized data in the Golden Layer.
    - **Schema Public:** Stores data for the Training Model in the Data Product layer.
    - The daily weather data is divided into 10-minute intervals and stored in the `RAW_Data_Weather` table. dbt is responsible for transforming the data and saving it in the `FCT_Data_Weather` table in the DWH schema. I then create an additional model to calculate the daily average metrics from the new data in the `FCT_Data_Weather` table and save it in the `Fct_Weather_Data_Daily` table. The purpose of this table is to prepare data for the Training Model.
    - The Fact tables in the DWH Schema are all FA tables (Fact Append) with the key being `Input_Date`, meaning that during the Transform step, dbt will only extract records from the source table with `Input_Date` values greater than the maximum `Input_Date` value in the destination table.

## Second DAG - Training_Model: Model Training

After completing the tasks in the first DAG, I create a new task to trigger the second DAG, which primarily focuses on Training the Model. The tasks in this DAG mainly involve calling Procedures in Snowflake, with UDFs written in Python for ease of use.

1. **Data Extraction:** The last 10 days of data in the `Fct_Weather_Data_Daily` table are extracted to prepare for the Training Model and saved into the `Prepared_Data` table in **`Overwrite`** mode.

2. **Model Training:** A Random Forest model from the scikit-learn library is used to predict weather data for the next three days. The prediction results are overwritten into the `Prediction_Data` table.

3. **Merging Results:** Finally, I create a Procedure in Snowflake using the Merge function to combine the `Prediction_Data` and `Data_Product` tables. The `Data_Product` table stores the prediction results and is published on Snowflake's Data Marketplace. The actual data in the `Prepared_Data` table is also updated into the `Data_Product` table to ensure accuracy, with the predicted data in the `Data_Product` table being replaced by the actual data from the `Prepared_Data` table.

## Error Handling and Improvements

To handle issues with faulty daily data, I have implemented two solutions:

1. **Send Email Notifications When DAG Fails:** This helps to promptly address errors.
2. **Use Backfill:** To retrieve faulty data. I use the `End_Interval_Date` variable in Airflow as an input parameter to ensure the data remains accurate when passing the parameters back to the Lambda Function.

## Additional DAGs: Extraction_City and Extraction_Province

Here is the link I use to call the REST API for retrieving weather data:
[Weather Data API Link](https://www.data.jma.go.jp/obd/stats/etrn/view/10min_s1.php?prec_no=44&block_no=47675&year=2024&month=1&day=1&view=)

It requires two additional parameters: `Prec_no` (Province_code) and `Block_No` (City_code). To ensure these parameters are correctly extracted in each DAG execution and to use dbt to create SCD2 tables, I have created two additional DAGs.

The `Prec_no` and `Block_No` parameters used by the `Extraction_Weather_Data` DAG are retrieved from the `SCD_CITY` table with records having `Status = 1` (in use).

These two DAGs have a simple execution logic as follows:

1. **Web Scraping:** Using Lambda to scrape HTML and extract the necessary information.
2. **Data Storage:** Using StringIO to store the data in RAM and upload it to S3.
3. **Copy Data:** Data from S3 is copied into the RAW table in Snowflake.
4. **Create Snapshot:** Using dbt to create a snapshot for the SCD2 table whenever the DAG runs.

### Summary: 
The execution sequence follows this logic:

+ DAG Extraction_Province → DAG Extraction_City → DAG Extraction_Weather_Data → DAG Training_Model
