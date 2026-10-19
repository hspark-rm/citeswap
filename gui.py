"""CiteSwap — 레퍼런스 매니저 호환 · 변환 데스크톱 앱 (macOS · Windows).

두 탭: ① 원고 변환(Word 원고 인용을 Zotero · Mendeley Cite · EndNote 사이에서 바꿈)
       ② 라이브러리 비교(공저자 원고 · Mendeley · EndNote 와 내 Zotero 를 대조하고 서로 없는 문헌을 채움)
화면만 맡는다. 변환 · 인증 · API 는 zms.py, 비교는 compare.py 가 한다.
공개 도구 Zoteley(github.com/hspark-rm/zoteley)에서 이어 왔다.
"""
import html
import os
import shutil
import subprocess
import sys
import threading
import queue
from pathlib import Path

APP = "CiteSwap"


def app_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home()) / APP
    return Path.home() / ".config" / "citeswap"


# zms 는 가져올 때 설정·작업 폴더를 정하므로, 가져오기 전에 OS별 폴더를 알려 준다.
APP_DIR = app_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ZMS_CONF", str(APP_DIR))
os.environ.setdefault("ZMS_DATA", str(APP_DIR / "data"))
# 이미 Zoteley(같은 엔진)나 명령줄 도구로 설정했다면 그 설정(Mendeley 앱 등록 · 로그인)을 그대로 가져온다. 원본은 둔다.
for _old in (APP_DIR.parent / "Zoteley", Path.home() / ".config" / "zoteley", Path.home() / ".config" / "zotero-mendeley-sync"):
    if not (APP_DIR / "config.json").exists() and (_old / "config.json").exists():
        for n in ("config.json", "token.json"):
            if (_old / n).exists():
                shutil.copy2(_old / n, APP_DIR / n)

import compare  # noqa: E402
import zms  # noqa: E402
from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTabBar, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSETS = BASE / "assets"
DEV_SITE = "https://dev.mendeley.com/myapps.html"
HELP_URL = "https://github.com/hspark-rm/citeswap#readme"

# ---------- 문구 (한국어 · 영어) ----------

