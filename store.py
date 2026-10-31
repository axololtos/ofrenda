"""SQLite memory store. Plain cosine scan: fine for a family's worth of stories."""
import json
import math
import os
import sqlite3


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(os.getenv("OFRENDA_DB", "ofrenda.db"))
    c.execute(
        "create table if not exists memories("
        "id integer primary key, person text, text text, tags text, vec text)"
    )
    return c


def add(person: str, text: str, tags: list[str], vec: list[float]) -> None:
    with _db() as c:
        c.execute(
            "insert into memories(person,text,tags,vec) values(?,?,?,?)",
            (person, text, json.dumps(tags), json.dumps(vec)),
        )


def _cos(a: list[float], b: list[float]) -> float:
    d = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / d if d else 0.0


# ponytail: linear scan, swap for sqlite-vec / MongoDB Atlas vector search past ~50k memories
def search(person: str, qvec: list[float], k: int = 4) -> list[dict]:
    with _db() as c:
        rows = c.execute("select text,tags,vec from memories where person=?", (person,)).fetchall()
    rows.sort(key=lambda r: _cos(qvec, json.loads(r[2])), reverse=True)
    return [{"text": t, "tags": json.loads(g)} for t, g, _ in rows[:k]]


def people() -> list[str]:
    with _db() as c:
        return [r[0] for r in c.execute("select distinct person from memories order by person")]
