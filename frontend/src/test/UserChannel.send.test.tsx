/**
 * FE-02: UserChannel handleSend() 파일 업로드 플로우 TDD 테스트
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// api 모듈 모킹
vi.mock('../lib/api', () => ({
  api: {
    chat: vi.fn(),
    uploadFiles: vi.fn(),
    getRunStatus: vi.fn(),
  },
}))

import { api } from '../lib/api'
import UserChannel from '../components/UserChannel'

const defaultProps = {
  currentSession: null,
  messages: [],
  runId: null,
  runStatus: { status: 'done' as const, progress: null, response: null, mode: null, model: null, agents: null, timing: null },
  onMessageAdded: vi.fn(),
  onSessionCreated: vi.fn(),
  onModeChange: vi.fn(),
  onRunChange: vi.fn(),
}

describe('UserChannel handleSend — 파일 업로드 플로우', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.chat as ReturnType<typeof vi.fn>).mockResolvedValue({ run_id: 'run-1', session_id: 'sess-1' })
    ;(api.uploadFiles as ReturnType<typeof vi.fn>).mockResolvedValue({
      uploaded: [{ file_id: 'fid-1', filename: 'photo.png', size: 100 }],
    })
  })

  it('파일이 없으면 uploadFiles를 호출하지 않아야 한다', async () => {
    render(<UserChannel {...defaultProps} />)
    const textarea = screen.getByPlaceholderText('메시지를 입력하세요...')
    await userEvent.type(textarea, '안녕')
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(api.chat).toHaveBeenCalledOnce())
    expect(api.uploadFiles).not.toHaveBeenCalled()
  })

  it('파일이 있으면 chat 호출 전에 uploadFiles를 먼저 호출해야 한다', async () => {
    const callOrder: string[] = []
    ;(api.uploadFiles as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      callOrder.push('upload')
      return { uploaded: [{ file_id: 'fid-1', filename: 'photo.png', size: 100 }] }
    })
    ;(api.chat as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      callOrder.push('chat')
      return { run_id: 'run-1', session_id: 'sess-1' }
    })

    render(<UserChannel {...defaultProps} />)

    // 파일 첨부
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    // 메시지 전송
    const textarea = screen.getByPlaceholderText('메시지를 입력하세요...')
    await userEvent.type(textarea, '이미지 분석해줘')
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(callOrder).toContain('chat'))
    expect(callOrder[0]).toBe('upload')
    expect(callOrder[1]).toBe('chat')
  })

  it('chat 요청에 업로드된 file_ids가 포함되어야 한다', async () => {
    ;(api.uploadFiles as ReturnType<typeof vi.fn>).mockResolvedValue({
      uploaded: [{ file_id: 'fid-abc', filename: 'photo.png', size: 100 }],
    })

    render(<UserChannel {...defaultProps} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    const textarea = screen.getByPlaceholderText('메시지를 입력하세요...')
    await userEvent.type(textarea, '분석해줘')
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(api.chat).toHaveBeenCalledOnce())
    const chatArg = (api.chat as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(chatArg.file_ids).toEqual(['fid-abc'])
  })

  it('전송 완료 후 첨부 파일 목록이 초기화되어야 한다', async () => {
    render(<UserChannel {...defaultProps} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    // 파일 태그 표시 확인
    expect(screen.getByText('photo.png')).toBeInTheDocument()

    const textarea = screen.getByPlaceholderText('메시지를 입력하세요...')
    await userEvent.type(textarea, '분석해줘')
    await userEvent.keyboard('{Enter}')

    // 전송 후 파일 태그 사라짐
    await waitFor(() => expect(screen.queryByText('photo.png')).not.toBeInTheDocument())
  })

  it('파일 업로드 실패 시 에러 메시지를 표시해야 한다', async () => {
    ;(api.uploadFiles as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('upload failed'))

    render(<UserChannel {...defaultProps} />)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    const textarea = screen.getByPlaceholderText('메시지를 입력하세요...')
    await userEvent.type(textarea, '분석해줘')
    await userEvent.keyboard('{Enter}')

    await waitFor(() =>
      expect(defaultProps.onMessageAdded).toHaveBeenCalledWith(
        expect.objectContaining({ role: 'reader' })
      )
    )
    // chat은 호출되지 않아야 한다
    expect(api.chat).not.toHaveBeenCalled()
  })
})