KO = QLocale.system().name().startswith("ko")
T = {
    "subtitle": ("레퍼런스 매니저 호환 · 변환 — Zotero · Mendeley · EndNote", "Reference manager compatibility — Zotero · Mendeley · EndNote"),
    "tab_convert": ("원고 변환", "Convert manuscript"),
    "tab_compare": ("라이브러리 비교", "Compare libraries"),
    # 라이브러리 비교
    "c_theirs": ("상대 쪽:", "Theirs:"),
    "c_mine": ("내 Zotero:", "My Zotero:"),
    "c_manuscript": ("공저자 원고(Word)…", "Co-author manuscript (Word)…"),
    "c_mendeley": ("Mendeley…", "Mendeley…"),
    "c_endnote": ("EndNote…", "EndNote…"),
    "c_all": ("전체", "Whole library"),
    "c_pick": ("비교할 상대를 고르세요. 공저자의 Word 원고, Mendeley 라이브러리(개인·그룹), EndNote 라이브러리(.enl)나 XML을 내 Zotero와 대조합니다.",
               "Choose what to compare: a co-author's Word manuscript, a Mendeley library (personal or group), or an EndNote library (.enl) or XML."),
    "c_tabs": (("상대에게만 있음", "내게만 있음", "양쪽 다 있음", "DOI 충돌(확인 필요)"), ("Only theirs", "Only mine", "In both", "DOI conflict (check)")),
    "c_cols": (("", "제목", "저자", "연도", "게재지", "DOI", "차이(내 값 → 상대 값)"), ("", "Title", "Authors", "Year", "Source", "DOI", "Differences (mine → theirs)")),
    "c_labels": (("제목", "첫 저자", "연도", "게재지"), ("title", "first author", "year", "source")),
    "c_summary": ("<b>{src}</b> ({n:,}건) ↔ <b>{scope}</b> ({m:,}건)<br>상대에게만 <b>{a:,}</b> · 내게만 <b>{b:,}</b> · 양쪽 다 <b>{c:,}</b>",
                  "<b>{src}</b> ({n:,}) ↔ <b>{scope}</b> ({m:,})<br>Only theirs <b>{a:,}</b> · only mine <b>{b:,}</b> · in both <b>{c:,}</b>"),
    "c_conflicts": (" · DOI 충돌 <b>{x:,}</b>(제목은 같고 DOI가 다름)", " · DOI conflicts <b>{x:,}</b> (same title, different DOI)"),
    "c_my_doi": ("내 DOI {a} · 상대 DOI {b}", "my DOI {a} · their DOI {b}"),
    "c_check_all": ("모두 고르기", "Select all"),
    "c_check_none": ("모두 풀기", "Select none"),
    "c_to_zotero": ("내 Zotero에 넣기", "Add to my Zotero"),
    "c_to_mendeley": ("Mendeley에 넣기", "Add to Mendeley"),
    "c_to_xml": ("EndNote XML로 저장", "Save as EndNote XML"),
    "c_choose_some": ("문헌을 고르세요(왼쪽 칸에 표시).", "Select references first (check boxes on the left)."),
    "c_added_zotero": ("{n}건을 내 Zotero에 넣었습니다. Zotero에서 지금 고른 컬렉션에 들어갔고, 태그 '{tag}'를 붙였습니다.",
                       "Added {n} references to Zotero (into the collection selected in Zotero), tagged '{tag}'."),
    "c_added_mendeley": ("{n}건을 {dst}에 넣었습니다.", "Added {n} references to {dst}."),
    "c_stopped": ("{n}건을 넣은 뒤 멈췄습니다.", "Stopped after adding {n}."),
    "c_saved_xml": ("{n}건을 저장했습니다.\n공저자는 EndNote에서 File > Import > File('EndNote generated XML')로 넣으면 됩니다.",
                    "Saved {n} references.\nYour co-author can import them in EndNote via File > Import > File ('EndNote generated XML')."),
    "c_xml_name": ("공저자에게_보낼_문헌.xml", "references_for_coauthor.xml"),
    "c_read_fail": ("읽지 못했습니다.", "Could not read it."),
    "c_loading": ("읽는 중…", "Reading…"),
    "c_mendeley_lib": ("비교할 Mendeley 라이브러리:", "Mendeley library to compare:"),
    "c_mendeley_personal": ("내 Mendeley 개인 라이브러리", "My personal Mendeley library"),
    "c_mendeley_group": ("그룹: {g}", "Group: {g}"),
    "c_no_groups": ("가입한 Mendeley 그룹이 없습니다. 공저자와 그룹을 만들면 여기에 나타납니다.",
                    "You are not in any Mendeley group. Groups you share with co-authors appear here."),
    "c_endnote_filter": ("EndNote 라이브러리 또는 XML (*.enl *.xml)", "EndNote library or XML (*.enl *.xml)"),
    "c_zotero_needed": ("Zotero 데이터 폴더를 먼저 설정하세요.", "Set the Zotero data folder first."),
    "drop": ("Word 원고(.docx)를 여기에 끌어다 놓으세요", "Drop a Word manuscript (.docx) here"),
    "choose": ("파일 선택…", "Choose file…"),
    "to_zotero": ("Zotero 원고로", "To Zotero"),
    "to_mendeley": ("Mendeley 원고로", "To Mendeley"),
    "to_endnote": ("EndNote 원고로", "To EndNote"),
    "to_sub": ("{src} → {dst}", "{src} → {dst}"),
    "settings": ("설정", "Settings"),
    "help": ("도움말", "Help"),
    "kind_one": ("{fmt} 인용 {n}개", "{n} {fmt} citations"),
    "kind_mixed": ("여러 형식이 섞인 원고: {parts}", "Mixed citations: {parts}"),
    "kind_none": ("인용이 없는 원고입니다", "No citations found in this manuscript"),
    "only_docx": ("Word 원고(.docx)만 바꿀 수 있습니다.", "Only Word manuscripts (.docx) can be converted."),
    "working": ("{fmt} 형식으로 바꾸는 중…", "Converting to {fmt}…"),
    "working_import": ("Zotero에 문헌을 넣는 중…", "Adding references to Zotero…"),
    "done": ("인용 {n}개를 {fmt} 형식으로 바꿨습니다.", "Converted {n} citations to {fmt} format."),
    "done_added": ("Mendeley에 없던 문헌 {n}건을 라이브러리에 추가했습니다.",
                   "Added {n} references that were missing from Mendeley."),
    "done_unl": ("{fmt} 라이브러리에 없는 문헌 {n}건은 문서 안 정보로 넣었습니다.",
                 "{n} references not in your {fmt} library were kept as embedded data."),
    "tip_mendeley": ("Word에서 Mendeley Cite를 열고 참고문헌을 한 번 새로고침하세요.",
                     "Open Mendeley Cite in Word and refresh the bibliography once."),
    "tip_zotero": ("Word의 Zotero 메뉴에서 Refresh를 한 번 누르세요.", "Click Refresh in Word's Zotero tab once."),
    "tip_endnote": ("Word의 EndNote 메뉴에서 Update Citations and Bibliography를 한 번 누르세요.",
                    "Click Update Citations and Bibliography in Word's EndNote tab once."),
    "new_file": ("새 파일: {f}", "New file: {f}"),
    "open_word": ("Word로 열기", "Open in Word"),
    "reveal": ("폴더에서 보기", "Show in folder"),
    "ok": ("확인", "OK"),
    "cancel": ("취소", "Cancel"),
    "missing_q": ("Zotero에 없는 문헌이 {n}건 있습니다.\n\nZotero에 넣으면 이 문헌들도 Zotero에서 편집할 수 있습니다. "
                  "문헌은 Zotero에서 지금 선택된 컬렉션에 들어갑니다.",
                  "{n} cited references are not in your Zotero library.\n\nAdd them to Zotero so you can edit them "
                  "there? They go into the collection currently selected in Zotero."),
    "add_and_convert": ("Zotero에 넣고 바꾸기", "Add to Zotero and convert"),
    "convert_only": ("넣지 않고 바꾸기", "Convert without adding"),
    "en_missing_q": ("EndNote 라이브러리에 없는 문헌이 {n}건 있습니다.\n\n문서 안 정보로 넣고 바꿀 수 있습니다. "
                     "라이브러리에 넣으려면 가져오기 파일을 EndNote에서 File > Import > File('EndNote generated XML')로 넣은 뒤 다시 바꾸세요.",
                     "{n} cited references are not in your EndNote library.\n\nYou can convert now and keep them as embedded data. "
                     "To add them to your library, import the file in EndNote via File > Import > File ('EndNote generated XML') and convert again."),
    "show_import_file": ("가져오기 파일 보기", "Show import file"),
    "zotero_off": ("Zotero가 열려 있어야 문헌을 넣을 수 있습니다. Zotero를 연 뒤 다시 시도하세요.",
                   "Zotero must be running to add references. Open Zotero and try again."),
    "retry": ("다시 시도", "Try again"),
    "error": ("작업 중 오류가 났습니다.", "Something went wrong."),
    "need_login": ("Mendeley 로그인이 필요합니다.", "You need to sign in to Mendeley."),
    "need_setup": ("처음 한 번 설정이 필요합니다.", "First-time setup is needed."),
    "status": ("Zotero {z} · Mendeley {m} · EndNote {e}", "Zotero {z} · Mendeley {m} · EndNote {e}"),
    "st_ok": ("✓", "✓"),
    "st_login": ("로그인 필요", "sign-in needed"),
    "st_none": ("미설정", "not set"),
    # 설정 창
    "s_title": ("설정", "Settings"),
    "s_mendeley": ("1. Mendeley 연결", "1. Connect Mendeley"),
    "s_guide": ("Mendeley 개발자 사이트에서 앱을 한 번 등록해야 합니다(무료).\n"
                "① '개발자 사이트 열기' → Register a new app\n"
                "② Redirect URL에 아래 주소를 그대로 넣기\n"
                "③ Generate secret → 약관 동의 → 등록\n"
                "④ 받은 client ID와 secret을 아래에 넣고 '저장하고 로그인'",
                "Register a (free) app on the Mendeley developer site once.\n"
                "① 'Open developer site' → Register a new app\n"
                "② Paste the Redirect URL below exactly\n"
                "③ Generate secret → accept terms → register\n"
                "④ Enter the client ID and secret below and click 'Save and sign in'"),
    "s_open_dev": ("개발자 사이트 열기", "Open developer site"),
    "s_copy": ("복사", "Copy"),
    "s_copied": ("복사함", "Copied"),
    "s_cid": ("client ID", "Client ID"),
    "s_secret": ("client secret", "Client secret"),
    "s_secret_keep": ("바꾸지 않으려면 비워 두세요", "Leave empty to keep the current one"),
    "s_save_login": ("저장하고 로그인", "Save and sign in"),
    "s_login": ("다시 로그인", "Sign in again"),
    "s_zotero": ("2. Zotero 데이터 폴더", "2. Zotero data folder"),
    "s_zotero_tip": ("Zotero 설정 > 고급 > 파일 및 폴더의 '데이터 디렉터리 위치'", "Zotero Settings > Advanced > Files and Folders > Data Directory Location"),
    "s_browse": ("찾아보기…", "Browse…"),
    "s_target": ("3. Mendeley로 보낼 때 문헌을 넣을 곳", "3. Where to add references when sending to Mendeley"),
    "s_personal": ("내 개인 라이브러리", "My personal library"),
    "s_load_groups": ("그룹 불러오기", "Load groups"),
    "s_endnote": ("4. EndNote 라이브러리 (EndNote로 바꿀 때만, 선택)", "4. EndNote library (only for converting to EndNote, optional)"),
    "s_endnote_tip": ("고르면 인용을 내 EndNote 라이브러리의 문헌과 연결합니다.", "If set, citations are linked to records in your EndNote library."),
    "s_bad_endnote": ("EndNote 라이브러리(.enl) 파일을 고르세요.", "Choose an EndNote library (.enl) file."),
    "s_close": ("닫기", "Close"),
    "s_state_ok": ("로그인됨", "Signed in"),
    "s_state_no": ("로그인 안 됨", "Not signed in"),
    "s_need_cid": ("client ID를 입력하세요.", "Enter the client ID."),
    "s_need_secret": ("client secret을 입력하세요.", "Enter the client secret."),
    "s_bad_zotero": ("이 폴더에 zotero.sqlite가 없습니다.", "zotero.sqlite was not found in this folder."),
    # 로그인 창
    "l_title": ("Mendeley 로그인", "Sign in to Mendeley"),
    "l_text": ("브라우저에서 Mendeley 로그인 창이 열렸습니다.\n로그인하고 '허용'을 누르면 자동으로 이어집니다.",
               "A Mendeley sign-in page opened in your browser.\nSign in and click 'Allow' — this window continues automatically."),
    "l_paste": ("브라우저에 오류 화면이 남으면, 그 창의 주소 전체를 복사해 붙여 넣으세요:",
                "If the browser shows an error page, copy its full address and paste it here:"),
    "l_apply": ("적용", "Apply"),
}


