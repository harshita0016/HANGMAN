import sqlite3
from tabulate import tabulate

db_path = "hangman.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

tables = ["signup", "login", "scores", "word_history", "words"]

for table in tables:
    print(f"\n--- {table.upper()} TABLE SCHEMA ---")
    cur.execute(f"PRAGMA table_info({table});")
    schema = cur.fetchall()
    print(tabulate(schema, headers=["CID", "Name", "Type", "Not Null", "Default", "PK"], tablefmt="fancy_grid"))

    print(f"\n--- {table.upper()} TABLE CONTENTS ---")
    cur.execute(f"SELECT * FROM {table};")
    contents = cur.fetchall()
    if contents:
        col_headers = [desc[0] for desc in cur.description]

        # Paginate if table is too long
        page_size = 20
        for i in range(0, len(contents), page_size):
            print(tabulate(contents[i:i+page_size], headers=col_headers, tablefmt="fancy_grid"))
            if i + page_size < len(contents):
                input("Press Enter to see more...")
    else:
        print("No data found!")

con.close()
