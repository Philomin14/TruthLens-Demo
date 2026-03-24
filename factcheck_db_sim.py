import sqlite3

def create_db(path="factcheck.db"):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email    TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS claims (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL REFERENCES users(id),
            claim_text     TEXT NOT NULL,
            date_submitted TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS fact_check_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id       INTEGER NOT NULL UNIQUE REFERENCES claims(id),
            validity_score REAL NOT NULL CHECK(validity_score BETWEEN 0.0 AND 1.0),
            summary        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sources (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL REFERENCES fact_check_results(id),
            url       TEXT NOT NULL,
            title     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('person','organisation','date','place')),
            UNIQUE(name, entity_type)
        );

        CREATE TABLE IF NOT EXISTS claim_entities (
            claim_id  INTEGER NOT NULL REFERENCES claims(id),
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            PRIMARY KEY (claim_id, entity_id)
        );
    """)
    conn.commit()
    return conn


def add_user(conn, username, email):
    cur = conn.execute("INSERT INTO users (username, email) VALUES (?,?)", (username, email))
    conn.commit()
    return cur.lastrowid

def add_claim(conn, user_id, claim_text):
    cur = conn.execute("INSERT INTO claims (user_id, claim_text) VALUES (?,?)", (user_id, claim_text))
    conn.commit()
    return cur.lastrowid

def add_result(conn, claim_id, validity_score, summary):
    cur = conn.execute(
        "INSERT INTO fact_check_results (claim_id, validity_score, summary) VALUES (?,?,?)",
        (claim_id, validity_score, summary)
    )
    conn.commit()
    return cur.lastrowid

def add_source(conn, result_id, url, title):
    cur = conn.execute("INSERT INTO sources (result_id, url, title) VALUES (?,?,?)", (result_id, url, title))
    conn.commit()
    return cur.lastrowid

def add_entity(conn, name, entity_type):
    conn.execute("INSERT OR IGNORE INTO entities (name, entity_type) VALUES (?,?)", (name, entity_type))
    conn.commit()
    row = conn.execute("SELECT id FROM entities WHERE name=? AND entity_type=?", (name, entity_type)).fetchone()
    return row[0]

def link_entity(conn, claim_id, entity_id):
    conn.execute("INSERT OR IGNORE INTO claim_entities (claim_id, entity_id) VALUES (?,?)", (claim_id, entity_id))
    conn.commit()

def get_claim_summary(conn, claim_id):
    conn.row_factory = sqlite3.Row
    claim    = conn.execute("SELECT c.*, u.username FROM claims c JOIN users u ON c.user_id=u.id WHERE c.id=?", (claim_id,)).fetchone()
    result   = conn.execute("SELECT * FROM fact_check_results WHERE claim_id=?", (claim_id,)).fetchone()
    sources  = conn.execute("SELECT * FROM sources WHERE result_id=?", (result["id"],)).fetchall() if result else []
    entities = conn.execute(
        "SELECT e.name, e.entity_type FROM entities e "
        "JOIN claim_entities ce ON e.id=ce.entity_id WHERE ce.claim_id=?", (claim_id,)
    ).fetchall()
    return {"claim": dict(claim), "result": dict(result) if result else None,
            "sources": [dict(s) for s in sources], "entities": [dict(e) for e in entities]}


# -- Demo ----------------------------------------------------------------------
if __name__ == "__main__":
    conn = create_db(":memory:")

    alice = add_user(conn, "alice", "alice@example.com")
    bob   = add_user(conn, "bob",   "bob@example.com")

    c1 = add_claim(conn, alice, "The WHO declared COVID-19 a pandemic in March 2020.")
    c2 = add_claim(conn, bob,   "Elon Musk founded Amazon in 1994.")

    r1 = add_result(conn, c1, 0.98, "Confirmed - WHO announced this on 11 March 2020.")
    r2 = add_result(conn, c2, 0.02, "False - Amazon was founded by Jeff Bezos.")

    add_source(conn, r1, "https://www.who.int/news/item/11-03-2020", "WHO Statement March 2020")
    add_source(conn, r2, "https://en.wikipedia.org/wiki/Amazon_(company)", "Amazon - Wikipedia")

    who    = add_entity(conn, "WHO",        "organisation")
    musk   = add_entity(conn, "Elon Musk",  "person")
    bezos  = add_entity(conn, "Jeff Bezos", "person")
    amazon = add_entity(conn, "Amazon",     "organisation")
    mar20  = add_entity(conn, "March 2020", "date")

    link_entity(conn, c1, who);   link_entity(conn, c1, mar20)
    link_entity(conn, c2, musk);  link_entity(conn, c2, bezos); link_entity(conn, c2, amazon)

    for cid in (c1, c2):
        s = get_claim_summary(conn, cid)
        score = s["result"]["validity_score"] if s["result"] else "?"
        verdict = "TRUE" if score >= 0.7 else "FALSE" if score <= 0.3 else "UNCERTAIN"
        print(f'\nClaim: "{s["claim"]["claim_text"]}"')
        print(f'  User:     {s["claim"]["username"]}')
        print(f'  Score:    {score}  [{verdict}]')
        print(f'  Summary:  {s["result"]["summary"]}')
        print(f'  Sources:  {[src["title"] for src in s["sources"]]}')
        print(f'  Entities: {[(e["name"], e["entity_type"]) for e in s["entities"]]}')