# 마크다운 필터링 로직 상세 분석 보고서

**작성일**: 2025-11-20
**작성자**: Claude Code
**버전**: 1.0
**대상 파일**: `backend/app/utils/markdown_parser.py` - `parse_markdown_to_md_elements()` 함수

---

## 1. 개요

마크다운 파일을 HWPX로 변환할 때, 변환 불가능한 요소들을 사전에 필터링하여 제거합니다. 본 보고서는 특히 **테이블(table)**과 **링크(link)** 필터링에 대한 정교한 정규식과 알고리즘을 정의합니다.

### 1.1 필터링 대상 (No Convert Type)

⚠️ **Unit Spec v1.6과의 정렬**: 다음은 변환 불가능한 요소들입니다. **인용(>)과 수평선(---)은 변환 가능하므로 필터링하지 않습니다.**

| No | 타입 | 마크다운 문법 | 필터링 필요성 | 우선도 | 상태 |
|----|------|----------|-----------|--------|------|
| 1 | 코드 블록 | `` ``` `` 또는 `~~~` | 높음 | 🔴 필수 | 필터링 |
| 2 | 테이블 | `\|` 구분선 | 높음 | 🔴 필수 | 필터링 |
| 3 | 이미지 | `![alt](url)` | 높음 | 🔴 필수 | 필터링 |
| 4 | 링크 | `[text](url)` 또는 `[text][ref]` | 높음 | 🔴 필수 | 필터링 |
| 5 | 체크박스 | `- [ ]` 또는 `- [x]` | 중간 | 🟡 권장 | 필터링 |
| 6 | HTML 태그 | `<script>`, `<style>` 등 위험 태그 | 중간 | 🟡 권장 | 필터링 |
| 7 | 주석 | `<!-- 주석 -->` | 낮음 | 🟢 선택 | 필터링 |
| — | **인용** | **`> 텍스트`** | **변환 필요** | **🔴 필수** | **파싱 (필터링 안 함)** |
| — | **수평선** | **`---` 또는 `***`** | **변환 필요** | **🔴 필수** | **파싱 (필터링 안 함)** |

---

## 2. 코드 블록 필터링 (Code Block)

### 2.1 정의

마크다운의 코드 블록은 다음 두 가지 형식을 지원:

```markdown
# 형식 1: 백틱 3개
```python
def hello():
    print("Hello")
```

# 형식 2: 틸드 3개
~~~javascript
const hello = () => console.log("Hello");
~~~
```

### 2.2 필터링 알고리즘

**단계 1: 코드 블록 시작/종료 감지**

```python
import re

def is_code_block_start(line: str) -> bool:
    """코드 블록 시작 여부 판별

    Args:
        line: 검사할 마크다운 라인

    Returns:
        True if 코드 블록 시작, False otherwise
    """
    # 백틱 3개 이상 또는 틸드 3개 이상
    return bool(re.match(r'^\s*(`{3,}|~{3,})', line))
```

**단계 2: 코드 블록 범위 추출**

```python
def extract_code_blocks(md_text: str) -> List[Tuple[int, int]]:
    """마크다운 텍스트에서 모든 코드 블록의 시작/종료 라인 번호 추출

    Args:
        md_text: 마크다운 전체 텍스트

    Returns:
        [(start_line, end_line), ...] 튜플 리스트
    """
    lines = md_text.split('\n')
    code_blocks = []
    in_code_block = False
    block_start = -1
    fence_char = None

    for i, line in enumerate(lines):
        if re.match(r'^\s*(`{3,}|~{3,})', line):
            match = re.match(r'^\s*(`{3,}|~{3,})', line)
            current_fence = match.group(1)[0]  # '`' 또는 '~'

            if not in_code_block:
                # 코드 블록 시작
                in_code_block = True
                block_start = i
                fence_char = current_fence
            elif current_fence == fence_char:
                # 같은 종류의 펜스로 닫힘
                in_code_block = False
                code_blocks.append((block_start, i))
                fence_char = None

    # 닫히지 않은 코드 블록 (파일 끝까지)
    if in_code_block:
        code_blocks.append((block_start, len(lines) - 1))

    return code_blocks

