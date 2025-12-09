/**
 * topic.ts
 *
 * 토픽(대화 스레드) 관련 TypeScript 타입 정의
 */

export type TopicStatus = 'active' | 'archived' | 'deleted'

export interface TopicUpdate {
    generated_title?: string
    status?: TopicStatus
}

export interface Topic {
    id: number
    input_prompt: string
    generated_title: string | null
    language: string
    status: TopicStatus
    template_id: number
    created_at: string
    updated_at: string
}

export interface TopicListResponse {
    topics: Topic[]
    total: number
    page: number
    page_size: number
}

// Ask API Request
export interface AskRequest {
  content: string;
  artifact_id?: number | null;
  include_artifact_content?: boolean;
  max_messages?: number | null;
  isWebSearch?: boolean;
}

// Ask API Response
export interface AskResponse {
    topic_id: number
    status: string // 'answering'
    message: string
    status_check_url: string
    stream_url: string
}

// Plan API Request
export interface PlanRequest {
    topic: string
    isTemplateUsed: boolean
    template_id: number | null
    isWebSearch: boolean
}

// Plan API Response
export interface Section {
    title: string
    description: string
}

export interface PlanResponse {
    topic_id: number
    plan: string
    sections: Section[]
}

// TopicGenerationStatus
export interface TopicGenerationStatus {
    topic_id: number
    status: 'generating' | 'completed' | 'failed'
    progress_percent: number
    current_step?: string
    artifact_id?: number
    started_at?: string
    completed_at?: string
    error_message?: string
}

// 보고서 생성 요청
export interface ReportGenerationRequest {
    topic: string
    plan: string
    isEdit: boolean
    isWebSearch: boolean
}

// 보고서 생성 응답
export interface ReportGenerationResponse {
    topic_id: number
    status: string
    message: string
    status_check_url: string
}

