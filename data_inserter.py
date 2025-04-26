# random_insert_update_delete.py

import mysql.connector
import random
import time

# MySQL connection config
conn = mysql.connector.connect(
    host="localhost",    # or your Docker host IP
    user="root",
    password="debezium",
    database="testdb",
    port=3306
)

cursor = conn.cursor()
# ✅ Ensure employees table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS employees (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    position VARCHAR(255),
    salary FLOAT
)
""")
conn.commit()

names = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Heidi']
positions = ['Data Engineer', 'DevOps Engineer', 'Analyst', 'Manager', 'Tester']

def insert_employee():
    name = random.choice(names) + str(random.randint(100, 999))
    position = random.choice(positions)
    salary = random.randint(50000, 200000)

    query = "INSERT INTO employees (name, position, salary) VALUES (%s, %s, %s)"
    values = (name, position, salary)

    cursor.execute(query, values)
    conn.commit()
    print(f"✅ Inserted: {name} | {position} | {salary}")

def update_employee():
    cursor.execute("SELECT id FROM employees ORDER BY RAND() LIMIT 1")
    result = cursor.fetchone()
    if result:
        id = result[0]
        new_salary = random.randint(60000, 210000)
        query = "UPDATE employees SET salary = %s WHERE id = %s"
        cursor.execute(query, (new_salary, id))
        conn.commit()
        print(f"🛠️ Updated: id={id} with new salary {new_salary}")
    else:
        print("No employees found to update.")

def delete_employee():
    cursor.execute("SELECT id FROM employees ORDER BY RAND() LIMIT 1")
    result = cursor.fetchone()
    if result:
        id = result[0]
        query = "DELETE FROM employees WHERE id = %s"
        cursor.execute(query, (id,))
        conn.commit()
        print(f"🗑️ Deleted: id={id}")
    else:
        print("No employees found to delete.")

while True:
    action = random.choice(['insert', 'update', 'delete'])

    if action == 'insert':
        insert_employee()
    elif action == 'update':
        update_employee()
    elif action == 'delete':
        delete_employee()

    time.sleep(2)  # wait for 5 seconds
