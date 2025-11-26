/**
 * 바이트 크기를 사람이 읽기 쉬운 형식으로 변환합니다.
 *
 * @param bytes - 변환할 바이트 크기 (음수가 아닌 정수)
 * @returns 포맷된 파일 크기 문자열 (소수점 둘째 자리까지)
 *
 * @example
 * formatFileSize(0)          // '0 Bytes'
 * formatFileSize(1024)       // '1 KB'
 * formatFileSize(1536)       // '1.5 KB'
 * formatFileSize(1048576)    // '1 MB'
 * formatFileSize(5242880)    // '5 MB'
 * formatFileSize(1073741824) // '1 GB'
 */
export const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Unix 타임스탬프를 한국어 형식의 날짜/시간 문자열로 변환합니다.
 *
 * @param timestamp - Unix 타임스탬프 (초 단위)
 * @returns 한국어 로케일 형식의 날짜/시간 문자열 (YYYY. MM. DD. HH:MM)
 *
 * @example
 * formatDate(1609459200)      // '2021. 01. 01. 오전 09:00' (KST 기준)
 * formatDate(1735689600)      // '2025. 01. 01. 오전 12:00' (KST 기준)
 * formatDate(1704067200)      // '2024. 01. 01. 오전 09:00' (KST 기준)
 *
 * @remarks
 * - 입력은 Unix 타임스탬프 (초 단위)이며, 밀리초로 변환하여 Date 객체 생성
 * - 출력 형식은 한국 표준시(KST) 기준
 * - 시간은 24시간 형식이 아닌 오전/오후 형식으로 표시됨
 */
export const formatDate = (timestamp: number): string => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    })
}

/**
 * ISO 8601 문자열을 Date 객체로 변환합니다.
 * @param isoString 백엔드에서 받은 날짜/시간 문자열 (ISO 8601)
 * @returns 유효한 Date 객체 또는 null
 */
export const isoStringToDate = (isoString: string | null): Date | null => {
    if (!isoString) {
        return null;
    }
    // JavaScript의 Date 생성자는 ISO 8601 문자열을 자동으로 파싱합니다.
    const date = new Date(isoString);
    
    // Date 객체가 유효한지 확인합니다.
    if (isNaN(date.getTime())) {
        console.error("isoStringToDate >> invalid isoString >> ", isoString);
        return null;
    }
    
    return date;
};

/**
 * Date 객체를 한국 표준시(KST) 기반의 문자열로 포맷합니다.
 * @param date 포맷할 Date 객체
 * @returns 'YYYY. MM. DD. HH:MM' 형식의 문자열
 */
export const formatDateToString = (date: Date | null): string => {
    // 1. 날짜가 없는 경우
    if (date === null) {
        return '-';
    }

    // 2. Date 객체이지만 유효하지 않은 경우 (NaN)
    if (isNaN(date.getTime())) {
        // 비정상적인 데이터이므로 오류를 기록합니다.
        console.error("formatDateToString >> invalid date >> ", date);
        return 'N/A';
    }

    // 3. toLocaleString 메서드를 사용하여 포맷팅합니다.
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit', // 월을 01, 02 형식으로 표시
        day: '2-digit',   // 일을 01, 02 형식으로 표시
        hour: '2-digit',  // 시간을 01, 02 형식으로 표시
        minute: '2-digit',// 분을 01, 02 형식으로 표시
        hour12: true      // 24시간제 미사용 (오전/오후 표시)
    });
};