def is_in_code_block(line_num: int, code_blocks: List[Tuple[int, int]]) -> bool:
    """주어진 라인이 코드 블록 범위 내에 있는지 판별"""
    for start, end in code_blocks:
        if start <= line_num <= end:
            return True
    return False
```

### 2.3 테스트 케이스

```python
test_md = """# 제목

```python
def hello():
    print("Hello")
```

내용

~~~javascript
const x = 1;
~~~

더 이상 코드 블록 아님
"""

# 예상 결과
# Line 3-5: 코드 블록
# Line 10-12: 코드 블록
# Line 14: 일반 텍스트
```

---

## 3. 테이블 필터링 (Table)

### 3.1 마크다운 테이블 형식

**표준 GFM(GitHub Flavored Markdown) 테이블:**

```markdown
| 헤더1 | 헤더2 | 헤더3 |
|-------|-------|-------|
| 셀1-1 | 셀1-2 | 셀1-3 |
| 셀2-1 | 셀2-2 | 셀2-3 |
```

**테이블 구조:**
- 라인 1: 헤더 행 (파이프로 구분)
- 라인 2: 구분선 (대시와 파이프로 구성, 콜론으로 정렬 지정 가능)
- 라인 3+: 데이터 행

**구분선 형식:**
```
| :--- |   정렬: 좌측
| ---: |   정렬: 우측
| :---: |  정렬: 중앙
| --- |    정렬: 기본(좌측)
```

### 3.2 필터링 알고리즘

**단계 1: 테이블 구분선 정규식**

```python
import re

def is_table_separator(line: str) -> bool:
    """테이블 구분선 판별

    마크다운 테이블의 구분선은:
    - 파이프(|)로 시작하고 종료
    - 대시(-), 콜론(:), 파이프(|)만 포함
    - 최소 3개의 대시 필요 (예: ---)

    유효한 분리선:
    | --- | --- |
    |:---|---:|
    | : --- : |

    무효한 분리선:
    | - | - |        (대시가 1-2개)
    | a | b |        (문자 포함)
    """
    # 공백 제거
    stripped = line.strip()

    # 파이프로 시작 및 종료 확인
    if not (stripped.startswith('|') and stripped.endswith('|')):
        return False

    # 파이프 사이의 셀 추출
    cells = stripped.split('|')[1:-1]

    if not cells:
        return False

    # 각 셀이 유효한 분리선 형식인지 확인
    for cell in cells:
        cell_stripped = cell.strip()

        # 빈 셀은 무효
        if not cell_stripped:
            return False

        # 콜론, 대시, 공백만 포함하는지 확인
        if not re.match(r'^[:|-]*$', cell_stripped):
            return False

        # 최소 1개의 대시 필요
        if '-' not in cell_stripped:
            return False

    return True

def is_table_header(line: str) -> bool:
    """테이블 헤더 행 판별

    테이블 헤더는:
    - 파이프(|)로 구분된 셀들
    - 다음 라인이 구분선이어야 함

    주의: 단독으로는 판별 불가, 다음 라인과 함께 확인 필요
    """
    stripped = line.strip()

    # 파이프 포함 확인
    if '|' not in stripped:
        return False

    # 파이프로 시작 및 종료
    return stripped.startswith('|') and stripped.endswith('|')
