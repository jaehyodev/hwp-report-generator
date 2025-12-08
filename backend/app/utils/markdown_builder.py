"""
Markdown 빌더 유틸리티

Claude가 생성한 보고서 파싱 결과를 Markdown 문자열로 변환합니다.
"""
import logging
import re
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


#TODO: 기능필요 여부 확인필요. llm 에서 받아온 값을 md 파일에 저장할 때 재대로 저장이 안되는 문제있음.
def build_report_md(parsed: Dict[str, str]) -> str:
    """Claude 생성 결과(dict)를 Markdown 문서로 변환.

    필요한 키:
      - title, title_summary, summary,
        title_background, background,
        title_main_content, main_content,
        title_conclusion, conclusion
    """
    title = parsed.get("title", "보고서")
    t_sum = parsed.get("title_summary", "요약")
    sumv = parsed.get("summary", "")
    t_bg = parsed.get("title_background", "배경 및 목적")
    bg = parsed.get("background", "")
    t_main = parsed.get("title_main_content", "주요 내용")
    main = parsed.get("main_content", "")
    t_con = parsed.get("title_conclusion", "결론 및 제언")
    con = parsed.get("conclusion", "")

    generated_at = parsed.get("generated_at")
    if not generated_at:
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    parts = [
        f"# {title}",
        f"_생성일: {generated_at}_\n",
        f"## {t_sum}",
        sumv.strip(),
        f"\n## {t_bg}",
        bg.strip(),
        f"\n## {t_main}",
        main.strip(),
        f"\n## {t_con}",
        con.strip(),
        "",
    ]
    return "\n\n".join(parts)


def build_report_md_from_json(
    structured_response: "StructuredReportResponse",
    placeholder_titles: Optional[Dict[str, str]] = None,
) -> str:
    """JSON 구조화 응답을 마크다운으로 변환.

    StructuredReportResponse를 받아서 마크다운 문자열로 변환합니다.
    섹션 순서는 order 필드로 정렬되며, 각 섹션 타입에 따라 다른 마크다운
    형식을 적용합니다.

    Args:
        structured_response: StructuredReportResponse 객체
        placeholder_titles: Placeholder 키를 한글 제목으로 매핑하는 딕셔너리
                          (예: {"MARKET_ANALYSIS": "시장 분석"})

    Returns:
        완성된 마크다운 문자열

    Process:
        1. sections을 order로 정렬
        2. 각 섹션을 마크다운으로 변환:
           - TITLE: H1 제목 (#)
           - DATE: 수평선 + "생성일: yyyy.mm.dd" + 수평선
           - 다른 섹션: H2 제목 (##) + 내용
        3. 섹션들을 연결하여 최종 마크다운 반환

    Example:
        >>> from app.models.report_section import StructuredReportResponse, SectionMetadata, SectionType
        >>> sections = [
        ...     SectionMetadata(
        ...         id="TITLE",
        ...         type=SectionType.TITLE,
        ...         content="2025년 디지털금융 동향",
        ...         order=1,
        ...         source_type=SourceType.BASIC
        ...     ),
        ...     SectionMetadata(
        ...         id="DATE",
        ...         type=SectionType.DATE,
        ...         content="2025.11.28",
        ...         order=2,
        ...         source_type=SourceType.SYSTEM
        ...     )
        ... ]
        >>> response = StructuredReportResponse(sections=sections)
        >>> md = build_report_md_from_json(response)
        >>> "# 2025년 디지털금융 동향" in md
        True
        >>> "생성일: 2025.11.28" in md
        True
    """
    if not structured_response or not structured_response.sections:
        logger.warning("[MARKDOWN] Empty structured response")
        return ""

    # 섹션을 order로 정렬
    sorted_sections = sorted(
        structured_response.sections, key=lambda s: s.order
    )

    logger.info(
        f"[MARKDOWN] Building markdown from {len(sorted_sections)} sections"
    )

    parts: List[str] = []

    # 기본 placeholder 제목 매핑 (한글)
    _placeholder_titles = {
        "TITLE": "제목",
        "BACKGROUND": "배경 및 목적",
        "MAIN_CONTENT": "주요 내용",
        "SUMMARY": "요약",
        "CONCLUSION": "결론 및 제언",
        "MARKET_ANALYSIS": "시장 분석",
        "FINANCIAL_ANALYSIS": "재무 분석",
        "RISK_ASSESSMENT": "위험 평가",
        "RECOMMENDATIONS": "제언",
    }

    # 사용자 정의 제목 매핑 병합
    if placeholder_titles:
        _placeholder_titles.update(placeholder_titles)

    for section in sorted_sections:
        try:
            section_type = (
                section.type.value if hasattr(section.type, "value") else str(section.type)
            )
            section_id = section.id
            content = section.content.strip() if section.content else ""
            source_type_val = (
                section.source_type.value
                if hasattr(section.source_type, "value")
                else str(section.source_type)
            )
            placeholder_key = section.placeholder_key

            logger.debug(
                f"[MARKDOWN] Processing section: type={section_type}, id={section_id}, "
                f"source_type={source_type_val}, placeholder_key={placeholder_key}, order={section.order}"
            )

            # source_type이 basic 또는 system인 경우 (TEMPLATE 제외)
            if source_type_val in ["basic", "system"]:
                if section_type == "TITLE":
                    # TITLE: H1 제목
                    parts.append(f"# {content}")

                elif section_type == "DATE":
                    # DATE: 수평선 + "생성일: yyyy.mm.dd" + 수평선
                    parts.append("---")
                    parts.append(f"생성일: {content}")
                    parts.append("---")

                else:
                    # 다른 섹션: H2 제목 + 내용
                    section_title = _placeholder_titles.get(section_id, section_id)

                    if section.max_length and len(content) > section.max_length:
                        logger.warning(
                            f"[MARKDOWN] Section {section_id} exceeds max_length: "
                            f"{len(content)} > {section.max_length}, "
                            f"content will be preserved (not truncated)"
                        )

                    parts.append(f"## {section_title}")
                    parts.append(content)

            # source_type이 template인 경우
            elif source_type_val == "template":
                if section_type == "TITLE" and placeholder_key == "{{TITLE}}":
                    # TITLE: H1 제목
                    parts.append(f"# {content}")

                elif section_type == "DATE" and placeholder_key == "{{DATE}}":
                    # DATE: 수평선 + "생성일: yyyy.mm.dd" + 수평선
                    parts.append("---")
                    parts.append(f"생성일: {content}")
                    parts.append("---")

                elif section_type == "TITLE" and placeholder_key != "{{TITLE}}":
                    # 일반 섹션: H2 제목 
                    parts.append(f"## {content}")
                else:
                    # 본문 생성 
                    if content:
                        parts.append(postprocess_headings(content))

            else:
                # 예상치 못한 source_type
                logger.warning(
                    f"[MARKDOWN] Unknown source_type: {source_type_val}, id={section_id}"
                )
                if content:
                    parts.append(content)

        except Exception as e:
            logger.error(
                f"[MARKDOWN] Error processing section {section.id}: {str(e)}",
                exc_info=True
            )
            continue

    # 섹션들을 빈 줄로 구분하여 연결
    result = "\n\n".join(parts)

    logger.info(
        f"[MARKDOWN] Markdown built successfully - length={len(result)}, sections={len(sorted_sections)}"
    )
    return result


