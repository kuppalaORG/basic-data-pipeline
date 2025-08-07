#!/bin/bash

echo "🔁 Cleaning up previous Jupyter and PySpark instances..."
pkill -f jupyter-notebook
pkill -f pyspark

echo "🚀 Starting Jupyter Notebook with PySpark and ClickHouse JDBC..."

env \
  PYSPARK_DRIVER_PYTHON=~/.local/bin/jupyter-notebook \
  PYSPARK_DRIVER_PYTHON_OPTS="--no-browser --ip=0.0.0.0 --port=8999 --notebook-dir=/home/ec2-user" \
  PYSPARK_PYTHON=python3 \
  JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java)))) \
  PATH=$JAVA_HOME/bin:$PATH \
  SPARK_HOME=/opt/spark \
  PATH=$SPARK_HOME/bin:$PATH:$PATH \
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
    --conf spark.ui.showConsoleProgress=true