"""라이브러리 비교: 내 Zotero 와 상대(공저자 원고 · Mendeley · EndNote)의 문헌을 대조한다.

화면(gui.py)과 떨어진 순수 함수만 둔다. 내 Zotero 는 zotero.sqlite 사본을 읽기만 한다(Zotero 가 켜져 있어도 됨).
짝짓기 규칙
- DOI 가 양쪽에 있으면 DOI 로만 판정한다.
- DOI 가 한쪽이라도 없으면 전체 제목 · 연도 · 첫 저자 성으로 판정한다.
- 제목 · 연도 · 첫 저자는 같은데 DOI 가 서로 다르면 같은 문헌으로 치지 않고 '충돌'로 따로 보인다.
"""
import re
import shutil
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
# EndNote 라이브러리(.enl) 안의 문헌 유형 번호(XML 의 ref-type 번호와 다름) → CSL 유형
ENL_TYPES = {0: "article-journal", 1: "book", 2: "thesis", 3: "paper-conference", 5: "article-newspaper",
             7: "chapter", 8: "article-magazine", 9: "book", 10: "report", 16: "webpage"}
# Zotero 유형 → CSL 유형(EndNote XML 로 내보낼 때)
ZOTERO_TO_CSL = {"journalArticle": "article-journal", "book": "book", "bookSection": "chapter", "thesis": "thesis",
                 "report": "report", "conferencePaper": "paper-conference", "webpage": "webpage",
                 "newspaperArticle": "article-newspaper", "magazineArticle": "article-magazine",
                 "preprint": "article", "manuscript": "manuscript", "document": "document"}
SOURCE_FIELDS = ("publicationTitle", "bookTitle", "proceedingsTitle", "websiteTitle", "university", "institution")


@dataclass
class Ref:
    """내 Zotero 문헌 한 건(비교에 필요한 것만)."""
    id: int
    key: str
    type: str
    fields: dict = field(default_factory=dict)
    creators: list = field(default_factory=list)   # [(성, 이름, 역할)]
    collections: set = field(default_factory=set)

    @property
    def title(self):
        return self.fields.get("title", "")

    @property
    def year(self):
        m = re.search(r"\d{4}", self.fields.get("date", ""))
        return m.group(0) if m else ""

    @property
    def source(self):
        return next((self.fields[k] for k in SOURCE_FIELDS if self.fields.get(k)), "")

    @property
    def authors_text(self):
        names = [c[0] for c in self.creators if c[2] == "author"] or [c[0] for c in self.creators]
        return names[0] + (" et al." if len(names) > 2 else f", {names[1]}" if len(names) == 2 else "") if names else ""

    @property
    def doi(self):
        return self.fields.get("DOI") or (re.search(r"DOI:\s*(\S+)", self.fields.get("extra", ""), re.I) or [None, ""])[1]


@dataclass
class Collection:
    id: int
    key: str
    name: str
    parent: int = None


def open_copy(db):
    """Zotero DB 사본(DB + WAL)을 연다. 돌려줌: (연결, 지울 임시 폴더)."""
    db = Path(db)
    tmp = Path(tempfile.mkdtemp(prefix="citeswap-"))
    shutil.copy2(db, tmp / "zotero.sqlite")
    wal = db.with_name(db.name + "-wal")
    if wal.exists():
        shutil.copy2(wal, tmp / "zotero.sqlite-wal")
    return sqlite3.connect(tmp / "zotero.sqlite"), tmp


def load_zotero(db):
    """(문헌 [Ref], 컬렉션 {id: Collection}). 내 라이브러리(libraryID 1)만, 휴지통·첨부·메모·주석은 뺀다."""
    con, tmp = open_copy(db)
    try:
        refs = {}
        for iid, key, typ in con.execute(
                """select i.itemID, i.key, t.typeName from items i join itemTypes t using(itemTypeID)
                   where i.libraryID = 1 and t.typeName not in ('attachment', 'note', 'annotation')
                     and i.itemID not in (select itemID from deletedItems)"""):
            refs[iid] = Ref(iid, key, typ)
        for iid, name, val in con.execute(
                """select d.itemID, f.fieldName, v.value from itemData d
                   join fields f using(fieldID) join itemDataValues v using(valueID)"""):
            if iid in refs:
                refs[iid].fields[name] = val
        for iid, first, last, mode, role in con.execute(
                """select ic.itemID, c.firstName, c.lastName, c.fieldMode, ct.creatorType from itemCreators ic
                   join creators c using(creatorID) join creatorTypes ct using(creatorTypeID)
                   order by ic.itemID, ic.orderIndex"""):
            if iid in refs:
                refs[iid].creators.append((last or "", "" if mode == 1 else (first or ""), role))
        cols = {cid: Collection(cid, key, name, parent) for cid, key, name, parent in con.execute(
            "select collectionID, key, collectionName, parentCollectionID from collections where libraryID = 1")}
        deleted_cols = {r[0] for r in con.execute("select collectionID from deletedCollections")} \
            if con.execute("select 1 from sqlite_master where name='deletedCollections'").fetchone() else set()
        for cid in deleted_cols:
            cols.pop(cid, None)
        for cid, iid in con.execute("select collectionID, itemID from collectionItems"):
            if iid in refs and cid in cols:
                refs[iid].collections.add(cid)
        return list(refs.values()), cols
    finally:
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)


