from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig, DbtTaskGroup, RenderConfig
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from cosmos.profiles import SnowflakeUserPasswordProfileMapping
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash import BashOperator
from email.mime.multipart import MIMEMultipart
from airflow.hooks.base_hook import BaseHook
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from airflow import DAG
import smtplib


def generate_output_file(**kwargs):
    data_interval_end = kwargs['data_interval_end'] - timedelta(days=1)
    output_file = f'Data_Weather-{data_interval_end.strftime("%Y%m%d")}.csv'
    execution_date = data_interval_end.strftime('%Y/%m/%d')
    print(f'Generated output file: {output_file}')
    print(f'Execution Date: {execution_date}')
    print(type(execution_date))
    # Push output_file to XCom
    kwargs['ti'].xcom_push(key='output_file', value=output_file)
    kwargs['ti'].xcom_push(key='execution_date', value=execution_date)

def call_snowflake_procedure(snowflake_conn, procedure_name, execution_date):
    hook = SnowflakeHook(snowflake_conn_id=snowflake_conn)
    conn = hook.get_conn()
    cursor = conn.cursor()
    if execution_date is None:
        sql_query = f"CALL {procedure_name}();"
        conn.cursor().execute(sql_query)
    else:
        execution_date = datetime.strptime(execution_date, '%Y/%m/%d').date()
        print(type(execution_date))
        var = f"'{execution_date}'"
        sql_query = f"CALL {procedure_name}({var});"
        conn.cursor().execute(sql_query)
        
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
    'retries': 0,  # Số lần thử lại
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
    dag_id='Prediction_Model',
    default_args=default_args,
    schedule_interval=None, # Muốn chạy dược backfill thì tham số schedule_interval phải khác None
    catchup=False,
) as dag:
    
    # Task 1: Tạo Output_File và Execution_Date
    generate_output_file_task = PythonOperator(
        task_id = 'generate_output_file',
        python_callable = generate_output_file
    )

    # # Task 2: Đợi 5s để đảm bảo dữ liệu đã được Insert vào bảng FCT_WEATHER_DATA
    # sleep_task = BashOperator(
    #     task_id="sleep_for_5_seconds",
    #     bash_command="sleep 5"
    # )

    # Task 3: Khởi động dbt model Insert dữ liệu tổng hợp theo ngày vào bảng FCT_WEATHER_DATA_DAILY
    dbt_weather_data_daily_models = DbtTaskGroup(
        group_id="weather_data_daily_models",
        project_config=ProjectConfig("/opt/airflow/dags/Data_Marketplace",),
        execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt_venv/bin/dbt",),
        operator_args={"install_deps": True},
        profile_config=profile_config,
        default_args={"retries": 2},
        render_config=RenderConfig(
            select=["tag:Wind_Speed"],
        )
    )

    # Task 4: Call Procedure Prepare_Data
    call_Prepare_Data_procedure_task = PythonOperator(
        task_id='Call_Prepare_Data_Procedure',
        python_callable=call_snowflake_procedure,
        op_kwargs = {
            'snowflake_conn': 'snowflake_conn',
            'procedure_name': 'PREPARE_DATA',
            'execution_date': "{{ task_instance.xcom_pull(task_ids='generate_output_file', key='execution_date') }}"
            },
        provide_context=True
    )

    # Task 5: Call Procedure PREDICTION_MODEL
    call_Prediction_Model_procedure_task = PythonOperator(
        task_id='Call_Prediction_Model_Procedure',
        python_callable=call_snowflake_procedure,
        op_kwargs = {
            'snowflake_conn': 'snowflake_conn_public',
            'procedure_name': 'PREDICTION_MODEL',
            'execution_date': None
            },
        provide_context=True
    )

    # Task 6: Call Procedure MERGE_DATA_PRODUCT
    call_MERGE_DATA_PRODUCT_procedure_task = PythonOperator(
        task_id='Call_MERGE_DATA_PRODUCT_Procedure',
        python_callable=call_snowflake_procedure,
        op_kwargs = {
            'snowflake_conn': 'snowflake_conn_public',
            'procedure_name': 'MERGE_DATA_PRODUCT',
            'execution_date': None
            },
        provide_context=True
    )

    generate_output_file_task >> dbt_weather_data_daily_models >>  call_Prepare_Data_procedure_task >> call_Prediction_Model_procedure_task >> call_MERGE_DATA_PRODUCT_procedure_task




