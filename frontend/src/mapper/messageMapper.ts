import type {MessageResponse} from '@/types/api/MessageApi'
import type {MessageModel} from '@/types/domain/MessageModel'
import type {MessageUI} from '@/types/ui/MessageUI'

/**
 * messageMapper.ts
 *
 * 메시지 관련 매핑 함수 (순수 데이터 변환만 담당)
 * - Response → Model: API 응답을 도메인 모델로 변환
 * - Model → UI: 도메인 모델을 UI 표시용으로 변환
 *
 * 📌 책임 분리:
 * - Mapper: 데이터 구조 변환만 담당 (동기)
 * - Helper (messageHelpers.ts): API 호출 및 비즈니스 로직 담당 (비동기)
 */

/**
 * API 응답(MessageResponse)을 도메인 모델(MessageModel)로 변환
 *
 * 📌 artifacts와 reportData는 별도 API 호출 후 enrichMessageWithArtifact()로 추가
 */
export const mapMessageResponseToModel = (response: MessageResponse): MessageModel => {
    return {
        id: response.id,
        topicId: response.topic_id,
        role: response.role,
        content: response.content,
        seqNo: response.seq_no,
        createdAt: response.created_at
    }
}

/**
 * 여러 API 응답을 도메인 모델 배열로 변환
 */
export const mapMessageResponsesToModels = (responses: MessageResponse[]): MessageModel[] => {
    return responses.map(mapMessageResponseToModel)
}

/**
 * 도메인 모델(MessageModel)을 UI 모델(MessageUI)로 변환
 * ✅ 순수 매퍼: API 호출 없이 데이터 구조만 변환
 *
 * @param model - 변환할 MessageModel
 * @param clientId - UI 렌더링용 고유 ID
 *
 * @remarks
 * - artifacts에서 content가 있는 MD artifact를 찾아 reportData 생성
 * - reportData는 UI 레이어에서만 사용하는 편의 필드
 * - clientId는 React key로 사용되어 메시지 순서 변경 시에도 안정적인 렌더링 보장
 */
export const mapMessageModelToUI = (model: MessageModel, clientId: number): MessageUI => {
    // artifacts에서 content가 로드된 MD artifact 찾기
    const mdArtifact = model.artifacts?.find((art) => art.kind === 'md' && art.content)

    return {
        ...model,
        clientId,
        timestamp: new Date(model.createdAt),
        isOutline: false, // 기본값
        reportData: mdArtifact && mdArtifact.content
            ? {
                  reportId: mdArtifact.id,
                  filename: mdArtifact.filename,
                  content: mdArtifact.content as string // find 조건에서 이미 content 존재 확인
              }
            : undefined
    }
}

/**
 * 여러 도메인 모델을 UI 모델 배열로 변환
 * - clientId를 순차적으로 할당 (0, 1, 2, ...)
 */
export const mapMessageModelsToUI = (models: MessageModel[]): MessageUI[] => {
    return models.map((model, index) => mapMessageModelToUI(model, index))
}
