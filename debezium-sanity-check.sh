#!/bin/bash

# ✅ Sanity Check Script for Debezium + MySQL + Kafka

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
sudo yum install jq -y  OR  sudo apt-get install jq -y
# 1. Check Kafka Topics
echo -e "\n🔍 Checking Kafka topics..."
docker exec -it docker-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list || { echo -e "${RED}Kafka Topics Check Failed${NC}"; exit 1; }

# 2. Check Debezium Connector Status
echo -e "\n🔍 Checking Debezium Connector..."
curl -s http://localhost:8083/connectors/mysql-connector/status | jq || { echo -e "${RED}Debezium Connector Status Check Failed${NC}"; exit 1; }

# 3. Check MySQL binlog_format
echo -e "\n🔍 Checking MySQL binlog_format..."
docker exec -i docker-mysql-1 mysql -u root -pdebezium -e "SHOW VARIABLES LIKE 'binlog_format';" | grep ROW && \
  echo -e "${GREEN}binlog_format is ROW ✅${NC}" || \
  echo -e "${RED}binlog_format NOT set to ROW ❌${NC}"

# 4. Check MySQL binary logs
echo -e "\n🔍 Checking MySQL binary logs..."
docker exec -i docker-mysql-1 mysql -u root -pdebezium -e "SHOW BINARY LOGS;" || { echo -e "${RED}MySQL Binary Logs Check Failed${NC}"; exit 1; }

# 5. Insert Test Data into employees table (optional)
echo -e "\n🔍 Inserting test employee record into MySQL..."
docker exec -i docker-mysql-1 mysql -u root -pdebezium -e "INSERT INTO testdb.employees (id, name, position, salary) VALUES (FLOOR(RAND()*1000)+1000, 'TestUser', 'TestPosition', 12345);" || { echo -e "${RED}Insert into MySQL Failed${NC}"; exit 1; }

# 6. Tail Docker Debezium Logs
echo -e "\n🔍 Tailing Debezium Connect logs... (Press Ctrl+C to stop)"
docker logs --tail 50 -f docker-connect-1

# 7. (Optional) Tail Kafka Topic Events
echo -e "\n🔍 (Optional) Consuming from Kafka topic dbserver1.testdb.employees..."
echo -e "(Run this manually if needed)\n"
echo "docker exec -it docker-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic dbserver1.testdb.employees --from-beginning"

# End


# NOTE:
# Make sure `jq` is installed inside host to parse JSON nicely.
# sudo yum install jq -y  OR  sudo apt-get install jq -y
