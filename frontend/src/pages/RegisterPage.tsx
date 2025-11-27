import React, {useState} from 'react'
import {Form, Input, Button, Card, message} from 'antd'
import {UserOutlined, LockOutlined, MailOutlined} from '@ant-design/icons'
import {useNavigate, Link} from 'react-router-dom'
import {useAuth} from '../hooks/useAuth'
import type {RegisterRequest} from '../types/auth'
import styles from './RegisterPage.module.css'

const RegisterPage: React.FC = () => {
    const [loading, setLoading] = useState(false)
    const {register} = useAuth()
    const navigate = useNavigate()

    const onFinish = async (values: RegisterRequest & {confirmPassword: string}) => {
        setLoading(true)
        try {
            // confirmPassword 제외하고 백엔드로 전송
            const {confirmPassword, ...registerData} = values
            await register(registerData)
            message.success('회원가입이 완료되었습니다. 관리자 승인 후 로그인 가능합니다.')
            navigate('/login')
        } catch (error: any) {
            message.error(error.response?.data?.detail || '회원가입에 실패했습니다.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className={styles.container}>
            <Card className={styles.card}>
                <div className={styles.header}>
                    <h1>HWP 보고서 자동 생성 시스템</h1>
                    <h2 className={styles.subtitle}>회원가입</h2>
                </div>

                <Form name="register" onFinish={onFinish} autoComplete="off" layout="vertical">
                    <Form.Item
                        label="이메일"
                        name="email"
                        rules={[
                            {required: true, message: '이메일을 입력해주세요!'},
                            {type: 'email', message: '올바른 이메일 형식이 아닙니다!'}
                        ]}>
                        <Input prefix={<MailOutlined />} placeholder="이메일을 입력하세요" size="large" />
                    </Form.Item>

                    <Form.Item
                        label="사용자명"
                        name="username"
                        rules={[
                            {required: true, message: '사용자명을 입력해주세요!'},
                            {min: 3, message: '사용자명은 최소 3자 이상이어야 합니다!'}
                        ]}>
                        <Input prefix={<UserOutlined />} placeholder="사용자명을 입력하세요" size="large" />
                    </Form.Item>

                    <Form.Item
                        label="비밀번호"
                        name="password"
                        rules={[
                            {required: true, message: '비밀번호를 입력해주세요!'},
                            {min: 8, message: '비밀번호는 최소 8자 이상이어야 합니다!'}
                        ]}>
                        <Input.Password prefix={<LockOutlined />} placeholder="비밀번호를 입력하세요" size="large" />
                    </Form.Item>

                    <Form.Item
                        label="비밀번호 확인"
                        name="confirmPassword"
                        dependencies={['password']}
                        rules={[
                            {required: true, message: '비밀번호를 다시 입력해주세요!'},
                            ({getFieldValue}) => ({
                                validator(_, value) {
                                    if (!value || getFieldValue('password') === value) {
                                        return Promise.resolve()
                                    }
                                    return Promise.reject(new Error('비밀번호가 일치하지 않습니다!'))
                                }
                            })
                        ]}>
                        <Input.Password prefix={<LockOutlined />} placeholder="비밀번호를 다시 입력하세요" size="large" />
                    </Form.Item>

                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={loading} block size="large">
                            회원가입
                        </Button>
                    </Form.Item>

                    <div className={styles.footer}>
                        <span>이미 계정이 있으신가요? </span>
                        <Link to="/login">로그인</Link>
                    </div>
                </Form>
            </Card>
        </div>
    )
}

export default RegisterPage