def tr(key, **kw):
    s = T[key][0 if KO else 1]
    return s.format(**kw) if kw else s


def value(out, key):
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line[len(key) + 1:]
    return ""


def last_line(out):
    lines = [x for x in out.strip().splitlines() if x.strip()]
    return lines[-1] if lines else ""


# ---------- 백그라운드 실행 ----------

class Runner(QObject):
    """zms 명령을 작업 스레드에서 돌리고, 끝나면 (코드, 출력) 을 화면 스레드로 넘긴다."""
    done = Signal(int, str)

    def start(self, argv):
        threading.Thread(target=lambda: self.done.emit(*zms.run(argv)), daemon=True).start()


def run_blocking(parent, argv, message=None):
    """짧은 작업을 돌리는 동안 커서를 바꾸고 이벤트를 처리하며 기다린다."""
    result = {}
    ev = threading.Event()

    def work():
        result["r"] = zms.run(argv)
        ev.set()

    QGuiApplication.setOverrideCursor(Qt.WaitCursor)
    if message and parent is not None and hasattr(parent, "set_busy"):
        parent.set_busy(message)
    threading.Thread(target=work, daemon=True).start()
    while not ev.wait(0.03):
        QApplication.processEvents()
    QGuiApplication.restoreOverrideCursor()
    if message and parent is not None and hasattr(parent, "set_busy"):
        parent.set_busy(None)
    return result["r"]


