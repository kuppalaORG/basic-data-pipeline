#!/bin/bash

echo "🔌 Registering Debezium MySQL Connector..."

curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mysql-connector",
    "config": {
      "connector.class": "io.debezium.connector.mysql.MySqlConnector",
      "database.hostname": "docker-mysql-1",
      "database.port": "3306",
      "database.user": "debezium",
      "database.password": "dbz",
      "database.server.id": "184054",
      "topic.prefix": "dbserver1",
      "database.include.list": "testdb",
      "table.include.list": "testdb.employees",
      "include.schema.changes": "false",
      "schema.history.internal.kafka.bootstrap.servers": "docker-kafka-1:9092",
      "schema.history.internal.kafka.topic": "schema-changes.testdb"
    }
  }'

echo "✅ Connector registered (or already exists)!"
