"""
Markdown 빌더 유틸리티

Claude가 생성한 보고서 파싱 결과를 Markdown 문자열로 변환합니다.
"""
from datetime import datetime
from typing import Dict


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
