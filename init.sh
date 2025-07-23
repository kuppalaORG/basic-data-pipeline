#!/bin/bash
echo "⏳ Waiting for ClickHouse to be ready..."
until curl -s http://localhost:8123/ping | grep -q "Ok"; do
  sleep 2
done

echo "✅ ClickHouse is up. Creating raw database..."
clickhouse-client --query="CREATE DATABASE IF NOT EXISTS raw;"
