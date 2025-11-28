import {artifactApi} from '../services/artifactApi'
import type {Artifact} from '../types/artifact'
import type {MessageModel} from '@/types/domain/MessageModel'

/**
 * messageHelpers.ts
 *
 * 메시지 관련 유틸리티 함수
 * - 메시지와 아티팩트 연결
 */

/**
 * 단일 메시지에 관련 아티팩트를 연결하고, MD 아티팩트의 content를 로드합니다.
 *
 * Assistant 메시지에 연결된 아티팩트를 필터링하고,
 * MD 아티팩트가 있을 경우 API로 content를 로드하여 Artifact 객체에 추가합니다.
 *
 * @param message - 아티팩트를 연결할 메시지 객체
 * @param artifacts - 검색 대상 아티팩트 배열
 * @returns 아티팩트가 연결된 메시지 객체 (Promise)
 *
 * @example
 * const message: MessageModel = {
 *   id: 10,
 *   topicId: 1,
 *   role: 'assistant',
 *   content: '보고서를 생성했습니다.',
 *   seqNo: 2,
 *   createdAt: '2025-01-15T10:30:00Z'
 * }
 * const artifacts: Artifact[] = [
 *   { id: 5, kind: 'md', message_id: 10, filename: 'report.md', ... }
 * ]
 * const enriched = await enrichMessageWithArtifact(message, artifacts)
 * // enriched.artifacts[0].content = '# 보고서 내용...'
 *
 * @remarks
 * - Assistant 메시지만 처리 (User 메시지는 무시)
 * - MD 아티팩트의 content를 API로 로드하여 Artifact.content에 저장
 * - API 호출 실패 시 content 없이 artifacts 연결 (에러 로깅)
 */
export const enrichMessageWithArtifact = async (message: MessageModel, artifacts: Artifact[]): Promise<MessageModel> => {
    if (message.role === 'assistant') {
        // 이 메시지에 연결된 artifacts 필터링
        const messageArtifacts = artifacts.filter((art) => art.message_id === message.id)
        console.log('messageArtifacts:', messageArtifacts)
        // MD artifact 찾아서 content 로드
        const mdArtifact = messageArtifacts.find((art) => art.kind === 'md')

        if (mdArtifact) {
            try {
                // API로 artifact content 가져오기
                const contentResponse = await artifactApi.getArtifactContent(mdArtifact.id)

                // Artifact 객체에 content 추가
                mdArtifact.content = contentResponse.content
            } catch (error) {
                console.error('Failed to load artifact content:', error)
                // 실패 시 content 없이 진행
            }
        }

        return {
            ...message,
            artifacts: messageArtifacts // content 포함된 artifacts
        }
    }

    return message
}

/**
 * 여러 메시지에 아티팩트 내용을 일괄 연결합니다.
 *
 * 메시지 배열의 각 항목에 대해 `enrichMessageWithArtifact`를 병렬로 실행하여
 * 모든 관련 아티팩트 내용을 동시에 로드합니다.
 *
 * @param messages - 아티팩트를 연결할 메시지 배열
 * @param artifacts - 검색 대상 아티팩트 배열
 * @returns 아티팩트 내용이 포함된 메시지 배열 (Promise)
 *
 * @example
 * const messages: MessageModel[] = [
 *   { id: 10, topicId: 1, role: 'user', content: '요청', seqNo: 1, createdAt: '...' },
 *   { id: 11, topicId: 1, role: 'assistant', content: '응답', seqNo: 2, createdAt: '...' }
 * ]
 * const artifacts: Artifact[] = [
 *   { id: 5, kind: 'md', message_id: 11, filename: 'report.md', ... }
 * ]
 * const enrichedMessages = await enrichMessagesWithArtifacts(messages, artifacts)
 * // enrichedMessages[0]: 아티팩트 없음 (user 메시지)
 * // enrichedMessages[1]: reportData 포함 (assistant 메시지 + 아티팩트)
 *
 * @remarks
 * - 내부적으로 `Promise.all`을 사용하여 병렬 처리
 * - 각 메시지는 독립적으로 처리되며, 일부 실패해도 나머지는 정상 처리됨
 * - 빈 배열을 전달하면 빈 배열 반환
 */
export const enrichMessagesWithArtifacts = async (messages: MessageModel[], artifacts: Artifact[]): Promise<MessageModel[]> => {
    return Promise.all(messages.map((message) => enrichMessageWithArtifact(message, artifacts)))
}