def col_path(cols, cid):
    c = cols[cid]
    return (col_path(cols, c.parent) + " / " if c.parent in cols else "") + c.name


def in_collection(refs, cols, cid):
    """그 컬렉션과 하위 컬렉션의 문헌."""
    want, changed = {cid}, True
    while changed:
        changed = False
        for c in cols.values():
            if c.parent in want and c.id not in want:
                want.add(c.id)
                changed = True
    return [r for r in refs if r.collections & want]


# ---------- 짝짓기 ----------

def norm_title(t):
    return re.sub(r"[\W_]+", "", (t or "").casefold())


def norm_doi(doi):
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", (doi or "").strip().lower())
    return d if d.startswith("10.") else ""


def keys_of(title, year, first_author, doi):
    """(DOI, 제목 키). 제목 키 = (정규화한 전체 제목, 연도, 첫 저자 성)."""
    t = norm_title(title)
    tk = (t, str(year)[:4], first_author.casefold()) if t and year and first_author else None
    return norm_doi(doi), tk


def csl_keys(c):
    a = (c.get("author") or [{}])[0]
    parts = ((c.get("issued") or {}).get("date-parts") or [[None]])[0]
    return keys_of(c.get("title"), parts[0] if parts else None, a.get("family") or a.get("literal") or "", c.get("DOI"))


def ref_keys(r):
    first = next((c[0] for c in r.creators if c[2] == "author"), r.creators[0][0] if r.creators else "")
    return keys_of(r.title, r.year, first, r.doi)


def csl_brief(c):
    """(제목, 저자, 연도, 게재지, DOI)"""
    a = c.get("author") or []
    names = [x.get("family") or x.get("literal") or "" for x in a]
    au = names[0] + (" et al." if len(names) > 2 else f", {names[1]}" if len(names) == 2 else "") if names else ""
    parts = ((c.get("issued") or {}).get("date-parts") or [[""]])[0]
    return c.get("title", ""), au, str(parts[0] if parts else ""), c.get("container-title", ""), c.get("DOI", "")


def differences(r, c, labels=("title", "first author", "year", "source")):
    """양쪽에 있는 문헌의 서지 차이: [(칸 이름, 내 값, 상대 값)]."""
    t, au, yr, src, _ = csl_brief(c)
    mine_au = next((x[0] for x in r.creators if x[2] == "author"), r.creators[0][0] if r.creators else "")
    their_au = au.split(",")[0].replace(" et al.", "")
    out = []
    for name, a, b, same in ((labels[0], r.title, t, norm_title(r.title) == norm_title(t)),
                             (labels[1], mine_au, their_au, mine_au.casefold() == their_au.casefold()),
                             (labels[2], r.year, yr, str(r.year)[:4] == str(yr)[:4]),
                             (labels[3], r.source, src, norm_title(r.source) == norm_title(src))):
        if not same and (a or b):
            out.append((name, a, b))
    return out


def compare(mine, theirs):
    """(상대에게만 [CSL], 내게만 [Ref], 양쪽 [(Ref, CSL)], DOI 충돌 [(Ref, CSL)])."""
    by_doi, by_title = {}, {}
    for r in mine:
        d, t = ref_keys(r)
        if d:
            by_doi.setdefault(d, r)
        if t:
            by_title.setdefault(t, r)
    matched, conflicted = set(), set()
    only_theirs, both, conflicts = [], [], []
    seen_doi, seen_title = set(), set()  # 상대 쪽에 같은 문헌이 여러 번 있으면(공저자 원고에 흔함) 한 번만 센다
    for c in theirs:
        d, t = csl_keys(c)
        if (d and d in seen_doi) or (not d and t and t in seen_title):
            continue
        if d:
            seen_doi.add(d)
        if t:
            seen_title.add(t)
        hit = by_doi.get(d) if d else None
        if hit is None and t in by_title:
            cand = by_title[t]
            cd = norm_doi(cand.doi)
            if d and cd and cd != d:
                conflicts.append((cand, c))
                conflicted.add(cand.id)
                continue
            hit = cand
        if hit:
            matched.add(hit.id)
            both.append((hit, c))
        else:
            only_theirs.append(c)
    only_mine = [r for r in mine if r.id not in matched and r.id not in conflicted]
    return only_theirs, only_mine, both, conflicts


# ---------- 상대 쪽 읽기 ----------

def from_manuscript(path, zms):
    """Word 원고에 인용된 문헌(Zotero · Mendeley · EndNote 형식 모두)."""
    with zipfile.ZipFile(path) as z:
        x = z.read("word/document.xml").decode("utf-8")
    seen, out = set(), []
    for reader in zms.READERS.values():
        for c in reader(x)[0]:
            for it in c["items"]:
                if it["key"] not in seen and it["csl"].get("title"):
                    seen.add(it["key"])
                    out.append(it["csl"])
    return out