```

**단계 2: 테이블 범위 추출**

```python
def extract_tables(md_text: str) -> List[Tuple[int, int]]:
    """마크다운에서 모든 테이블의 시작/종료 라인 번호 추출

    Args:
        md_text: 마크다운 전체 텍스트

    Returns:
        [(start_line, end_line), ...] 튜플 리스트
    """
    lines = md_text.split('\n')
    tables = []
    i = 0

    while i < len(lines):
        # 헤더 행 후보 찾기
        if is_table_header(lines[i]):
            # 다음 라인이 구분선인지 확인
            if i + 1 < len(lines) and is_table_separator(lines[i + 1]):
                # 테이블 시작 확인
                table_start = i
                i += 2  # 헤더와 구분선 스킵

                # 테이블 끝 찾기 (파이프가 없는 라인까지)
                while i < len(lines) and is_table_header(lines[i]):
                    i += 1

                tables.append((table_start, i - 1))
                continue

        i += 1

    return tables

def is_in_table(line_num: int, tables: List[Tuple[int, int]]) -> bool:
    """주어진 라인이 테이블 범위 내에 있는지 판별"""
    for start, end in tables:
        if start <= line_num <= end:
            return True
    return False
```

### 3.3 오탐(False Positive) 방지

**문제 케이스:**

```markdown
2022-11-20 | 판매액: 1,000원
A & B | C & D
가격: 100 | 수량: 5개
```

위의 경우는 테이블이 아니지만, 파이프(|)를 포함합니다.

**해결책:**

```python
def is_valid_table(table_start: int, table_end: int, lines: List[str]) -> bool:
    """테이블 유효성 확인

    GFM 테이블의 필수 조건:
    1. 헤더 행: |로 구분된 최소 1개 셀
    2. 구분선: 최소 1개의 대시(-)를 포함한 셀들
    3. 데이터 행 (선택): 헤더와 동일한 개수의 셀
    """
    if table_start >= len(lines) or table_start + 1 >= len(lines):
        return False

    header_line = lines[table_start]
    separator_line = lines[table_start + 1]

    # 헤더 셀 개수
    header_cells = [c.strip() for c in header_line.split('|')[1:-1]]

    # 구분선 셀 개수
    separator_cells = [c.strip() for c in separator_line.split('|')[1:-1]]

    # 셀 개수가 일치해야 함
    if len(header_cells) != len(separator_cells):
        return False

    # 최소 2개 이상의 셀 필요 (테이블이라고 볼 수 있음)
    if len(header_cells) < 2:
        return False

    return True
```

### 3.4 테스트 케이스

```python
test_cases = [
    # 유효한 테이블
    ("""| 이름 | 나이 |
| --- | --- |
| 홍길동 | 25 |
| 김영희 | 30 |""", True),

    # 정렬 포함
    ("""| 항목 | 가격 |
| :--- | ---: |
| 책 | 10,000 |""", True),

    # 오탐: 파이프만 있음
    ("2022-11-20 | 판매액: 1,000원", False),

    # 오탐: 셀 개수 불일치
    ("""| 헤더1 | 헤더2 |
| --- |
| 데이터1 | 데이터2 |""", False),
]

for md, expected in test_cases:
    tables = extract_tables(md)
    has_table = len(tables) > 0
    if has_table:
        has_table = is_valid_table(tables[0][0], tables[0][1], md.split('\n'))
    assert has_table == expected
