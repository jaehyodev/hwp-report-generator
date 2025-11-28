import React, {useState} from 'react'
import {Form, Input, Button, Card} from 'antd'
import {LockOutlined} from '@ant-design/icons'
import {useMessage} from '../contexts/MessageContext'
import {TOAST_MESSAGES} from '../constants'
import {useNavigate} from 'react-router-dom'
import {useAuth} from '../hooks/useAuth'
import type {ChangePasswordRequest} from '../types/auth'
import MainLayout from '../components/layout/MainLayout'
import styles from './ChangePasswordPage.module.css'

const ChangePasswordPage: React.FC = () => {
    const {antdMessage} = useMessage()
    const [loading, setLoading] = useState(false)
    const {changePassword} = useAuth()
    const navigate = useNavigate()

    const onFinish = async (values: ChangePasswordRequest & {confirmPassword: string}) => {
        setLoading(true)
        try {
            await changePassword({
                current_password: values.current_password,
                new_password: values.new_password
            })
            antdMessage.success(TOAST_MESSAGES.PASSWORD_CHANGE_SUCCESS)
            navigate('/')
        } catch (error: any) {
            antdMessage.error(error.response?.data?.detail || TOAST_MESSAGES.PASSWORD_CHANGE_FAILED)
        } finally {
            setLoading(false)
        }
    }

    return (
        <MainLayout>
            <div className={styles.container}>
                <Card title="비밀번호 변경" className={styles.card}>
                    <Form name="changePassword" onFinish={onFinish} autoComplete="off" layout="vertical">
                        <Form.Item label="현재 비밀번호" name="current_password" rules={[{required: true, message: '현재 비밀번호를 입력해주세요!'}]}>
                            <Input.Password prefix={<LockOutlined />} placeholder="현재 비밀번호를 입력하세요" size="large" />
                        </Form.Item>

                        <Form.Item
                            label="새 비밀번호"
                            name="new_password"
                            rules={[
                                {required: true, message: '새 비밀번호를 입력해주세요!'},
                                {min: 8, message: '비밀번호는 최소 8자 이상이어야 합니다!'}
                            ]}>
                            <Input.Password prefix={<LockOutlined />} placeholder="새 비밀번호를 입력하세요" size="large" />
                        </Form.Item>

                        <Form.Item
                            label="새 비밀번호 확인"
                            name="confirmPassword"
                            dependencies={['new_password']}
                            rules={[
                                {required: true, message: '비밀번호를 다시 입력해주세요!'},
                                ({getFieldValue}) => ({
                                    validator(_, value) {
                                        if (!value || getFieldValue('new_password') === value) {
                                            return Promise.resolve()
                                        }
                                        return Promise.reject(new Error('비밀번호가 일치하지 않습니다!'))
                                    }
                                })
                            ]}>
                            <Input.Password prefix={<LockOutlined />} placeholder="새 비밀번호를 다시 입력하세요" size="large" />
                        </Form.Item>

                        <Form.Item>
                            <Button type="primary" htmlType="submit" loading={loading} block size="large">
                                비밀번호 변경
                            </Button>
                        </Form.Item>
                    </Form>
                </Card>
            </div>
        </MainLayout>
    )
}

export default ChangePasswordPage
