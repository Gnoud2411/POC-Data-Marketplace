from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig, DbtTaskGroup, RenderConfig
from airflow.operators.python_operator import PythonOperator, BranchPythonOperator
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from cosmos.profiles import SnowflakeUserPasswordProfileMapping
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.bash import BashOperator
from email.mime.multipart import MIMEMultipart
from airflow.hooks.base_hook import BaseHook
from email.mime.text import MIMEText
from airflow.models import Variable
from airflow import DAG

from datetime import datetime, timedelta
import pendulum
import requests
import smtplib
import json 

def generate_output_file(**kwargs):
    data_interval_end = kwargs['data_interval_end'] - timedelta(days=1)
    output_file = f'Data_Weather-{data_interval_end.strftime("%Y%m%d")}.csv'
    execution_date = data_interval_end.strftime('%Y/%m/%d')
    print(f'Generated output file: {output_file}')
    print(f'Execution Date: {execution_date}')
    # Push output_file to XCom
    kwargs['ti'].xcom_push(key='output_file', value=output_file)
    kwargs['ti'].xcom_push(key='execution_date', value=execution_date)

def check_inserted(raw_table, **kwargs):
    data_interval_end = kwargs['data_interval_end']
    current_date = data_interval_end - timedelta(days=1)

    # Chuyển đổi sang datetime.date
    current_date = current_date.date()
    print(current_date)
    print(type(current_date))

    hook = SnowflakeHook(snowflake_conn_id='snowflake_conn_raw')
    conn = hook.get_conn()
    cursor = conn.cursor()
    print('Connected Successfully!')
    check_date = f"""
        SELECT MAX(INPUT_DATE) FROM {raw_table};
    """
    print(check_date)

    cursor.execute(check_date)
    max_date_row = cursor.fetchone()
    if max_date_row is not None and max_date_row[0] is not None:
        max_date = max_date_row[0] 
        # Convert biến max_date từ giá trị Datetime thành dạng pendulum.date
        max_date = pendulum.date(max_date.year, max_date.month, max_date.day)
        print(max_date)
        print(type(max_date))
    else:
        print("No results found.")
        max_date = current_date - timedelta(days=2)
    # Đóng kết nối
    cursor.close()
    conn.close()
    # Trả về Task_ID của Task được thực thi tiếp theo
    if current_date <= max_date:
        print('no_new_data task will execute')
        return 'no_new_data' 
    else:
        print('invoke_lambda_task task will execute')
        return 'invoke_lambda_task'

def no_new_data():
    print("Data are inserted, skipping this run")

