#!/bin/bash

echo "🔌 Registering Debezium MySQL Connector..."

STATUS_CODE=$(curl -s -o response.json -w "%{http_code}" -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mysql-connector",
    "config": {
      "connector.class": "io.debezium.connector.mysql.MySqlConnector",
      "database.hostname": "mysql",
      "database.port": "3306",
      "database.user": "debezium",
      "database.password": "dbz",
      "database.server.id": "184054",
      "topic.prefix": "dbserver1",
      "database.include.list": "testdb",
      "table.include.list": "testdb.*",
      "database.history.store.only.captured.tables.ddl": "false",
      "snapshot.mode": "initial",
      "auto.create.topics.enable":"true",
      "table.ignore.builtin": "true",
      "include.schema.changes": "true",
      "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
      "schema.history.internal.kafka.topic": "schema-changes.testdb"
    }
  }')

echo "📦 HTTP Status: $STATUS_CODE"
cat response.json

if [[ "$STATUS_CODE" == "201" || "$STATUS_CODE" == "409" ]]; then
  echo "✅ Connector registered successfully (or already exists)."
else
  echo "❌ Connector registration failed!"
fi
