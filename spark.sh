#!/bin/bash

# --- Step 1: Clean up previous Jupyter, PySpark processes
echo "🔁 Cleaning up previous Jupyter and PySpark instances..."
pkill -f jupyter-notebook
pkill -f pyspark
# DO NOT kill all python3 processes — may kill ingestion or ETL scripts

# --- Step 2: Set required environment variables
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
export PATH=$JAVA_HOME/bin:$PATH
export SPARK_HOME=/opt/spark
export PATH=$SPARK_HOME/bin:$PATH

export PYSPARK_DRIVER_PYTHON=jupyter
export PYSPARK_DRIVER_PYTHON_OPTS="notebook --notebook-dir=/home/ec2-user --ip=0.0.0.0 --port=8999 --no-browser"

# --- Step 3: Launch PySpark with JDBC and Kafka packages
echo "🚀 Starting Jupyter Notebook with PySpark and ClickHouse JDBC..."
$SPARK_HOME/bin/pyspark \
  --master local[*] \
  --conf spark.sql.execution.arrow.pyspark.enabled=true \
  --conf spark.driver.memory=4g \
  --jars /home/ec2-user/jars/clickhouse-jdbc-0.4.6-all.jar \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.1 \
  --driver-class-path /home/ec2-user/jars/clickhouse-jdbc-0.4.6-all.jar \
  --conf spark.executor.extraClassPath=/home/ec2-user/jars/clickhouse-jdbc-0.4.6-all.jar \
  --conf spark.driver.extraClassPath=/home/ec2-user/jars/clickhouse-jdbc-0.4.6-all.jar \
  --conf spark.sql.catalogImplementation=in-memory \
  --conf spark.ui.showConsoleProgress=true \
  --conf spark.pyspark.python=python3