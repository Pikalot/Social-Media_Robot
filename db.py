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
    # `synced` = 0 means the Excel row is missing or out of date.
    _add_column_if_missing(cursor, "reports", "synced", "TINYINT NOT NULL DEFAULT 0")
    conn.commit()
    cursor.close()
    migrate_review_hashes(conn)


def _add_column_if_missing(cursor, table: str, column: str, definition: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        if (table, column) == ("reports", "synced"):
            cursor.execute("UPDATE reports SET synced = 1 WHERE exported_at IS NOT NULL")


def migrate_review_hashes(conn) -> None:
    """Re-key existing rows to the business|platform|author hash used by
    reporting._review_hash. Idempotent. UPDATE IGNORE skips rows that would
    collide (an older duplicate of a review already re-keyed)."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE IGNORE reviews
        SET review_hash = SHA2(CONCAT(business, '|', platform, '|', author), 256)
    """)
    conn.commit()
    cursor.close()
