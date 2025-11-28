"""
Markdown 빌더 유틸리티

Claude가 생성한 보고서 파싱 결과를 Markdown 문자열로 변환합니다.
"""
import logging
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
            section_type = section.type.value if hasattr(section.type, "value") else str(section.type)
            section_id = section.id
            content = section.content.strip() if section.content else ""

            logger.debug(
                f"[MARKDOWN] Processing section: type={section_type}, id={section_id}, order={section.order}"
            )

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
                # 제목은 placeholder_titles에서 조회하거나 기본값 사용
                section_title = _placeholder_titles.get(section_id, section_id)

                # max_length 검증 (절단하지 않고 경고만)
                if section.max_length and len(content) > section.max_length:
                    logger.warning(
                        f"[MARKDOWN] Section {section_id} exceeds max_length: "
                        f"{len(content)} > {section.max_length}, "
                        f"content will be preserved (not truncated)"
                    )

                parts.append(f"## {section_title}")
                parts.append(content)

        except Exception as e:
            logger.error(
                f"[MARKDOWN] Error processing section {section.id}: {str(e)}",
                exc_info=True
            )
            # 오류가 발생해도 계속 진행 (resilience)
            continue

    # 섹션들을 빈 줄로 구분하여 연결
    result = "\n\n".join(parts)

    logger.info(
        f"[MARKDOWN] Markdown built successfully - length={len(result)}, sections={len(sorted_sections)}"
    )
    return result
