from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig, DbtTaskGroup, RenderConfig
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from cosmos.profiles import SnowflakeUserPasswordProfileMapping
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow import DAG

from datetime import datetime, timedelta
import requests
import json 
import os


def generate_output_file(city_table, **kwargs):
    data_interval_end = kwargs['data_interval_end'] - timedelta(days=1)
    output_file = f'{city_table}-{data_interval_end.strftime("%Y%m%d")}.csv'
    print(f'Generated output file: {output_file}')
    return output_file

def invoke_lambda(**kwargs):
    ti = kwargs['ti']
    # execution_date = kwargs['data_interval_end'].strftime('%Y-%m-%d')
    output_file = ti.xcom_pull(task_ids='generate_output_file')
    print(output_file)
    payload = {'execution_date': output_file}
    json_payload = json.dumps(payload)
    print(json_payload)
    api_url = f'https://dql87wyic7.execute-api.ap-southeast-2.amazonaws.com/dev?execution_date={output_file}'
    print(api_url)

    headers = {'Content-Type': 'application/json'}
    
    # Thực hiện POST request đến API Gateway
    response = requests.post(api_url, data=json.dumps(json_payload), headers=headers, timeout=300)
    # Kiểm tra response
    if response.status_code == 200:
        print("Lambda function invoked successfully.")
        print("Response:", response.json())
    else:
        print("Failed to invoke Lambda function.")
        print("Response:", response.text)

def Truncate_Raw_Table(raw_table):
    hook = SnowflakeHook(snowflake_conn_id='snowflake_conn_raw')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print('Connected Successfully!')
    query = f"""
        TRUNCATE TABLE {raw_table};
    """
    print(query)
    conn.cursor().execute(query)
    # Đóng kết nối
    cursor.close()
    conn.close()

def copy_csv_to_table(s3_bucket, s3_key, raw_table):
    hook = SnowflakeHook(snowflake_conn_id='snowflake_conn_raw')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print('Connected to Snowflake Successfully!')

    # S3 configurations
    s3_url = f's3://{s3_bucket}/{s3_key}'
    # Lấy AWS credentials từ Airflow Variables
    aws_access_key_id = Variable.get('aws_access_key_id')
    aws_secret_access_key = Variable.get('aws_secret_access_key')

    print(s3_url)

    try:
        # Copy data from S3 to Snowflake table
        copy_query = f"""
        COPY INTO {raw_table}
        FROM '{s3_url}'
        CREDENTIALS = (AWS_KEY_ID='{aws_access_key_id}' AWS_SECRET_KEY='{aws_secret_access_key}')
        FILE_FORMAT = (TYPE = 'CSV', DATE_FORMAT = 'YYYYMMDD', SKIP_HEADER = 1, ENCODING='UTF8')
        FORCE = TRUE;
        """
        print(copy_query)
        conn.cursor().execute(copy_query)
    finally:
        # Đóng kết nối
        cursor.close()
        conn.close()


default_args = {
    'owner': 'Ducky',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 0,  # Số lần thử lại
    'retry_delay': timedelta(minutes=5), 
    'retry_exponential_backoff': True,  # Dùng exponential backoff
    'max_retry_delay': timedelta(minutes=60)
}


profile_config = ProfileConfig(
    profile_name="Data_Marketplace",
    target_name="dev",
    profile_mapping=SnowflakeUserPasswordProfileMapping(
        conn_id="snowflake_conn", 
        profile_args={"database": "POC_DATA_MARKETPLACE", "schema": "DWH"},
    )
)


with DAG(
    dag_id='Scrape_City',
    default_args=default_args,
    schedule_interval= None, # '@daily',
    catchup=False,
) as dag:
    
    Base_URL = 'https://www.data.jma.go.jp/obd/stats/etrn/'
    raw_table = 'RAW_CITY'
    # Thông tin AWS
    s3_bucket = 's3-poc-data-marketplace'
    s3_key = 'City/'

    # Task 1: Tạo tên file
    generate_output_file_task = PythonOperator(
        task_id = 'generate_output_file',
        python_callable = generate_output_file,
        op_kwargs = {'city_table': 'city_table'},
        provide_context=True
    )

    # Task 2: Invoke AWS Lambda Function
    invoke_lambda_task = PythonOperator(
        task_id='invoke_lambda_task',
        python_callable=invoke_lambda,
        provide_context=True
    )

    check_s3_file = S3KeySensor(
    task_id='check_s3_file',
    bucket_name= s3_bucket,
    bucket_key= s3_key + "{{ task_instance.xcom_pull(task_ids='generate_output_file') }}",
    aws_conn_id='aws_conn_poc',
    poke_interval=30,  # Khoảng thời gian chờ giữa các lần kiểm tra (giây)
    timeout=600,  # Thời gian chờ tối đa cho sensor (giây)
    )

    # Task 6: Truncate dữ liệu trong bảng Raw_Province phục vụ cho lần chạy Dag 
    truncate_task = PythonOperator(
        task_id = 'Truncate_Stage_Table',
        python_callable = Truncate_Raw_Table,
        op_kwargs = {'raw_table': raw_table},
        provide_context=True
    )

    copy_into_task = PythonOperator(
        task_id='copy_csv_to_table',
        python_callable = copy_csv_to_table, 
        op_kwargs = {
            's3_bucket': s3_bucket,
            's3_key': s3_key + "{{ task_instance.xcom_pull(task_ids='generate_output_file') }}",
            'raw_table': raw_table
            },
        provide_context=True
    )

    sleep_task = BashOperator(
        task_id="sleep_for_10_seconds",
        bash_command="sleep 10"
    )

    dbt_city_models = DbtTaskGroup(
        group_id="city_models",
        project_config=ProjectConfig("/opt/airflow/dags/Data_Marketplace",),
        execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt_venv/bin/dbt",),
        operator_args={"install_deps": True},
        profile_config=profile_config,
        default_args={"retries": 2},
        render_config=RenderConfig(
            select=["tag:city"],
        )
    )
    
    Trigger_DAG_Task = TriggerDagRunOperator(
    task_id='Trigger_DAG_Weather_Data',
    trigger_dag_id='Weather_Data_Extraction'
    )

    generate_output_file_task >> invoke_lambda_task >> check_s3_file >> truncate_task >> copy_into_task >> sleep_task >> dbt_city_models >> Trigger_DAG_Task
