from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.hooks.base_hook import BaseHook
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    'owner' : 'Ducky',
    'retries': 0,
    'retry_delay': timedelta(seconds=5),
    'email' : 'dohung24112002@gmail.com',
    'email_on_failure': True,
    'email_on_retry': False,
    'on_failure_callback': task_failure_alert,  
}

with DAG('Test_email',
         start_date=datetime(2024, 1, 1),
         schedule_interval='@daily',
         default_args=default_args,
         catchup=False
) as dag:
    task1 = BashOperator(
        task_id='Test',
        bash_command="cd non_exist_folder"
    )