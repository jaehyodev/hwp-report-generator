import {useState, useEffect} from 'react'
import {Input, Card, Button, Empty, Spin, Row, Col} from 'antd'
import {FileTextOutlined, CheckCircleFilled} from '@ant-design/icons'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import {templateApi} from '../../services/templateApi'
import type {TemplateListItem} from '../../types/template'
import {formatDate} from '../../utils/formatters'
import {useTopicStore} from '../../stores/useTopicStore'
import styles from './TemplateSelectionView.module.css'

const {Search} = Input

interface TemplateSelectionViewProps {
    onStartChat: (templateId: number) => void
}

/**
 * TemplateSelectionView
 *
 * ⭐ 보고서 생성 전 템플릿 선택 화면
 *
 * 기능:
 * 1. 템플릿 목록을 카드 형식으로 표시
 * 2. 템플릿 제목으로 검색
 * 3. 템플릿 선택 (단일 선택)
 * 4. "보고서 생성 시작하기" 버튼으로 대화 시작
 */
const TemplateSelectionView = ({onStartChat}: TemplateSelectionViewProps) => {
    const {antdMessage} = useMessage()
    const [templates, setTemplates] = useState<TemplateListItem[]>([])
    const [filteredTemplates, setFilteredTemplates] = useState<TemplateListItem[]>([])
    const [loading, setLoading] = useState(false)
    const [searchText, setSearchText] = useState('')
    const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)

    // 템플릿 목록 로드
    const loadTemplates = async () => {
        setLoading(true)
        try {
            const data = await templateApi.listTemplates()
            setTemplates(data)
            setFilteredTemplates(data)

            // 템플릿이 1개만 있으면 자동 선택
            if (data.length === 1) {
                setSelectedTemplateId(data[0].id)
            }
        } catch (error: any) {
            antdMessage.error(error.message || TOAST_MESSAGES.TEMPLATE_LOAD_FAILED)
        } finally {
            setLoading(false)
        }
    }

    // 초기 로드
    useEffect(() => {
        loadTemplates()
    }, [])

    // 검색 처리
    const handleSearch = (value: string) => {
        setSearchText(value)
        const filtered = templates.filter((template) => template.title.toLowerCase().includes(value.toLowerCase()))
        setFilteredTemplates(filtered)
    }

    const handleTemplateClick = (templateId: number) => {
        setSelectedTemplateId(selectedTemplateId === templateId ? null : templateId)
    }

    // 보고서 생성 시작
    const handleStartChat = () => {
        if (!selectedTemplateId) {
            antdMessage.warning(TOAST_MESSAGES.TEMPLATE_SELECT_REQUIRED)
            return
        }

        // 선택된 템플릿 찾기
        const selectedTemplate = templates.find(t => t.id === selectedTemplateId)
        if (selectedTemplate) {
            // Template 타입으로 변환 (TemplateListItem에서 Template으로)
            const templateForStore = {
                ...selectedTemplate,
                user_id: 0, // 실제 값은 서버에서 관리
                description: '',
                file_path: '',
                sha256: '',
                is_active: true,
                updated_at: selectedTemplate.created_at
            }
            // store에 템플릿 정보 저장
            useTopicStore.getState().setSelectedTemplate(templateForStore)
            // store에 템플릿 사용으로 저장
            useTopicStore.getState().setIsTemplateSelected(true)
        }

        onStartChat(selectedTemplateId)
    }

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <h1 className={styles.title}>보고서 템플릿 선택</h1>
                <p className={styles.subtitle}>보고서 생성에 사용할 템플릿을 선택하세요</p>
            </div>

            <div className={styles.searchSection}>
                <Search
                    placeholder="템플릿 제목 검색..."
                    allowClear
                    size="large"
                    onChange={(e) => handleSearch(e.target.value)}
                    onSearch={handleSearch}
                    value={searchText}
                    className={styles.searchInput}
                />
            </div>

            {loading ? (
                <div className={styles.loadingContainer}>
                    <Spin size="large"/>
                </div>
            ) : filteredTemplates.length === 0 ? (
                <Empty description={searchText ? '검색 결과가 없습니다.' : '등록된 템플릿이 없습니다.'} className={styles.empty} />
            ) : (
                <>
                    <Row gutter={[16, 16]} className={styles.cardGrid}>
                        {filteredTemplates.map((template) => {
                            const isSelected = selectedTemplateId === template.id

                            return (
                                <Col xs={24} sm={12} md={8} lg={6} key={template.id}>
                                    <Card
                                        hoverable
                                        className={`${styles.templateCard} ${isSelected ? styles.selected : ''}`}
                                        onClick={() => handleTemplateClick(template.id)}>
                                        {isSelected && (
                                            <div className={styles.selectedBadge}>
                                                <CheckCircleFilled className={styles.checkIcon} />
                                            </div>
                                        )}

                                        <div className={styles.cardContent}>
                                            <FileTextOutlined className={styles.fileIcon} />
                                            <h3 className={styles.templateTitle}>{template.title}</h3>
                                            <p className={styles.templateFilename}>{template.filename}</p>
                                            <p className={styles.templateDate}>{formatDate(new Date(template.created_at).getTime() / 1000)}</p>
                                        </div>
                                    </Card>
                                </Col>
                            )
                        })}
                    </Row>

                    <div className={styles.actionSection}>
                        <Button type="primary" size="large" onClick={handleStartChat} disabled={!selectedTemplateId} className={styles.startButton}>
                            보고서 생성 시작하기
                        </Button>
                    </div>
                </>
            )}
        </div>
    )
}

export default TemplateSelectionView
