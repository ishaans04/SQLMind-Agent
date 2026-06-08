import sqlite3
from pathlib import Path

DATABASE_PATH = Path("data/demo.db")


def main() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS sales;

            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                order_date TEXT NOT NULL,
                region TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL
            );

            INSERT INTO sales (order_date, region, product, amount) VALUES
                ('2026-01-05', 'North', 'Analytics Pro', 1200.00),
                ('2026-01-07', 'South', 'Analytics Pro', 850.00),
                ('2026-01-11', 'West', 'Data Studio', 1420.50),
                ('2026-01-17', 'North', 'Data Studio', 990.25),
                ('2026-01-20', 'East', 'Query Guard', 615.75),
                ('2026-01-24', 'West', 'Query Guard', 740.00),
                ('2026-02-02', 'South', 'Data Studio', 1110.00),
                ('2026-02-08', 'East', 'Analytics Pro', 1325.00);
            """
        )

    print(f"Created {DATABASE_PATH}")


if __name__ == "__main__":
    main()
