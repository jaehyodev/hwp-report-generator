import React, {useState} from 'react'
import {Card, Button, Input, Form, Space, Typography, Divider} from 'antd'
import {SaveOutlined, ReloadOutlined} from '@ant-design/icons'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import styles from './PromptManagement.module.css'

const {TextArea} = Input
const {Title, Text} = Typography

interface PromptFormData {
    systemPrompt: string
    reportStructurePrompt: string
    titleGenerationPrompt: string
}

const PromptManagement: React.FC = () => {
    const {antdMessage} = useMessage()
    const [form] = Form.useForm<PromptFormData>()
    const [isLoading, setIsLoading] = useState(false)
    const [isSaving, setIsSaving] = useState(false)

    // 기본 프롬프트 템플릿 (예시)
    const defaultPrompts: PromptFormData = {
        systemPrompt: `당신은 전문적인 비즈니스 보고서 작성 전문가입니다.
사용자가 요청한 주제에 대해 명확하고 논리적인 구조를 가진 보고서를 작성합니다.
보고서는 한국어로 작성되며, 비즈니스 환경에 적합한 공식적인 문체를 사용합니다.`,

        reportStructurePrompt: `다음 주제에 대한 보고서를 작성해주세요: {topic}

보고서는 다음 구조를 따라야 합니다:

1. 제목 (TITLE): 보고서의 핵심 주제를 나타내는 명확한 제목
2. 요약 (SUMMARY): 보고서의 핵심 내용을 3-5문장으로 요약
3. 배경 및 목적 (BACKGROUND): 보고서 작성 배경과 목적 설명
4. 주요 내용 (MAIN_CONTENT): 상세한 분석 및 내용
5. 결론 및 제언 (CONCLUSION): 결론과 향후 제언

각 섹션은 구체적이고 실용적인 내용으로 작성해주세요.`,

        titleGenerationPrompt: `다음 보고서 내용을 바탕으로 적절한 제목을 생성해주세요:

{content}

제목은 다음 조건을 만족해야 합니다:
- 20자 이내의 간결한 표현
- 보고서의 핵심 주제를 명확히 전달
- 공식적이고 전문적인 표현
- 연도 정보 포함 (현재 연도)

제목만 출력해주세요.`
    }

    // 초기 데이터 로드
    React.useEffect(() => {
        loadPrompts()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const loadPrompts = async () => {
        setIsLoading(true)
        try {
            // TODO: API 호출로 실제 프롬프트 데이터 로드
            // const response = await promptService.getPrompts();
            // form.setFieldsValue(response.data);

            // 임시로 기본값 설정
            form.setFieldsValue(defaultPrompts)
        } catch (error: any) {
            antdMessage.error(TOAST_MESSAGES.PROMPT_LOAD_FAILED)
            console.error('Failed to load prompts:', error)
            // 실패 시에도 기본값 표시
            form.setFieldsValue(defaultPrompts)
        } finally {
            setIsLoading(false)
        }
    }

    const handleSave = async (values: PromptFormData) => {
        setIsSaving(true)
        try {
            // TODO: API 호출로 프롬프트 저장
            // await promptService.updatePrompts(values);

            console.log('Saving prompts:', values)

            // 임시 딜레이 (API 호출 시뮬레이션)
            await new Promise((resolve) => setTimeout(resolve, 1000))

            antdMessage.success(TOAST_MESSAGES.PROMPT_SAVE_SUCCESS)
        } catch (error: any) {
            antdMessage.error(TOAST_MESSAGES.PROMPT_SAVE_FAILED)
            console.error('Failed to save prompts:', error)
        } finally {
            setIsSaving(false)
        }
    }

    const handleReset = () => {
        form.setFieldsValue(defaultPrompts)
        antdMessage.info(TOAST_MESSAGES.PROMPT_RESET)
    }

    return (
        <div className={styles.promptManagement}>
            <Card
                title={
                    <Space>
                        <Title level={4} style={{margin: 0}}>
                            프롬프트 관리
                        </Title>
                    </Space>
                }
                bordered={false}
                extra={
                    <Space>
                        <Button icon={<ReloadOutlined />} onClick={handleReset}>
                            기본값으로 초기화
                        </Button>
                        <Button type="primary" icon={<SaveOutlined />} onClick={() => form.submit()} loading={isSaving}>
                            저장
                        </Button>
                    </Space>
                }>
                <Form form={form} layout="vertical" onFinish={handleSave} disabled={isLoading}>
                    <Form.Item
                        label={
                            <Space direction="vertical" size={0}>
                                <Text strong>시스템 프롬프트</Text>
                                <Text type="secondary" style={{fontSize: '0.875rem'}}>
                                    AI의 기본 역할과 행동 방식을 정의합니다.
                                </Text>
                            </Space>
                        }
                        name="systemPrompt"
                        rules={[
                            {required: true, message: '시스템 프롬프트를 입력해주세요.'},
                            {min: 10, message: '최소 10자 이상 입력해주세요.'}
                        ]}>
                        <TextArea rows={6} placeholder="시스템 프롬프트를 입력하세요..." showCount maxLength={2000} />
                    </Form.Item>

                    <Divider />

                    <Form.Item
                        label={
                            <Space direction="vertical" size={0}>
                                <Text strong>보고서 구조 프롬프트</Text>
                                <Text type="secondary" style={{fontSize: '0.875rem'}}>
                                    보고서의 전체 구조와 각 섹션의 내용을 정의합니다. {'{topic}'}을 사용하여 주제를 삽입할 수 있습니다.
                                </Text>
                            </Space>
                        }
                        name="reportStructurePrompt"
                        rules={[
                            {required: true, message: '보고서 구조 프롬프트를 입력해주세요.'},
                            {min: 50, message: '최소 50자 이상 입력해주세요.'}
                        ]}>
                        <TextArea rows={12} placeholder="보고서 구조 프롬프트를 입력하세요..." showCount maxLength={4000} />
                    </Form.Item>

                    <Divider />

                    <Form.Item
                        label={
                            <Space direction="vertical" size={0}>
                                <Text strong>제목 생성 프롬프트</Text>
                                <Text type="secondary" style={{fontSize: '0.875rem'}}>
                                    보고서 제목을 생성하는 방식을 정의합니다. {'{content}'}를 사용하여 보고서 내용을 삽입할 수 있습니다.
                                </Text>
                            </Space>
                        }
                        name="titleGenerationPrompt"
                        rules={[
                            {required: true, message: '제목 생성 프롬프트를 입력해주세요.'},
                            {min: 20, message: '최소 20자 이상 입력해주세요.'}
                        ]}>
                        <TextArea rows={8} placeholder="제목 생성 프롬프트를 입력하세요..." showCount maxLength={2000} />
                    </Form.Item>
                </Form>

                <div className={styles.infoSection}>
                    <Text type="secondary">
                        <strong>💡 팁:</strong> 프롬프트를 수정한 후에는 반드시 저장 버튼을 눌러야 변경사항이 적용됩니다. 변수 사용 시 중괄호를
                        사용하세요. 예: {'{topic}'}, {'{content}'}
                    </Text>
                </div>
            </Card>
        </div>
    )
}

export default PromptManagement