def reveal(path):
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path])
    elif os.name == "nt":
        subprocess.run(["explorer", "/select,", os.path.normpath(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


def show_error(parent, code, out):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(APP)
    box.setText(tr("error"))
    box.setInformativeText(last_line(out))
    box.setDetailedText(out)
    box.exec()


# ---------- 로그인 창 ----------

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("l_title"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("l_text")))
        hint = QLabel(tr("l_paste"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)
        row = QHBoxLayout()
        self.paste = QLineEdit()
        self.paste.setPlaceholderText("http://localhost:53682/callback?code=…")
        apply_btn = QPushButton(tr("l_apply"))
        apply_btn.clicked.connect(self.apply_paste)
        row.addWidget(self.paste)
        row.addWidget(apply_btn)
        lay.addLayout(row)
        cancel = QPushButton(tr("cancel"))
        cancel.clicked.connect(self.cancel)
        lay.addWidget(cancel, alignment=Qt.AlignRight)
        self.result_code, self.result_out = None, ""
        zms.PASTE_QUEUE = queue.Queue()
        zms.CANCEL.clear()
        self.runner = Runner()
        self.runner.done.connect(self.finished_auth)
        self.runner.start(["auth", "--timeout", "300"])

    def apply_paste(self):
        if self.paste.text().strip():
            zms.PASTE_QUEUE.put(self.paste.text().strip())

    def cancel(self):
        zms.CANCEL.set()

    def reject(self):  # Esc·창 닫기도 취소로 처리해 작업 스레드를 끝낸다
        zms.CANCEL.set()

    def finished_auth(self, code, out):
        zms.PASTE_QUEUE = None
        self.result_code, self.result_out = code, out
        self.done(0)


def login(parent):
    dlg = LoginDialog(parent)
    dlg.exec()
    if dlg.result_code == 0:
        return True
    if dlg.result_code not in (zms.EXIT_CANCEL, None):
        show_error(parent, dlg.result_code, dlg.result_out)
    return False


# ---------- 설정 창 ----------

class SettingsDialog(QDialog):
    def __init__(self, parent=None, welcome=False):
        super().__init__(parent)
        self.setWindowTitle(tr("s_title"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        if welcome:
            w = QLabel(tr("need_setup"))
            w.setStyleSheet("font-weight: 600;")
            lay.addWidget(w)
        conf = zms.conf_raw()

        g1 = QGroupBox(tr("s_mendeley"))
        f1 = QVBoxLayout(g1)
        guide = QLabel(tr("s_guide"))
        guide.setWordWrap(True)
        f1.addWidget(guide)
        row = QHBoxLayout()
        self.redirect = QLineEdit(conf.get("redirect_uri") or zms.REDIRECT_DEFAULT)
        self.redirect.setReadOnly(True)
        copy = QPushButton(tr("s_copy"))
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.redirect.text()),
                                      copy.setText(tr("s_copied"))))
        dev = QPushButton(tr("s_open_dev"))
        dev.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DEV_SITE)))
        row.addWidget(QLabel("Redirect URL"))
        row.addWidget(self.redirect)
        row.addWidget(copy)
        f1.addLayout(row)
        f1.addWidget(dev, alignment=Qt.AlignLeft)
        form = QFormLayout()
        self.cid = QLineEdit(conf.get("client_id") or "")
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
        if conf.get("client_secret"):
            self.secret.setPlaceholderText(tr("s_secret_keep"))
        form.addRow(tr("s_cid"), self.cid)
        form.addRow(tr("s_secret"), self.secret)
        f1.addLayout(form)
        row2 = QHBoxLayout()
        self.login_state = QLabel()
        save = QPushButton(tr("s_save_login"))
        save.setDefault(True)
        save.clicked.connect(self.save_and_login)
        row2.addWidget(self.login_state)
        row2.addStretch()
        row2.addWidget(save)
        f1.addLayout(row2)
        lay.addWidget(g1)

        g2 = QGroupBox(tr("s_zotero"))
        f2 = QVBoxLayout(g2)
        row3 = QHBoxLayout()
        self.zdir = QLineEdit(str(zms.zotero_db().parent))
        self.zdir.setReadOnly(True)
        browse = QPushButton(tr("s_browse"))
        browse.clicked.connect(self.choose_zotero)
        row3.addWidget(self.zdir)
        row3.addWidget(browse)
        f2.addLayout(row3)
        tip = QLabel(tr("s_zotero_tip"))
        tip.setStyleSheet("color: gray;")
        f2.addWidget(tip)
        lay.addWidget(g2)

        g3 = QGroupBox(tr("s_target"))
        f3 = QHBoxLayout(g3)
        self.group = QComboBox()
        self.group.addItem(tr("s_personal"), "")
        if conf.get("group"):
            self.group.addItem(conf["group"], conf["group"])
            self.group.setCurrentIndex(1)
        self.group.currentIndexChanged.connect(self.save_group)
        load = QPushButton(tr("s_load_groups"))
        load.clicked.connect(self.load_groups)
        f3.addWidget(self.group, 1)
        f3.addWidget(load)
        lay.addWidget(g3)

        g4 = QGroupBox(tr("s_endnote"))
        f4 = QVBoxLayout(g4)
        row4 = QHBoxLayout()
        self.enl = QLineEdit(str(zms.endnote_library()))
        self.enl.setReadOnly(True)
        browse4 = QPushButton(tr("s_browse"))
        browse4.clicked.connect(self.choose_endnote)
        row4.addWidget(self.enl)
        row4.addWidget(browse4)
        f4.addLayout(row4)
        tip4 = QLabel(tr("s_endnote_tip"))
        tip4.setStyleSheet("color: gray;")
        f4.addWidget(tip4)
        lay.addWidget(g4)

        close = QPushButton(tr("s_close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignRight)
        self.refresh_state()

    def refresh_state(self):
        ok = (zms.CONF_DIR / "token.json").exists()
        self.login_state.setText(("✓ " if ok else "• ") + tr("s_state_ok" if ok else "s_state_no"))
        self.login_state.setStyleSheet("color: #1a7f37;" if ok else "color: #b42318;")

    def save_and_login(self):
        cid = self.cid.text().strip()
        sec = self.secret.text().strip()
        if not cid:
            QMessageBox.warning(self, APP, tr("s_need_cid"))
            return
        if not sec and not zms.conf_raw().get("client_secret"):
            QMessageBox.warning(self, APP, tr("s_need_secret"))
            return
        # secret 은 명령줄이 아닌 프로세스 환경으로만 넘기고 바로 지운다
        if sec:
            os.environ["ZMS_CLIENT_SECRET"] = sec
        try:
            code, out = zms.run(["config", "--client-id", cid])
        finally:
            os.environ.pop("ZMS_CLIENT_SECRET", None)
        if code != 0:
            show_error(self, code, out)
            return
        self.secret.clear()
        login(self)
        self.refresh_state()

    def choose_zotero(self):
        d = QFileDialog.getExistingDirectory(self, tr("s_zotero"), self.zdir.text())
        if not d:
            return
        if not (Path(d) / "zotero.sqlite").exists():
            QMessageBox.warning(self, APP, tr("s_bad_zotero"))
            return
        code, out = zms.run(["config", "--zotero-dir", d])
        if code == 0:
            self.zdir.setText(d)
        else:
            show_error(self, code, out)

    def choose_endnote(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("s_endnote"), str(Path(self.enl.text()).parent), "EndNote (*.enl)")
        if not f:
            return
        if not f.lower().endswith(".enl"):
            QMessageBox.warning(self, APP, tr("s_bad_endnote"))
            return
        code, out = zms.run(["config", "--endnote-library", f])
        if code == 0:
            self.enl.setText(f)
        else:
            show_error(self, code, out)

    def load_groups(self):
        code, out = run_blocking(self, ["groups"])
        if code == zms.EXIT_AUTH and login(self):
            code, out = run_blocking(self, ["groups"])
        if code != 0:
            show_error(self, code, out)
            return
        current = self.group.currentData()
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItem(tr("s_personal"), "")
        for line in out.splitlines():
            if line.startswith("GROUP=") and len(line) > 6:
                self.group.addItem(line[6:], line[6:])
        i = max(0, self.group.findData(current))
        self.group.setCurrentIndex(i)
        self.group.blockSignals(False)

    def save_group(self):
        zms.run(["config", "--group", self.group.currentData() or ""])


# ---------- 원고 놓는 칸 ----------

class DropZone(QFrame):
    def __init__(self, on_file):
        super().__init__()
        self.on_file = on_file
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self.setObjectName("drop")
        self.normal_style = ("#drop { border: 2px dashed #c9ced6; border-radius: 16px; background: palette(base); }")
        self.hover_style = ("#drop { border: 2px dashed #2f6feb; border-radius: 16px; background: rgba(47,111,235,0.06); }")
        self.setStyleSheet(self.normal_style)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        art = ASSETS / "dropzone.png"
        if art.exists():
            pic = QLabel()
            pic.setPixmap(QPixmap(str(art)).scaledToHeight(110, Qt.SmoothTransformation))
            pic.setAlignment(Qt.AlignCenter)
            lay.addWidget(pic)
        self.label = QLabel(tr("drop"))
        self.label.setAlignment(Qt.AlignCenter)
        f = self.label.font()
        f.setPointSize(f.pointSize() + 2)
        self.label.setFont(f)
        lay.addWidget(self.label)
        btn = QPushButton(tr("choose"))
        btn.clicked.connect(self.choose)
        lay.addWidget(btn, alignment=Qt.AlignCenter)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("choose"), str(Path.home()), "Word (*.docx)")
        if path:
            self.on_file(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(self.hover_style)

    def dragLeaveEvent(self, e):
        self.setStyleSheet(self.normal_style)

    def dropEvent(self, e):
        self.setStyleSheet(self.normal_style)
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.on_file(urls[0])


# ---------- 주 창 ----------

class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        self.setMinimumSize(760, 620)
        self.path = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)

        head = QHBoxLayout()
        icon = ASSETS / "icon.png"
        if icon.exists():
            ic = QLabel()
            ic.setPixmap(QPixmap(str(icon)).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            head.addWidget(ic)
        titles = QVBoxLayout()
        t = QLabel(APP)
        tf = QFont(t.font())
        tf.setPointSize(tf.pointSize() + 9)
        tf.setBold(True)
        t.setFont(tf)
        sub = QLabel(tr("subtitle"))
        sub.setStyleSheet("color: gray;")
        titles.addWidget(t)
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch()
        lay.addLayout(head)

        # 탭 ① 원고 변환 ② 라이브러리 비교
        self.tabs = QTabWidget()
        conv = QWidget()
        clay = QVBoxLayout(conv)
        clay.setContentsMargins(4, 10, 4, 4)
        self.drop = DropZone(self.set_file)
        clay.addWidget(self.drop)

        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setMinimumHeight(44)
        clay.addWidget(self.file_label)

        acts = QHBoxLayout()
        self.buttons = {}
        for fmt, color in (("zotero", "#a4161a"), ("mendeley", "#2f6feb"), ("endnote", "#3d4451")):
            b = self.action_button(tr("to_" + fmt), "", color)
            b.clicked.connect(lambda _=False, f=fmt: self.convert(f))
            acts.addWidget(b)
            self.buttons[fmt] = b
        clay.addLayout(acts)
        clay.addStretch()
        self.tabs.addTab(conv, tr("tab_convert"))
        self.compare_page = ComparePage(self)
        self.tabs.addTab(self.compare_page, tr("tab_compare"))
        lay.addWidget(self.tabs, 1)

        self.busy = QLabel()
        self.busy.setAlignment(Qt.AlignCenter)
        self.busy.setStyleSheet("color: #2f6feb;")
        lay.addWidget(self.busy)

        foot = QHBoxLayout()
        self.status = QLabel()
        self.status.setStyleSheet("color: gray;")
        help_btn = QPushButton(tr("help"))
        help_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(HELP_URL)))
        set_btn = QPushButton(tr("settings"))
        set_btn.clicked.connect(self.open_settings)
        foot.addWidget(self.status, 1)
        foot.addWidget(help_btn)
        foot.addWidget(set_btn)
        lay.addLayout(foot)
        self.update_actions(None)
        self.refresh_status()

    def action_button(self, title, sub, color):
        b = QPushButton(f"{title}\n{sub}")
        b.setMinimumHeight(64)
        b.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border: none; border-radius: 12px; "
            f"font-weight: 600; padding: 8px; }} QPushButton:disabled {{ background: #d0d4da; color: #7a808a; }}")
        return b

    def set_busy(self, msg):
        self.busy.setText(msg or "")
        for w in list(self.buttons.values()) + [self.drop]:
            w.setEnabled(msg is None)
        if msg is None:
            self.update_actions(getattr(self, "kind", None))

    def refresh_status(self):
        _, out = zms.run(["status"])
        z = tr("st_ok") if value(out, "ZOTERO_DB") == "ok" else tr("st_none")
        if value(out, "MENDELEY_KEYS") != "ok":
            m = tr("st_none")
        else:
            m = tr("st_ok") if value(out, "MENDELEY_LOGIN") == "ok" else tr("st_login")
        e = tr("st_ok") if value(out, "ENDNOTE") == "ok" else tr("st_none")
        self.status.setText(tr("status", z=z, m=m, e=e))
        return out

    def ensure_ready(self, target):
        """대상 형식에 필요한 준비만 확인한다. Mendeley 로 바꿀 때만 Mendeley 로그인이 필요하다."""
        out = self.refresh_status()
        if target == "zotero" and value(out, "ZOTERO_DB") != "ok":
            SettingsDialog(self, welcome=True).exec()
            return value(self.refresh_status(), "ZOTERO_DB") == "ok"
        if target == "mendeley":
            if value(out, "MENDELEY_KEYS") != "ok":
                SettingsDialog(self, welcome=True).exec()
                out = self.refresh_status()
                if value(out, "MENDELEY_KEYS") != "ok":
                    return False
            if value(out, "MENDELEY_LOGIN") != "ok":
                ok = login(self)
                self.refresh_status()
                return ok
        return True

    def open_settings(self):
        SettingsDialog(self).exec()
        self.refresh_status()

    def update_actions(self, kind, counts=None):
        self.kind = kind
        self.counts = counts or getattr(self, "counts", {})
        present = [f for f in zms.FORMATS if self.counts.get(f)]
        src = " · ".join(zms.FORMAT_NAME[f] for f in present)
        for fmt, b in self.buttons.items():
            # 원고에 다른 형식의 인용이 있어야 그 형식으로 바꿀 수 있다
            on = bool(kind) and kind != "none" and any(f != fmt for f in present)
            b.setEnabled(on)
            sub = tr("to_sub", src=src, dst=zms.FORMAT_NAME[fmt]) if on else ""
            b.setText(tr("to_" + fmt) + ("\n" + sub if sub else ""))

    def set_file(self, path):
        if not path.lower().endswith(".docx"):
            QMessageBox.information(self, APP, tr("only_docx"))
            return
        self.path = path
        code, out = zms.run(["detect", path])
        if code != 0:
            show_error(self, code, out)
            return
        kind = value(out, "KIND")
        counts = {f: int(value(out, f.upper()) or 0) for f in zms.FORMATS}
        if kind in zms.FORMATS:
            info = tr("kind_one", fmt=zms.FORMAT_NAME[kind], n=counts[kind])
        elif kind == "mixed":
            info = tr("kind_mixed", parts=", ".join(f"{zms.FORMAT_NAME[f]} {n}" for f, n in counts.items() if n))
        else:
            info = tr("kind_none")
        self.file_label.setText(f"<b>{Path(path).name}</b><br><span style='color:gray'>{info}</span>")
        self.update_actions(kind, counts)

    def run_with_login(self, argv, message):
        code, out = run_blocking(self, argv, message)
        if code == zms.EXIT_AUTH:
            QMessageBox.information(self, APP, tr("need_login"))
            if login(self):
                self.refresh_status()
                code, out = run_blocking(self, argv, message)
        return code, out

    def convert(self, target):
        if not self.path or not self.ensure_ready(target):
            return
        name = zms.FORMAT_NAME[target]
        argv = ["convert", self.path, "--to", target]
        if target == "mendeley":
            code, out = self.run_with_login(argv + ["--add-missing"], tr("working", fmt=name))
        else:
            code, out = run_blocking(self, argv, tr("working", fmt=name))
            if code == zms.EXIT_MISSING:
                if not self.ask_missing(target, out):
                    return
                code, out = run_blocking(self, argv + ["--allow-unlinked"], tr("working", fmt=name))
        if code != 0:
            show_error(self, code, out)
            return
        msg = tr("done", n=value(out, "CITES"), fmt=name)
        if value(out, "ADDED") not in ("", "0"):
            msg += "\n" + tr("done_added", n=value(out, "ADDED"))
        if value(out, "UNLINKED") not in ("", "0"):
            msg += "\n" + tr("done_unl", n=value(out, "UNLINKED"), fmt=name)
        self.show_result(msg + "\n\n" + tr("tip_" + target), value(out, "OUT"))

    def ask_missing(self, target, out):
        """라이브러리에 없는 문헌이 있을 때 어떻게 할지 묻는다. 계속하면 True."""
        box = QMessageBox(self)
        box.setWindowTitle(APP)
        box.setIcon(QMessageBox.Question)
        n = value(out, "MISSING")
        if target == "zotero":
            box.setText(tr("missing_q", n=n))
            add = box.addButton(tr("add_and_convert"), QMessageBox.AcceptRole)
        else:
            box.setText(tr("en_missing_q", n=n))
            add = box.addButton(tr("show_import_file"), QMessageBox.ActionRole)
        only = box.addButton(tr("convert_only"), QMessageBox.AcceptRole if target != "zotero" else QMessageBox.ActionRole)
        box.addButton(tr("cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(add if target == "zotero" else only)
        box.exec()
        if box.clickedButton() is add:
            if target == "zotero":
                return self.import_to_zotero(value(out, "MISSING_FILE"))
            reveal(value(out, "MISSING_FILE"))
            return False
        return box.clickedButton() is only

    def import_to_zotero(self, json_path):
        while True:
            code, out = run_blocking(self, ["zotero-import", json_path], tr("working_import"))
            if code == 0:
                return True
            if code != zms.EXIT_ZOTERO_OFF:
                show_error(self, code, out)
                return False
            r = QMessageBox.question(self, APP, tr("zotero_off"), QMessageBox.Retry | QMessageBox.Cancel)
            if r != QMessageBox.Retry:
                return False

    def show_result(self, msg, out_path):
        box = QMessageBox(self)
        box.setWindowTitle(APP)
        box.setIcon(QMessageBox.Information)
        box.setText(msg)
        box.setInformativeText(tr("new_file", f=Path(out_path).name))
        word = box.addButton(tr("open_word"), QMessageBox.AcceptRole)
        folder = box.addButton(tr("reveal"), QMessageBox.ActionRole)
        box.addButton(tr("ok"), QMessageBox.RejectRole)
        box.setDefaultButton(word)
        box.exec()
        if box.clickedButton() is word:
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_path))
        elif box.clickedButton() is folder:
            reveal(out_path)