```

---

## 4. 링크 필터링 (Link)

### 4.1 마크다운 링크 형식

마크다운은 여러 가지 링크 형식을 지원합니다:

```markdown
# 인라인 링크
[텍스트](https://example.com)
[텍스트](https://example.com "제목")

# 참조 링크
[텍스트][참조]
[참조]: https://example.com

# 자동 링크
<https://example.com>
<이메일@example.com>

# URL (링크화되지 않은 일반 텍스트)
https://example.com (변환 불필요)
```

### 4.2 필터링 알고리즘

**단계 1: 링크 감지 정규식**

```python
import re
from typing import List, Tuple

def find_inline_links(text: str) -> List[Tuple[int, int, str]]:
    """인라인 링크 감지

    패턴: [텍스트](URL)

    주의사항:
    1. 중첩된 대괄호 처리: [[inner]](url) → 오탐
    2. 이스케이프된 괄호: \[텍스트\](url) → 제외
    3. 링크 텍스트가 비어있는 경우: [](url) → 처리

    Args:
        text: 검사할 텍스트

    Returns:
        [(시작위치, 종료위치, 전체_링크), ...] 리스트
    """
    # 패턴 설명:
    # (?<!\\\)    - 역슬래시가 앞에 없음 (이스케이프 방지)
    # \[          - 열린 대괄호
    # ([^\[\]]+)  - 대괄호가 없는 텍스트 (링크 텍스트)
    # \]          - 닫힌 대괄호
    # \(          - 열린 괄호
    # ([^\)]+)    - 괄호가 없는 텍스트 (URL)
    # \)          - 닫힌 괄호

    pattern = r'(?<!\\)\[([^\[\]]*)\]\(([^\)]+)\)'
    matches = []

    for match in re.finditer(pattern, text):
        matches.append((
            match.start(),
            match.end(),
            match.group(0)  # 전체 매칭된 텍스트
        ))

    return matches

def find_reference_links(md_text: str) -> List[Tuple[str, str]]:
    """참조 링크 감지

    패턴:
    [참조]: URL
    [참조]: URL "제목"

    Args:
        md_text: 마크다운 전체 텍스트

    Returns:
        [(참조명, URL), ...] 튜플 리스트
    """
    # 패턴 설명:
    # ^           - 라인 시작
    # \[          - 열린 대괄호
    # ([^\]]+)    - 참조명
    # \]:         - 닫힌 대괄호 + 콜론
    # \s+         - 공백
    # ([^\s"]+)   - URL

    pattern = r'^\[([^\]]+)\]:\s+([^\s"]+)'
    references = []

    for line in md_text.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            references.append((match.group(1), match.group(2)))

    return references

def find_auto_links(text: str) -> List[Tuple[int, int, str]]:
    """자동 링크 감지

    패턴:
    <URL>
    <이메일@example.com>

    Args:
        text: 검사할 텍스트

    Returns:
        [(시작위치, 종료위치, 전체_링크), ...] 리스트
    """
    pattern = r'<([^>]+)>'
    matches = []

    for match in re.finditer(pattern, text):
        content = match.group(1)

        # URL 또는 이메일 형식인지 확인
        if (content.startswith('http://') or
            content.startswith('https://') or
            content.startswith('ftp://') or
            '@' in content):  # 이메일

            matches.append((
                match.start(),
                match.end(),
                match.group(0)
            ))

    return matches
```

**단계 2: 링크 행 필터링**

```python
def is_line_with_links(line: str) -> bool:
    """라인에 링크가 포함되어 있는지 판별

    Args:
        line: 검사할 마크다운 라인

    Returns:
        True if 링크 포함, False otherwise
    """
    # 인라인 링크 확인
    if find_inline_links(line):
        return True

    # 자동 링크 확인
    if find_auto_links(line):
        return True

    # 참조 링크 정의 확인 (라인 자체가 참조 정의)
    if re.match(r'^\[([^\]]+)\]:\s+([^\s"]+)', line.strip()):
        return True

    return False

def extract_link_lines(md_text: str) -> List[int]:
    """링크를 포함하는 모든 라인 번호 추출

    Args:
        md_text: 마크다운 전체 텍스트

    Returns:
        [라인번호, ...] 리스트
    """
    lines = md_text.split('\n')
    link_lines = []
    reference_defs = find_reference_links(md_text)

    for i, line in enumerate(lines):
        # 라인에 링크가 포함되면 필터링
        if is_line_with_links(line):
            link_lines.append(i)

    return link_lines

def should_filter_line(line_num: int, link_lines: List[int]) -> bool:
    """주어진 라인을 필터링해야 하는지 판별"""
    return line_num in link_lines
```

### 4.3 오탐(False Positive) 방지

**문제 케이스:**

```markdown
가격: (100원)
비용(세금 포함): 150원
함수명: get_user()
이스케이프: \[텍스트\](url)
```

위의 경우들은 링크가 아니지만, 대괄호와 괄호를 포함합니다.

**해결책:**

```python
def is_valid_link(match_text: str) -> bool:
    """링크의 유효성 확인

    Args:
        match_text: 정규식으로 매칭된 텍스트 (예: [텍스트](url))

    Returns:
        True if 유효한 링크, False otherwise
    """
    # 괄호 내용이 URL인지 확인
    match = re.match(r'\[([^\[\]]*)\]\(([^\)]+)\)', match_text)

    if not match:
        return False

    link_text = match.group(1)
    url = match.group(2)

    # URL이 공백이면 무효
    if not url.strip():
        return False

    # URL 형식 확인
    # - http://, https://, ftp://로 시작
    # - 또는 상대 경로 (/, ../, ./)
    # - 또는 앵커 (#)
    # - 또는 메일링 링크 (mailto:)

    valid_url_pattern = r'^(https?://|ftp://|/|\.\.?/|#|mailto:)'

    if not re.match(valid_url_pattern, url):
        # 상대 경로 또는 파일명 (확장자 포함)
        if not re.search(r'\.[a-zA-Z0-9]{1,5}$', url):
            # 경로 구분자가 없으면 무효 (단순 단어)
            if '/' not in url and '.' not in url:
                return False

    return True
```

### 4.4 테스트 케이스

```python
test_cases = [
    # 유효한 링크
    ("[Google](https://google.com)", True),
    ("[상대경로](./file.md)", True),
    ("[앵커](#section)", True),

    # 오탐: 링크 형식이지만 유효하지 않은 URL
    ("[텍스트]()", False),
    ("[텍스트](word)", False),

    # 오탐: 대괄호와 괄호이지만 링크가 아님
    ("가격: (100원)", False),
    ("함수명: get_user()", False),

    # 참조 링크
    ("[Google][ref]", True),  # [ref]: https://google.com 정의 있으면 True

    # 자동 링크
    ("<https://example.com>", True),
    ("<user@example.com>", True),
]

for text, expected in test_cases:
    has_link = is_line_with_links(text)
    assert has_link == expected, f"Failed: {text}"
```

---

## 5. 기타 필터링 (선택)

### 5.1 이미지 필터링

```python
def is_image_line(line: str) -> bool:
    """이미지 포함 라인 판별

    패턴: ![alt text](image.png)
    또는: ![alt text][ref]
    """
    # 이미지는 느낌표(!)로 시작하는 링크
    pattern = r'!\[([^\[\]]*)\]\(([^\)]+)\)'
    return bool(re.search(pattern, line))
```

### 5.2 체크박스 필터링

```python
def is_checkbox_line(line: str) -> bool:
    """체크박스 항목 판별

    패턴:
    - [ ] 미완료
    - [x] 완료
    """
    pattern = r'^\s*[-*]\s+\[[\sx]\]\s+'
    return bool(re.match(pattern, line))
```

### 5.3 HTML 태그 필터링

```python
def has_html_tags(line: str) -> bool:
    """HTML 태그 포함 여부 판별

    주의: 마크다운에서 허용되는 인라인 HTML
    """
    pattern = r'<(script|style|iframe|embed|object|[^!][^>]*javascript)[^>]*>'
    return bool(re.search(pattern, line, re.IGNORECASE))
```

---

## 6. 통합 필터링 함수

### 6.1 전체 필터링 플로우

```python
from dataclasses import dataclass

@dataclass
class FilterContext:
    """필터링 컨텍스트 - 한 번 계산한 결과를 캐시"""
    code_blocks: List[Tuple[int, int]]
    tables: List[Tuple[int, int]]
    link_lines: List[int]
    image_lines: List[int]
    html_lines: List[int]

def prepare_filter_context(md_text: str) -> FilterContext:
    """필터링을 위한 컨텍스트 준비

    성능 최적화: 각 필터링 요소를 미리 계산
    """
    lines = md_text.split('\n')

    return FilterContext(
        code_blocks=extract_code_blocks(md_text),
        tables=extract_tables(md_text),
        link_lines=[i for i, line in enumerate(lines) if is_line_with_links(line)],
        image_lines=[i for i, line in enumerate(lines) if is_image_line(line)],
        html_lines=[i for i, line in enumerate(lines) if has_html_tags(line)]
    )

def should_filter_element(element: 'MdElement', line_num: int, context: FilterContext) -> bool:
    """주어진 요소를 필터링해야 하는지 판별

    Args:
        element: 파싱된 마크다운 요소
        line_num: 요소가 위치한 라인 번호
        context: 필터링 컨텍스트

    Returns:
        True if 필터링 필요, False otherwise
    """
    # 코드 블록
    if is_in_code_block(line_num, context.code_blocks):
        return True

    # 테이블
    if is_in_table(line_num, context.tables):
        return True

    # 링크
    if line_num in context.link_lines:
        return True

    # 이미지
    if line_num in context.image_lines:
        return True

    # HTML 태그
    if line_num in context.html_lines:
        return True

    return False
```

### 6.2 파싱 함수 통합

```python
def parse_markdown_to_md_elements(md_content: str) -> List['MdElement']:
    """마크다운을 파싱하여 요소별로 분류

    사용자 피드백 적용:
    1. orderedList: ^\\d+\\. (들여쓰기 감지 안 함)
    2. 단락 처리: \\n\\n 기준으로 단락 그룹화
    3. 필터링: 상세 로직 적용
    """
    # 필터링 컨텍스트 준비
    filter_context = prepare_filter_context(md_content)

    # 단락 분할 (\\n\\n 기준)
    paragraphs = md_content.split('\n\n')

    elements = []
    line_num = 0

    for paragraph in paragraphs:
        lines = paragraph.split('\n')

        for line in lines:
            # 빈 줄 스킵
            if not line.strip():
                line_num += 1
                continue

            # 필터링 확인
            if should_filter_element(None, line_num, filter_context):
                line_num += 1
                continue

            # 요소 타입 판별 및 추가
            md_type = classify_markdown_line(line)

            if md_type != MdType.NO_CONVERT:
                element = MdElement(
                    type=md_type,
                    content=line.strip(),
                    line_num=line_num
                )
                elements.append(element)

            line_num += 1

    return elements
```

---

## 7. 성능 고려사항

### 7.1 정규식 컴파일 캐싱

```python
import re

# 모듈 레벨에서 정규식 컴파일 (한 번만 수행)
PATTERNS = {
    'code_block_start': re.compile(r'^\s*(`{3,}|~{3,})'),
    'table_separator': re.compile(r'^\s*\|[\s:|-]+\|'),
    'table_header': re.compile(r'^\s*\|.*\|'),
    'inline_link': re.compile(r'(?<!\\)\[([^\[\]]*)\]\(([^\)]+)\)'),
    'auto_link': re.compile(r'<([^>]+)>'),
    'image': re.compile(r'!\[([^\[\]]*)\]\(([^\)]+)\)'),
    'html_tag': re.compile(r'<(script|style|iframe)[^>]*>', re.IGNORECASE),
}

def find_inline_links_optimized(text: str) -> List[Tuple[int, int, str]]:
    """캐시된 정규식 사용"""
    matches = []
    for match in PATTERNS['inline_link'].finditer(text):
        matches.append((match.start(), match.end(), match.group(0)))
    return matches
```

### 7.2 한 번의 순회로 모든 필터 적용

**비효율적:**
```python
# 각 라인마다 여러 함수 호출
for line in lines:
    if is_in_code_block(line):
        continue
    if is_in_table(line):
        continue
    if is_line_with_links(line):
        continue
    # ...
```

**효율적:**
```python
# 사전 계산 + 한 번의 조회
context = prepare_filter_context(md_text)
for line_num, line in enumerate(lines):
    if should_filter_element(None, line_num, context):
        continue
```

---

## 8. 구현 체크리스트

### 8.1 코드 블록 필터링
- [ ] `is_code_block_start()` 함수 구현
- [ ] `extract_code_blocks()` 함수 구현
- [ ] `is_in_code_block()` 함수 구현
- [ ] 백틱과 틸드 모두 지원 확인
- [ ] 닫히지 않은 코드 블록 처리

### 8.2 테이블 필터링
- [ ] `is_table_separator()` 함수 구현
- [ ] `is_table_header()` 함수 구현
- [ ] `extract_tables()` 함수 구현
- [ ] `is_valid_table()` 유효성 검사
- [ ] 오탐(파이프만 있는 텍스트) 방지

### 8.3 링크 필터링
- [ ] `find_inline_links()` 함수 구현
- [ ] `find_reference_links()` 함수 구현
- [ ] `find_auto_links()` 함수 구현
- [ ] `is_valid_link()` 유효성 검사
- [ ] 이스케이프된 링크 처리
- [ ] 참조 링크 정의 라인 필터링

### 8.4 통합
- [ ] `FilterContext` 데이터클래스 정의
- [ ] `prepare_filter_context()` 함수 구현
- [ ] `should_filter_element()` 함수 구현
- [ ] 정규식 패턴 모듈 레벨 캐싱

### 8.5 테스트
- [ ] 각 필터링 요소별 단위 테스트
- [ ] 오탐 케이스 테스트
- [ ] 복합 케이스 테스트 (여러 필터 섞임)
- [ ] 성능 테스트 (대용량 마크다운)

---

## 9. 예시: 완전한 필터링 프로세스

### 9.1 입력 마크다운

```markdown
# 프로젝트 개요

이는 [GitHub](https://github.com) 기반 프로젝트입니다.

## 설치 방법

```bash
npm install
npm start
```

| 항목 | 설명 |
|------|------|
| 가격 | 100원 |

다음은 일반 텍스트입니다.
- 항목 1
- 항목 2
```

### 9.2 파싱 과정

1. **코드 블록 추출**: Line 8-10 (```bash ... ```)
2. **테이블 추출**: Line 12-14
3. **링크 추출**: Line 3
4. **일반 요소 처리**:
   - Line 1: TITLE ("# 프로젝트 개요")
   - Line 3: NORMAL_TEXT ("이는 ... 프로젝트입니다.") → 링크 포함이므로 필터링
   - Line 6: SECTION ("## 설치 방법")
   - Line 8-10: 필터링 (코드 블록)
   - Line 12-14: 필터링 (테이블)
   - Line 16: NORMAL_TEXT ("다음은...")
   - Line 17: UNORDERED_LIST_DEP1 ("- 항목 1")
   - Line 18: UNORDERED_LIST_DEP1 ("- 항목 2")

### 9.3 최종 결과

```python
[
    MdElement(type=TITLE, content="프로젝트 개요"),
    MdElement(type=SECTION, content="설치 방법"),
    MdElement(type=NORMAL_TEXT, content="다음은 일반 텍스트입니다."),
    MdElement(type=UNORDERED_LIST_DEP1, content="항목 1"),
    MdElement(type=UNORDERED_LIST_DEP1, content="항목 2"),
]
```

---

## 10. 참고 자료

- [GFM (GitHub Flavored Markdown) 스펙](https://github.github.com/gfm/)
- [CommonMark 스펙](https://spec.commonmark.org/)
- [Python re 모듈 문서](https://docs.python.org/3/library/re.html)
- 기존 `backend/app/utils/markdown_parser.py`의 `parse_markdown_to_content()` 함수

---

**작성 완료**: 2025-11-20
**다음 단계**: `parse_markdown_to_md_elements()` 함수 구현 시 본 보고서의 정규식과 알고리즘 참조