def invoke_lambda(**kwargs):
    ti = kwargs['ti']
    # execution_date = kwargs['data_interval_end'].strftime('%Y-%m-%d')
    output_file = ti.xcom_pull(task_ids='generate_output_file', key='output_file')
    execution_date = ti.xcom_pull(task_ids='generate_output_file', key='execution_date')

    print(output_file)
    print(execution_date)
    payload = {'execution_date': execution_date,
               'file_name': output_file}
    json_payload = json.dumps(payload)
    print(json_payload)
    
    api_url = f'https://eyzyhdwl8l.execute-api.ap-southeast-2.amazonaws.com/dev?execution_date={execution_date}&file_name={output_file}'
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
        FILE_FORMAT = (TYPE = 'CSV', DATE_FORMAT = 'YYYY-MM-DD', SKIP_HEADER = 1, ENCODING='UTF8')
        FORCE = TRUE;
        """
        print(copy_query)
        conn.cursor().execute(copy_query)
    finally:
        # Đóng kết nối
        cursor.close()
        conn.close()

def task_failure_alert(context):
    # Lấy thông tin từ connection smtp_default
    smtp_conn = BaseHook.get_connection('smtp_default')

    smtp_host = smtp_conn.host
    smtp_port = smtp_conn.port
    smtp_user = smtp_conn.login
    smtp_password = smtp_conn.password

    # Thông tin email
    from_email = smtp_user
    to_email = 'dohung24112002@gmail.com'
    subject = f"Task {context['task_instance'].task_id} in DAG {context['dag_run'].dag_id} failed."
    body = f"""
    Task {context['task_instance'].task_id} in DAG {context['dag_run'].dag_id} has failed.
    DAG: {context['dag_run'].dag_id}
    Task: {context['task_instance'].task_id}
    Execution Time: {context['execution_date']}
    Log URL: {context['task_instance'].log_url}
    """

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        # Kết nối và gửi email
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, to_email, msg.as_string())
        print('Alert email has been sent successfully!')
    except Exception as e:
        print(f'Failed to send alert email. Error: {e}')
    finally:
        server.quit()

default_args = {
    'owner': 'Ducky',
    'depends_on_past': False,
    'start_date': datetime(2023, 12, 31),
    'email': 'dohung24112002@gmail.com',
    'email_on_failure': True,       
    'email_on_retry': False,              
    'retries': 0, 
    'retry_delay': timedelta(minutes=5), 
    'retry_exponential_backoff': True,  # Dùng exponential backoff
    'max_retry_delay': timedelta(minutes=60),
    'on_failure_callback': task_failure_alert, 
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
    dag_id='Weather_Data_Extraction',
    default_args=default_args,
    schedule_interval='@daily', # Muốn chạy dược backfill thì tham số schedule_interval phải khác None
    catchup=False,
) as dag:
    
    raw_table = 'RAW_WEATHER_DATA'

    # Thông tin AWS
    s3_bucket = 's3-poc-data-marketplace'
    s3_key = 'Weather_Data/'

    # Task 1: Tạo Output_File và Execution_Date
    generate_output_file_task = PythonOperator(
        task_id = 'generate_output_file',
        python_callable = generate_output_file
    )

    # Task 2: Check dữ liệu đã tồn tại trong bảng RAW_WEATHER_DATA hay chưa
    is_insertd_task = BranchPythonOperator(
        task_id = 'check_inserted',
        python_callable = check_inserted,
        op_kwargs = {'raw_table': raw_table}
    )

    # Skip lần thực thi này
    no_new_data_task = PythonOperator(
        task_id='no_new_data',
        provide_context=True,
        python_callable=no_new_data,
        trigger_rule=TriggerRule.ONE_SUCCESS
    )

    # # Task 2: Invoke AWS Lambda Function
    # invoke_lambda_task = PythonOperator(
    #     task_id='invoke_lambda_task',
    #     python_callable=invoke_lambda,
    #     provide_context=True
    # )

    # check_s3_file = S3KeySensor(
    #     task_id='check_s3_file',
    #     bucket_name= s3_bucket,
    #     bucket_key=s3_key + "{{ task_instance.xcom_pull(task_ids='generate_output_file', key='output_file') }}",
    #     aws_conn_id='aws_conn_poc',
    #     poke_interval=30,
    #     timeout=600, 
    #     )

    # # Task 6: Copy dữ liệu từ Stage vào bảng RAW_WEATHER_DATA
    # copy_into_task = PythonOperator(
    #     task_id='copy_csv_to_table',
    #     python_callable = copy_csv_to_table, 
    #     op_kwargs = {
    #         's3_bucket': s3_bucket,
    #         's3_key': s3_key + "{{ task_instance.xcom_pull(task_ids='generate_output_file', key='output_file') }}",
    #         'raw_table': raw_table
    #         },
    #     provide_context=True
    # )

    # sleep_task = BashOperator(
    #     task_id="sleep_for_10_seconds",
    #     bash_command="sleep 10"
    # )

    # dbt_weather_data_models = DbtTaskGroup(
    #     group_id="weather_data_models",
    #     project_config=ProjectConfig("/opt/airflow/dags/Data_Marketplace",),
    #     execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt_venv/bin/dbt",),
    #     operator_args={"install_deps": True},
    #     profile_config=profile_config,
    #     default_args={"retries": 2},
    #     render_config=RenderConfig(
    #         select=["tag:Weather_Data"],
    #     )
    # )

    # Trigger_DAG_Task = TriggerDagRunOperator(
    # task_id='Trigger_DAG_Prediction_Model',
    # trigger_dag_id='Prediction_Model'
    # )

    generate_output_file_task >> is_insertd_task
    is_insertd_task >> no_new_data_task
    is_insertd_task  # >> invoke_lambda_task >> check_s3_file  >> copy_into_task >> sleep_task >> dbt_weather_data_models >> Trigger_DAG_Task



