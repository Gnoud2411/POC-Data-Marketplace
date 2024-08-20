import os
from airflow import DAG

from datetime import datetime
from airflow.operators.empty import EmptyOperator

from cosmos import DbtDag, ProjectConfig, ProfileConfig, ExecutionConfig, DbtTaskGroup, RenderConfig
from cosmos.profiles import SnowflakeUserPasswordProfileMapping


profile_config = ProfileConfig(
    profile_name="Data_Marketplace",
    target_name="dev",
    profile_mapping=SnowflakeUserPasswordProfileMapping(
        conn_id="snowflake_conn", 
        profile_args={"database": "POC_DATA_MARKETPLACE", "schema": "DWH"},
    )
)

# dbt_snowflake_dag = DbtDag(
#     project_config=ProjectConfig("/usr/local/airflow/dags/Data_Marketplace",),
#     operator_args={"install_deps": True},
#     profile_config=profile_config,
#     execution_config=ExecutionConfig(dbt_executable_path=f"{os.environ['AIRFLOW_HOME']}/dbt_venv/bin/dbt",),
#     schedule_interval="@daily",
#     start_date=datetime(2023, 9, 10),
#     catchup=False,
#     dag_id="dbt_dag",
# )

with DAG(
    dag_id="dbt_dag_filterd",
    start_date=datetime(2023, 11, 24),
    schedule=None,
    catchup=False,
) as dag:

    pre_dbt_workflow = EmptyOperator(task_id="pre_dbt_workflow")

    dbt_snowflake_task = DbtTaskGroup(
        group_id="customers_group",
        project_config=ProjectConfig("/opt/airflow/dags/Data_Marketplace",),
        execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt_venv/bin/dbt",),
        operator_args={"install_deps": True},
        profile_config=profile_config,
        default_args={"retries": 2},
        render_config=RenderConfig(
            select=["tag:Wind_Speed"],
        )
    )

    post_dbt_workflow = EmptyOperator(task_id="post_dbt_workflow")

    pre_dbt_workflow >> dbt_snowflake_task >> post_dbt_workflow