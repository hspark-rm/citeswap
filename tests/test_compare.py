"""라이브러리 비교 시험 — 개인 자료 없이 가짜 Zotero DB · EndNote 라이브러리로 돈다.
실행: python -m pytest -q tests"""
import os
import sqlite3
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ZMS_CONF", tempfile.mkdtemp())
os.environ.setdefault("ZMS_DATA", tempfile.mkdtemp())

import compare as C  # noqa: E402
import zms  # noqa: E402


def fake_zotero(rows, cols=(), members=(), deleted=()):
    """rows: [(itemID, key, type, {field: value}, [(last, first, role)])]"""
    d = Path(tempfile.mkdtemp()) / "zotero.sqlite"
    con = sqlite3.connect(d)
    con.executescript("""
        create table itemTypes(itemTypeID integer primary key, typeName text);
        create table items(itemID integer primary key, itemTypeID int, libraryID int, key text);
        create table deletedItems(itemID int);
        create table fields(fieldID integer primary key, fieldName text);
        create table itemDataValues(valueID integer primary key, value text);
        create table itemData(itemID int, fieldID int, valueID int);
        create table creators(creatorID integer primary key, firstName text, lastName text, fieldMode int);
        create table creatorTypes(creatorTypeID integer primary key, creatorType text);
        create table itemCreators(itemID int, creatorID int, creatorTypeID int, orderIndex int);
        create table collections(collectionID integer primary key, key text, collectionName text, parentCollectionID int,
                                 libraryID int);
        create table collectionItems(collectionID int, itemID int);
        create table deletedCollections(collectionID int);
    """)
    types, fields, ctypes = {}, {}, {}
    for iid, key, typ, f, people in rows:
        tid = types.setdefault(typ, len(types) + 1)
        con.execute("insert or ignore into itemTypes values (?, ?)", (tid, typ))
        con.execute("insert into items values (?, ?, 1, ?)", (iid, tid, key))
        for name, val in f.items():
            fid = fields.setdefault(name, len(fields) + 1)
            con.execute("insert or ignore into fields values (?, ?)", (fid, name))
            vid = con.execute("insert into itemDataValues(value) values (?)", (val,)).lastrowid
            con.execute("insert into itemData values (?, ?, ?)", (iid, fid, vid))
        for n, (last, first, role) in enumerate(people):
            cid = con.execute("insert into creators(firstName, lastName, fieldMode) values (?, ?, 0)", (first, last)).lastrowid
            rid = ctypes.setdefault(role, len(ctypes) + 1)
            con.execute("insert or ignore into creatorTypes values (?, ?)", (rid, role))
            con.execute("insert into itemCreators values (?, ?, ?, ?)", (iid, cid, rid, n))
    for c in cols:
        con.execute("insert into collections values (?, ?, ?, ?, 1)", c)
    con.executemany("insert into collectionItems values (?, ?)", members)
    con.executemany("insert into deletedItems values (?)", [(i,) for i in deleted])
    con.commit()
    con.close()
    return d


def csl(title, year, family, doi=None, container=None):
    c = {"type": "article-journal", "title": title, "issued": {"date-parts": [[year]]}, "author": [{"family": family, "given": "A"}]}
    if doi:
        c["DOI"] = doi
    if container:
        c["container-title"] = container
    return c


MINE = [
    (1, "AAAA1111", "journalArticle", {"title": "Bullying and depression", "date": "2020", "DOI": "10.1037/abc",
                                       "publicationTitle": "Journal of Applied Psychology"}, [("Kim", "Min", "author")]),
    (2, "BBBB2222", "journalArticle", {"title": "No DOI paper", "date": "2019"}, [("Lee", "Ha", "author")]),
    (3, "CCCC3333", "journalArticle", {"title": "Conflict paper", "date": "2018", "DOI": "10.1037/mine"}, [("Park", "J", "author")]),
    (4, "DDDD4444", "book", {"title": "Only mine book", "date": "2010"}, [("Choi", "S", "author")]),
    (5, "EEEE5555", "journalArticle", {"title": "In trash", "date": "2001"}, [("Gone", "X", "author")]),
]


def library():
    db = fake_zotero(MINE, cols=[(10, "COL1", "Project", None), (11, "COL2", "Sub", 10)], members=[(11, 1), (10, 4)],
                     deleted=[5])
    return C.load_zotero(db)


def test_load_zotero_skips_trash_and_reads_collections():
    refs, cols = library()
    assert {r.key for r in refs} == {"AAAA1111", "BBBB2222", "CCCC3333", "DDDD4444"}
    assert C.col_path(cols, 11) == "Project / Sub"
    assert {r.key for r in C.in_collection(refs, cols, 10)} == {"AAAA1111", "DDDD4444"}  # 하위 컬렉션 포함


def test_compare_rules():
    refs, _ = library()
    theirs = [
        csl("BULLYING and Depression!", 2020, "Kim", "https://doi.org/10.1037/ABC", "J Appl Psychol"),  # DOI 로 짝
        csl("Bullying and depression", 2020, "Kim", "10.1037/abc"),     # 같은 문헌이 두 번 — 한 번만 센다
        csl("No DOI paper", 2019, "Lee", "10.9999/theirs"),              # DOI 가 한쪽만 → 제목으로 짝
        csl("Conflict paper", 2018, "Park", "10.1037/other"),            # 제목은 같고 DOI 가 다름 → 충돌
        csl("Brand new", 2022, "Yoon"),                               # 상대에게만
    ]
    only_theirs, only_mine, both, conflicts = C.compare(refs, theirs)
    assert [c["title"] for c in only_theirs] == ["Brand new"]
    assert {r.key for r in only_mine} == {"DDDD4444"}
    assert {r.key for r, _ in both} == {"AAAA1111", "BBBB2222"}
    assert [r.key for r, _ in conflicts] == ["CCCC3333"]
    diffs = C.differences(next(r for r, _ in both if r.key == "AAAA1111"), theirs[0])
    assert ("source", "Journal of Applied Psychology", "J Appl Psychol") in diffs


def test_endnote_xml_round_trip():
    refs, _ = library()
    csls = [C.ref_to_csl(r) for r in refs]
    x = C.endnote_xml(csls, zms)
    back = [zms.en_record_to_csl(r) for r in ET.fromstring(x).iter("record")]
    assert [b["title"] for b in back] == [r.title for r in refs]
    assert next(b for b in back if b["title"] == "Bullying and depression").get("DOI") == "10.1037/abc"


def test_endnote_library():
    d = Path(tempfile.mkdtemp()) / "lib.enl"
    con = sqlite3.connect(d)
    con.execute("""create table refs(reference_type int, author text, year text, title text, secondary_title text,
                   volume text, number text, pages text, electronic_resource_number text, abstract text, isbn text,
                   url text, trash_state int)""")
    con.execute("insert into refs values (0, 'Kim, Min\rLee, Ha', '2020', 'Bullying and depression', 'JAP', '1', '2', "
                "'3-4', '10.1037/abc', '', '1234-5678', '', 0)")
    con.execute("insert into refs values (0, 'X, Y', '1999', 'Trashed', '', '', '', '', '', '', '', '', 1)")
    con.commit()
    con.close()
    refs = C.from_endnote_library(d)
    assert len(refs) == 1 and refs[0]["DOI"] == "10.1037/abc" and refs[0]["author"][1]["family"] == "Lee"


def test_gui_starts_offscreen(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import importlib
    import gui
    importlib.reload(gui)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = gui.Main()
    assert w.tabs.count() == 2 and w.compare_page.table.columnCount() == 7
    w.close()
    del app
