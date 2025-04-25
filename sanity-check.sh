
set -e

echo "\n🔍 Checking running Docker containers..."
docker ps -a

echo "\n🔍 Checking MySQL connectivity..."
docker exec -i docker-mysql-1 mysql -uroot -pdebezium -e "SHOW DATABASES;"

echo "\n🔍 Checking Kafka topics..."
docker exec -i docker-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list

echo "\n🔍 Checking Kafka topic messages (showing 5 messages only)..."
docker exec -i docker-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic dbserver1.testdb.employees --from-beginning --timeout-ms 5000 | head -n 5


echo "\n🔍 Checking ClickHouse HTTP ping..."
curl -s http://localhost:8123/ping || echo "ClickHouse not responding"

echo "\n🔍 Checking Debezium Connector status..."
curl -s http://localhost:8083/connectors || echo "Debezium not responding"

echo "\n🔍 Checking network IP address..."
ip route get 1 | awk '{print $NF;exit}'

echo "\n✅ Sanity check completed!"