def mendeley_to_csl(d):
    t = {"journal": "article-journal", "book": "book", "book_section": "chapter", "report": "report",
         "thesis": "thesis", "conference_proceedings": "paper-conference", "web_page": "webpage",
         "working_paper": "article", "magazine_article": "article-magazine", "newspaper_article": "article-newspaper"}
    c = {"type": t.get(d.get("type"), "article-journal"), "title": d.get("title", "")}
    au = [{"family": a.get("last_name", ""), "given": a.get("first_name", "")} for a in d.get("authors") or []]
    if au:
        c["author"] = au
    if d.get("year"):
        c["issued"] = {"date-parts": [[d["year"]] + ([d["month"]] if d.get("month") else [])]}
    for src, dst in (("source", "container-title"), ("volume", "volume"), ("issue", "issue"), ("pages", "page"),
                     ("abstract", "abstract")):
        if d.get(src):
            c[dst] = str(d[src])
    ids = d.get("identifiers") or {}
    for src, dst in (("doi", "DOI"), ("issn", "ISSN"), ("isbn", "ISBN"), ("pmid", "PMID")):
        if ids.get(src):
            c[dst] = ids[src]
    return c


def from_mendeley(zms, group_id=None):
    params = {"view": "all", "limit": 500}
    if group_id:
        params["group_id"] = group_id
    docs = zms.get_all("/documents", params)
    if not group_id:
        docs = [d for d in docs if not d.get("group_id")]
    return [mendeley_to_csl(d) for d in docs if d.get("title")]


def from_endnote_library(path):
    """EndNote 라이브러리(.enl = SQLite)를 사본으로 읽는다."""
    tmp = Path(tempfile.mkdtemp(prefix="citeswap-")) / "lib.enl"
    shutil.copy2(path, tmp)
    con = sqlite3.connect(tmp)
    out = []
    try:
        for rtype, author, year, title, sec, vol, num, pages, erm, abstract, isbn, url in con.execute(
                """select reference_type, author, year, title, secondary_title, volume, number, pages,
                          electronic_resource_number, abstract, isbn, url
                   from refs where trash_state = 0"""):
            c = {"type": ENL_TYPES.get(rtype, "article-journal"), "title": (title or "").strip()}
            names = [n.strip() for n in re.split(r"[\r\n]+", author or "") if n.strip()]
            c["author"] = [({"family": n.split(",", 1)[0].strip(), "given": n.split(",", 1)[1].strip()}
                            if "," in n else {"literal": n}) for n in names]
            y = re.search(r"\d{4}", year or "")
            if y:
                c["issued"] = {"date-parts": [[int(y.group(0))]]}
            for v, k in ((sec, "container-title"), (vol, "volume"), (num, "issue"), (pages, "page"), (abstract, "abstract"),
                         (url, "URL")):
                if v:
                    c[k] = v.strip()
            m = DOI_RE.search(erm or "")
            if m:
                c["DOI"] = m.group(0).rstrip(".")
            if isbn:
                c["ISSN" if c["type"] == "article-journal" else "ISBN"] = re.split(r"[\s\r\n]", isbn.strip())[0]
            if c["title"]:
                out.append(c)
    finally:
        con.close()
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return out


def from_endnote_xml(path, zms):
    root = ET.parse(path).getroot()
    return [c for c in (zms.en_record_to_csl(r) for r in root.iter("record")) if c.get("title")]


# ---------- 내 문헌 내보내기 ----------

def ref_to_csl(r):
    """Zotero 문헌 → CSL-JSON(EndNote XML 로 공저자에게 보낼 때)."""
    f = r.fields
    c = {"type": ZOTERO_TO_CSL.get(r.type, "document"), "title": r.title}
    for role in ("author", "editor"):
        ppl = [({"family": last, "given": first} if first else {"literal": last} if last else {})
               for last, first, ro in r.creators if ro == role]
        ppl = [p for p in ppl if p]
        if ppl:
            c[role] = ppl
    if r.year:
        c["issued"] = {"date-parts": [[int(r.year)]]}
    if r.source:
        c["container-title"] = r.source
    for src, dst in (("volume", "volume"), ("issue", "issue"), ("pages", "page"), ("abstractNote", "abstract"),
                     ("url", "URL"), ("ISSN", "ISSN"), ("ISBN", "ISBN"), ("publisher", "publisher"), ("language", "language")):
        if f.get(src):
            c[dst] = f[src]
    if r.doi:
        c["DOI"] = r.doi
    return c


def endnote_xml(csls, zms, dbid="citeswap"):
    recs = "".join(f"<record>{zms.en_record_xml(c, n + 1, dbid)}</record>" for n, c in enumerate(csls))
    return f'<?xml version="1.0" encoding="UTF-8"?><xml><records>{recs}</records></xml>'