# ---------- 라이브러리 비교 탭 ----------

def call_blocking(parent, fn, message=None):
    """오래 걸리는 함수(Mendeley 내려받기 등)를 작업 스레드에서 돌리며 화면을 살려 둔다. (결과, 예외)"""
    box = {}
    ev = threading.Event()

    def work():
        try:
            box["r"] = fn()
        except BaseException as e:  # zms 는 오류 때 sys.exit 를 부른다
            box["e"] = e
        ev.set()

    QGuiApplication.setOverrideCursor(Qt.WaitCursor)
    if message and hasattr(parent, "set_busy"):
        parent.set_busy(message)
    threading.Thread(target=work, daemon=True).start()
    while not ev.wait(0.03):
        QApplication.processEvents()
    QGuiApplication.restoreOverrideCursor()
    if message and hasattr(parent, "set_busy"):
        parent.set_busy(None)
    return box.get("r"), box.get("e")


class ComparePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.kind, self.name, self.group_id = "", "", None
        self.theirs, self.refs, self.cols = [], [], {}
        self.result = ([], [], [], [])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 10, 4, 4)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("c_theirs")))
        for key, slot in (("c_manuscript", self.pick_manuscript), ("c_mendeley", self.pick_mendeley),
                          ("c_endnote", self.pick_endnote)):
            b = QPushButton(tr(key))
            b.clicked.connect(slot)
            top.addWidget(b)
        top.addSpacing(16)
        top.addWidget(QLabel(tr("c_mine")))
        self.scope = QComboBox()
        self.scope.currentIndexChanged.connect(self.recompute)
        top.addWidget(self.scope, 1)
        lay.addLayout(top)
        self.summary = QLabel(tr("c_pick"))
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("padding: 6px 0;")
        lay.addWidget(self.summary)
        self.bar = QTabBar()
        for t in tr("c_tabs"):
            self.bar.addTab(t)
        self.bar.currentChanged.connect(self.show_list)
        lay.addWidget(self.bar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(list(tr("c_cols")))
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for c, w in ((0, 28), (2, 130), (3, 48), (4, 160), (5, 150), (6, 220)):
            self.table.setColumnWidth(c, w)
        lay.addWidget(self.table, 1)
        act = QHBoxLayout()
        self.check_all = QPushButton(tr("c_check_all"))
        self.check_all.clicked.connect(lambda: self.set_all(True))
        self.check_none = QPushButton(tr("c_check_none"))
        self.check_none.clicked.connect(lambda: self.set_all(False))
        act.addWidget(self.check_all)
        act.addWidget(self.check_none)
        act.addStretch()
        self.btn_zotero = QPushButton(tr("c_to_zotero"))
        self.btn_zotero.clicked.connect(self.add_to_zotero)
        self.btn_mendeley = QPushButton(tr("c_to_mendeley"))
        self.btn_mendeley.clicked.connect(self.add_to_mendeley)
        self.btn_xml = QPushButton(tr("c_to_xml"))
        self.btn_xml.clicked.connect(self.export_xml)
        for w in (self.btn_zotero, self.btn_mendeley, self.btn_xml):
            act.addWidget(w)
        lay.addLayout(act)
        self.show_list()

    # 내 쪽
    def load_mine(self):
        db = zms.zotero_db()
        if not db.exists():
            QMessageBox.information(self, APP, tr("c_zotero_needed"))
            self.main.open_settings()
            db = zms.zotero_db()
            if not db.exists():
                return False
        self.refs, self.cols = compare.load_zotero(db)
        cur = self.scope.currentData()
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem(tr("c_all"), None)
        for cid in sorted(self.cols, key=lambda c: compare.col_path(self.cols, c).lower()):
            self.scope.addItem(compare.col_path(self.cols, cid), cid)
        self.scope.setCurrentIndex(max(0, self.scope.findData(cur)))
        self.scope.blockSignals(False)
        return True

    def mine(self):
        cid = self.scope.currentData()
        return self.refs if cid is None else compare.in_collection(self.refs, self.cols, cid)

    # 상대 쪽
    def load_theirs(self, kind, name, fn):
        if not self.load_mine():
            return
        r, e = call_blocking(self.main, fn, tr("c_loading"))
        if isinstance(e, SystemExit) and e.code == zms.EXIT_AUTH and login(self):
            r, e = call_blocking(self.main, fn, tr("c_loading"))
        if e is not None:
            QMessageBox.warning(self, APP, tr("c_read_fail") + f"\n{e}")
            return
        self.theirs, self.kind, self.name = r, kind, name
        self.recompute()

    def pick_manuscript(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("c_manuscript"), str(Path.home()), "Word (*.docx)")
        if path:
            self.group_id = None
            self.load_theirs("manuscript", Path(path).name, lambda: compare.from_manuscript(path, zms))

    def pick_mendeley(self):
        if not self.main.ensure_ready("mendeley"):
            return
        groups, e = call_blocking(self.main, zms.list_groups, tr("c_loading"))
        if e is not None:
            QMessageBox.warning(self, APP, tr("c_read_fail") + f"\n{e}")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Mendeley")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("c_mendeley_lib")))
        lst = QListWidget()
        w = QListWidgetItem(tr("c_mendeley_personal"))
        w.setData(Qt.UserRole, None)
        lst.addItem(w)
        for g in groups or []:
            w = QListWidgetItem(tr("c_mendeley_group", g=g.get("name", "")))
            w.setData(Qt.UserRole, (g["id"], g.get("name", "")))
            lst.addItem(w)
        lst.setCurrentRow(0)
        lay.addWidget(lst)
        if not groups:
            hint = QLabel(tr("c_no_groups"))
            hint.setStyleSheet("color: gray;")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted or not lst.currentItem():
            return
        g = lst.currentItem().data(Qt.UserRole)
        self.group_id = g[0] if g else None
        name = tr("c_mendeley_group", g=g[1]) if g else tr("c_mendeley_personal")
        gid = self.group_id
        self.load_theirs("mendeley", name, lambda: compare.from_mendeley(zms, gid))

    def pick_endnote(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("c_endnote"), str(Path.home()), tr("c_endnote_filter"))
        if not path:
            return
        self.group_id = None
        if path.lower().endswith(".enl"):
            self.load_theirs("endnote", Path(path).name, lambda: compare.from_endnote_library(path))
        else:
            self.load_theirs("endnote", Path(path).name, lambda: compare.from_endnote_xml(path, zms))

    # 비교 · 보기
    def recompute(self):
        if not self.kind:
            return
        mine = self.mine()
        self.result = compare.compare(mine, self.theirs)
        a, b, c, x = self.result
        text = tr("c_summary", src=html.escape(self.name), n=len(self.theirs), scope=html.escape(self.scope.currentText()),
                  m=len(mine), a=len(a), b=len(b), c=len(c))
        if x:
            text += tr("c_conflicts", x=len(x))
        self.summary.setText(text)
        for i, n in enumerate((len(a), len(b), len(c), len(x))):
            self.bar.setTabText(i, f"{tr('c_tabs')[i]} {n:,}")
        self.show_list()

    def show_list(self):
        tab = self.bar.currentIndex()
        a, b, c, x = self.result
        labels = tr("c_labels")

        def diff(r, cc):
            return "; ".join(f"{n}: {m or '—'} → {t or '—'}" for n, m, t in compare.differences(r, cc, labels))

        def mine_row(r, extra="", doi=None):
            return (r.title, r.authors_text, r.year, r.source, r.doi if doi is None else doi, extra)
        rows = ([compare.csl_brief(cc) + ("",) for cc in a] if tab == 0 else
                [mine_row(r) for r in b] if tab == 1 else
                [mine_row(r, diff(r, cc)) for r, cc in c] if tab == 2 else
                [mine_row(r, diff(r, cc), tr("c_my_doi", a=r.doi, b=cc.get("DOI", ""))) for r, cc in x])
        self.table.setColumnHidden(6, tab < 2)
        self.table.setRowCount(len(rows))
        for i, vals in enumerate(rows):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, chk)
            for col, v in enumerate(vals, 1):
                self.table.setItem(i, col, QTableWidgetItem(str(v or "")))
        has = bool(rows)
        self.btn_zotero.setVisible(tab == 0)
        self.btn_mendeley.setVisible(tab == 1 and self.kind == "mendeley")
        self.btn_xml.setVisible(tab == 1)
        for w in (self.btn_zotero, self.btn_mendeley, self.btn_xml, self.check_all, self.check_none):
            w.setEnabled(has)
        self.check_all.setVisible(tab < 2)
        self.check_none.setVisible(tab < 2)

    def set_all(self, on):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def checked(self):
        rows = [i for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
        if not rows:
            QMessageBox.information(self, APP, tr("c_choose_some"))
        return rows

    # 채우기
    def add_to_zotero(self):
        rows = self.checked()
        if not rows:
            return
        items = [self.result[0][i] for i in rows]
        tmp = APP_DIR / "data" / "compare_import.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(__import__("json").dumps(items, ensure_ascii=False), encoding="utf-8")
        tag = f"CiteSwap: {self.name}"[:80]
        while True:
            code, out = run_blocking(self.main, ["zotero-import", str(tmp), "--tag", tag], tr("working_import"))
            if code == 0:
                break
            if code != zms.EXIT_ZOTERO_OFF:
                show_error(self, code, out)
                return
            if QMessageBox.question(self, APP, tr("zotero_off"), QMessageBox.Retry | QMessageBox.Cancel) != QMessageBox.Retry:
                return
        QMessageBox.information(self, APP, tr("c_added_zotero", n=value(out, "IMPORTED") or len(items), tag=tag))
        if self.load_mine():  # Zotero 가 쓰는 데 잠깐 걸린다 — 다시 읽어 표를 새로 고친다
            self.recompute()

    def add_to_mendeley(self):
        rows = self.checked()
        if not rows:
            return
        refs = [self.result[1][i] for i in rows]
        gid = self.group_id

        def post():
            done = 0
            for r in refs:
                body = zms.csl_to_mendeley(compare.ref_to_csl(r))  # 원고 변환 때 쓰는 것과 같은 변환
                if gid:
                    body["group_id"] = gid
                zms.api("POST", "/documents", body=body)
                done += 1
            return done
        done, e = call_blocking(self.main, post, tr("c_loading"))
        if e is not None:
            QMessageBox.warning(self, APP, tr("c_stopped", n=done or 0) + f"\n{e}")
            return
        QMessageBox.information(self, APP, tr("c_added_mendeley", n=done, dst=self.name))
        self.load_theirs("mendeley", self.name, lambda: compare.from_mendeley(zms, gid))

    def export_xml(self):
        rows = self.checked()
        if not rows:
            return
        csls = [compare.ref_to_csl(self.result[1][i]) for i in rows]
        path, _ = QFileDialog.getSaveFileName(self, tr("c_to_xml"), str(Path.home() / tr("c_xml_name")), "EndNote XML (*.xml)")
        if not path:
            return
        Path(path).write_text(compare.endnote_xml(csls, zms), encoding="utf-8")
        QMessageBox.information(self, APP, tr("c_saved_xml", n=len(csls)))


class App(QApplication):
    """macOS 에서 Dock 아이콘에 파일을 끌어다 놓으면 FileOpen 이벤트로 들어온다."""

    def __init__(self, argv):
        super().__init__(argv)
        self.window = None
        self.pending = None

    def event(self, e):
        if e.type() == QEvent.FileOpen:
            if self.window:
                self.window.set_file(e.file())
            else:
                self.pending = e.file()
            return True
        return super().event(e)


def main():
    app = App(sys.argv)
    app.setApplicationName(APP)
    if (ASSETS / "icon.png").exists():
        app.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
    w = Main()
    app.window = w
    w.show()
    # Windows 에서는 exe 아이콘에 끌어다 놓은 파일이 명령줄 인자로 들어온다
    first = app.pending or next((a for a in sys.argv[1:] if a.lower().endswith(".docx")), None)
    if first:
        w.set_file(first)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
