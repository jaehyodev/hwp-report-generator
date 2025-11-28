import React, {useState, useEffect} from 'react'
import {Modal, Input} from 'antd'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import {useTopicStore} from '../../stores/useTopicStore'
import type {Topic} from '../../types/topic'
import styles from './TopicEditModal.module.css'

interface TopicEditModalProps {
    topic: Topic | null
    isOpen: boolean
    onClose: () => void
    onSuccess?: () => void
}

const TopicEditModal: React.FC<TopicEditModalProps> = ({topic, isOpen, onClose, onSuccess}) => {
    const {antdMessage} = useMessage()
    const [editTitle, setEditTitle] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const {updateTopicById} = useTopicStore()

    // topic이 변경될 때마다 editTitle 업데이트
    useEffect(() => {
        if (topic) {
            setEditTitle(topic.generated_title || topic.input_prompt)
        }
    }, [topic])

    const handleSave = async () => {
        if (!topic) return

        const trimmedTitle = editTitle.trim()
        if (!trimmedTitle) {
            antdMessage.error(TOAST_MESSAGES.TOPIC_TITLE_EMPTY)
            return
        }

        if (trimmedTitle === (topic.generated_title || topic.input_prompt)) {
            antdMessage.info(TOAST_MESSAGES.TOPIC_TITLE_NO_CHANGE)
            onClose()
            return
        }

        setIsSaving(true)
        try {
            await updateTopicById(topic.id, {
                generated_title: trimmedTitle
            })

            antdMessage.success(TOAST_MESSAGES.TOPIC_TITLE_UPDATE_SUCCESS)
            onClose()
            onSuccess?.()
        } catch (error: any) {
            console.error('TopicEditModal > failed >', error)
            antdMessage.error(error.message || TOAST_MESSAGES.TOPIC_TITLE_UPDATE_FAILED)
        } finally {
            setIsSaving(false)
        }
    }

    const handleCancel = () => {
        onClose()
    }

    return (
        <Modal
            title="제목 수정"
            open={isOpen}
            onOk={handleSave}
            onCancel={handleCancel}
            okText="저장"
            cancelText="취소"
            confirmLoading={isSaving}
            centered
            className={styles.modal}>
            <div className={styles.content}>
                <Input
                    id="edit-title"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="제목을 입력하세요."
                    maxLength={200}
                    showCount
                    onPressEnter={handleSave}
                    autoFocus
                    className={styles.input}
                />
            </div>
        </Modal>
    )
}

export default TopicEditModal