def postprocess_headings(text: str) -> str:
    """H2 마크다운을 순서 리스트로 변환.

    Claude API의 Markdown 기반 응답 경로에서 H2(`##`) 마크다운 헤딩을
    순서 있는 리스트(`n. 제목`) 형식으로 자동 변환하는 전처리 함수.

    Args:
        text: 원본 Markdown 문자열 (H2 헤딩 포함 가능)

    Returns:
        H2를 순서 리스트로 변환한 문자열

    처리 규칙:
        1. 정규식으로 모든 H2 라인 탐색: ^##\\s*(\\d+\\.?)?\\s*(.+)$
        2. 각 H2에 대해:
           a. 숫자 있음 → 숫자 추출, max_num 업데이트
           b. 숫자 없음 → next_num = max(max_num, 0) + 1 할당
           c. '##' 제거, 'n. 제목' 형식으로 변환
        3. 본문/불릿/기타는 그대로 유지
        4. 변환된 텍스트 반환

    예:
        "## 배경\\n내용\\n##내용" → "1. 배경\\n내용\\n2. 내용"
    """
    if not text:
        logger.info("[POSTPROCESS] Empty input text")
        return text

    try:
        lines = text.split("\n")
        result_lines = []
        max_num = 0
        has_h2 = False

        # H2 패턴: 라인 시작 + ## (뒤에 #이 없음) + 선택적 공백 + 선택적 숫자 + 선택적 마침표 + 선택적 공백 + 제목
        # negative lookahead (?!#)를 사용하여 ###+ (H3 이상)는 제외
        h2_pattern = r'^##(?!#)\s*(\d+\.?)?\s*(.+)$'

        for line in lines:
            match = re.match(h2_pattern, line)

            if match:
                has_h2 = True
                number_part = match.group(1)  # '1', '1.', '2', 등
                title = match.group(2).strip()  # 제목 부분

                if not title:
                    logger.debug("[POSTPROCESS] Empty H2 heading detected")

                # 숫자가 있는 경우
                if number_part:
                    try:
                        # '1.', '2.' 형태에서 숫자만 추출
                        num = int(number_part.rstrip('.'))
                        # 중복 번호 처리: 같은 번호가 반복되면 자동 증가
                        if num <= max_num:
                            max_num += 1
                            result_lines.append(f"{max_num}. {title}")
                            logger.debug(f"[POSTPROCESS] Converted H2 with duplicate number (adjusted): {max_num}. {title}")
                        else:
                            max_num = num
                            result_lines.append(f"{num}. {title}")
                            logger.debug(f"[POSTPROCESS] Converted H2 with number: {num}. {title}")
                    except (ValueError, AttributeError) as e:
                        # 숫자 파싱 실패 시 자동 번호 부여
                        logger.warning(f"[POSTPROCESS] Failed to parse number from H2 '{line}', using auto-numbering: {str(e)}")
                        max_num += 1
                        result_lines.append(f"{max_num}. {title}")
                else:
                    # 숫자가 없는 경우 자동 순번 부여
                    max_num += 1
                    result_lines.append(f"{max_num}. {title}")
                    logger.debug(f"[POSTPROCESS] Converted H2 without number: {max_num}. {title}")
            else:
                # H2가 아닌 라인은 그대로 유지
                result_lines.append(line)

        if not has_h2:
            logger.info("[POSTPROCESS] No H2 headings found, returning original text")
            return text

        result = "\n".join(result_lines)
        logger.info(f"[POSTPROCESS] H2 conversion complete: {max_num} headings processed")
        return result

    except Exception as e:
        logger.error(f"[POSTPROCESS] Error in postprocess_headings: {str(e)}", exc_info=True)
        # 에러 발생 시 원본 텍스트 반환
        return text
