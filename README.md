# CiteSwap

**레퍼런스 매니저 호환 · 변환 — Zotero · Mendeley · EndNote** · [English below](#english)

서로 다른 문헌 관리 프로그램을 쓰는 공저자와 같은 원고로 일하기 위한 데스크톱 앱입니다(macOS · Windows).

| 탭 | 하는 일 |
|---|---|
| **원고 변환** | Word 원고의 인용을 Zotero · Mendeley Cite · EndNote 형식 사이에서 바꿉니다(6방향). 원본은 그대로 두고 `원고_zotero.docx` 같은 사본을 만듭니다. |
| **라이브러리 비교** | 공저자의 Word 원고, Mendeley 라이브러리(개인 · 그룹), EndNote 라이브러리(`.enl`)나 XML을 내 Zotero와 대조합니다. '상대에게만 · 내게만 · 양쪽 다 · DOI 충돌'로 나눠 보여 주고, 서로 없는 문헌을 채웁니다. |

- 라이브러리 비교의 짝짓기: DOI가 양쪽에 있으면 DOI로만, 없으면 전체 제목 · 연도 · 첫 저자로 짝짓습니다. 제목은 같은데 DOI가 다르면 같은 문헌으로 치지 않고 'DOI 충돌'로 따로 보입니다. 양쪽에 다 있는 문헌은 제목 · 첫 저자 · 연도 · 게재지 차이를 보여 줍니다.
- 채우기: 상대에게만 있는 문헌 → **내 Zotero에 넣기**(Zotero에서 지금 고른 컬렉션, 태그 `CiteSwap: <상대 이름>`). 내게만 있는 문헌 → **Mendeley에 넣기**(상대가 Mendeley일 때) 또는 **EndNote XML로 저장**(공저자가 EndNote에서 가져오기).
- 내 Zotero는 데이터 파일 사본을 **읽기만** 합니다. 문헌을 넣을 때만 실행 중인 Zotero의 커넥터 기능을 씁니다.

> Zotero, Mendeley, Elsevier, EndNote(Clarivate)와 관계없는 개인 프로젝트입니다. 각 이름은 해당 소유자의 상표입니다.
> [Zoteley](https://github.com/hspark-rm/zoteley)의 후속 앱입니다. Zoteley 설정(Mendeley 앱 등록 · 로그인)이 있으면 처음 실행 때 그대로 가져옵니다.

## 내려받기

[Releases](https://github.com/hspark-rm/citeswap/releases/latest)에서 내려받습니다.

| 컴퓨터 | 파일 |
|---|---|
| Mac (M1·M2·M3·M4) | `CiteSwap-mac-apple-silicon.dmg` |
| Mac (Intel) | `CiteSwap-mac-intel.dmg` |
| Windows 10 · 11 | `CiteSwap-windows.zip` |

### 처음 열 때 보안 경고

코드 서명을 하지 않은 무료 앱이라 처음 한 번 경고가 뜹니다. 운영체제 보안 기능을 끌 필요는 없습니다.

- **Mac**: dmg를 열고 CiteSwap을 응용 프로그램 폴더로 끌어다 놓습니다. 앱을 열면 경고가 뜹니다 → **시스템 설정 > 개인정보 보호 및 보안** 아래쪽의 **그래도 열기**를 누릅니다.
- **Windows**: zip을 풀고 `CiteSwap\CiteSwap.exe`를 실행합니다. "Windows의 PC 보호" 창이 뜨면 **추가 정보 > 실행**을 누릅니다.

## 처음 설정

필요한 것만 하면 됩니다.

1. **Zotero 데이터 폴더**: 보통 홈 폴더의 `Zotero`라 자동으로 찾습니다. 다르면 설정에서 Zotero 설정 > 고급 > 파일 및 폴더의 위치를 고릅니다.
2. **Mendeley (Mendeley로 바꾸거나 Mendeley와 비교할 때만)**: 무료 Mendeley 앱 등록이 한 번 필요합니다.
   1. 설정에서 **개발자 사이트 열기**(dev.mendeley.com) → **Register a new app**.
   2. **Redirect URL**에 `http://localhost:53682/callback`을 넣고 **Generate secret** → 약관 동의 → 등록.
   3. 받은 **client ID**와 **secret**을 설정에 넣고 **저장하고 로그인**.
3. **EndNote 라이브러리 (선택)**: EndNote로 바꿀 때 내 라이브러리 문헌과 연결하려면 `.enl` 파일을 고릅니다.

## 쓰는 법

**원고 변환**: Word 원고(.docx)를 창에 끌어다 놓고 바꿀 형식의 단추를 누릅니다. 다 되면 Word에서 그 프로그램의 새로고침을 한 번 누릅니다(Zotero: Refresh, Mendeley Cite: 참고문헌 새로고침, EndNote: Update Citations and Bibliography).

**라이브러리 비교**: 위쪽에서 상대(공저자 원고 · Mendeley · EndNote)를 고르고, 필요하면 '내 Zotero' 범위를 컬렉션으로 좁힙니다. 탭을 옮겨 가며 결과를 보고, 왼쪽 칸에 표시한 문헌을 넣거나 저장합니다.

## 개인정보

- 문헌 자료는 내 컴퓨터 안에서 처리합니다. 외부로 나가는 것은 Mendeley를 쓸 때의 Mendeley API(내 계정)뿐입니다.
- Mendeley 비밀값과 로그인 토큰은 내 컴퓨터의 설정 폴더(Mac `~/Library/Application Support/CiteSwap`, Windows `%APPDATA%\CiteSwap`)에만 저장합니다.

## 소스에서 실행

```bash
python -m pip install -r requirements.txt
python gui.py
```
명령줄 엔진: `python zms.py --help` (`convert`, `detect`, `zotero-import` 등). 시험: `python -m pytest -q tests`.

## 라이선스

MIT

---

<a id="english"></a>

# CiteSwap (English)

**Reference manager compatibility — Zotero · Mendeley · EndNote.** A desktop app (macOS · Windows) for working on the same manuscript with co-authors who use a different reference manager.

| Tab | What it does |
|---|---|
| **Convert manuscript** | Converts Word manuscript citations among Zotero, Mendeley Cite and EndNote (all 6 directions). The original is untouched; a copy such as `paper_zotero.docx` is created. |
| **Compare libraries** | Compares a co-author's Word manuscript, a Mendeley library (personal or group), or an EndNote library (`.enl`) or XML with your Zotero library: only theirs · only mine · in both · DOI conflicts. Fills the gaps in either direction. |

- Matching: by DOI when both sides have one; otherwise by full title, year and first author. Same title with different DOIs is reported as a **DOI conflict**, not merged. For references in both, differences in title, first author, year and source are shown.
- Filling gaps: only-theirs → **Add to my Zotero** (into the collection selected in Zotero, tagged `CiteSwap: <source>`). Only-mine → **Add to Mendeley** (when comparing with Mendeley) or **Save as EndNote XML** for an EndNote co-author.
- Your Zotero database is only **read** from a copy. Adding references uses the running Zotero's connector.

> A personal project, not affiliated with Zotero, Mendeley, Elsevier or EndNote (Clarivate). Names are trademarks of their owners.
> Successor of [Zoteley](https://github.com/hspark-rm/zoteley); existing Zoteley settings (Mendeley app and sign-in) are imported on first run.

## Download

From [Releases](https://github.com/hspark-rm/citeswap/releases/latest): `CiteSwap-mac-apple-silicon.dmg`, `CiteSwap-mac-intel.dmg`, `CiteSwap-windows.zip` (Windows 10 · 11).

The app is not code-signed, so the first launch shows a warning. **Mac**: System Settings > Privacy & Security > **Open Anyway**. **Windows**: "Windows protected your PC" > **More info > Run anyway**. You do not need to turn off any security feature.

## Setup

1. **Zotero data folder**: found automatically (usually `~/Zotero`); otherwise choose it in Settings.
2. **Mendeley** (only to convert to or compare with Mendeley): register a free app at dev.mendeley.com once, with Redirect URL `http://localhost:53682/callback`, then enter the client ID and secret in Settings and sign in.
3. **EndNote library** (optional): choose your `.enl` to link converted citations to your EndNote records.

## Privacy

Everything runs locally. Only Mendeley features talk to the Mendeley API with your own account. Secrets and tokens stay in the settings folder on your computer.

## From source

```bash
python -m pip install -r requirements.txt
python gui.py
```

## License

MIT
