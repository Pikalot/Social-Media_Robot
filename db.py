import os

import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        database=os.getenv("MYSQL_DATABASE"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
    )


def init_schema(conn) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            business VARCHAR(255) NOT NULL,
            author VARCHAR(255) NOT NULL,
            rating INT NOT NULL,
            text TEXT,
            review_time VARCHAR(32),
            platform VARCHAR(64) NOT NULL,
            link VARCHAR(1024),
            review_hash CHAR(64) NOT NULL UNIQUE,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            version INT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            review_id INT NOT NULL,
            branch_code VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'Open',
            description VARCHAR(512),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exported_at TIMESTAMP NULL DEFAULT NULL,
            version INT DEFAULT 0,
            FOREIGN KEY (review_id) REFERENCES reviews(id)
        )
    """)
    conn.commit()
    cursor.close()
