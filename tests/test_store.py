"""Run: python tests/test_store.py  (from the ofrenda/ folder)"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["OFRENDA_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import store  # noqa: E402

store.add("Abuela", "Burned the first tortilla for the house.", ["food"], [1.0, 0.0])
store.add("Abuela", "Sang boleros while washing dishes.", ["song"], [0.0, 1.0])
store.add("Tio", "Fixed radios.", [], [1.0, 0.0])

assert store.search("Abuela", [0.9, 0.1], k=1)[0]["text"].startswith("Burned")
assert store.search("Abuela", [0.1, 0.9], k=1)[0]["text"].startswith("Sang")
assert len(store.search("Abuela", [1, 0], k=5)) == 2  # other people's memories never leak
assert store.people() == ["Abuela", "Tio"]
print("ok")
