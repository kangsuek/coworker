/**
 * FE-01: api.ts uploadFiles() 메서드 TDD 테스트
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('api.uploadFiles', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uploadFiles 메서드가 api 객체에 존재해야 한다', async () => {
    const { api } = await import('../lib/api')
    expect(typeof api.uploadFiles).toBe('function')
  })

  it('POST /api/upload 엔드포인트로 FormData를 전송해야 한다', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ uploaded: [{ file_id: 'uuid-1', filename: 'photo.png', size: 100 }] }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('../lib/api')
    const file = new File(['content'], 'photo.png', { type: 'image/png' })
    await api.uploadFiles([file])

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/upload')
    expect(options.method).toBe('POST')
    expect(options.body).toBeInstanceOf(FormData)
  })

  it('FormData에 files 키로 파일이 담겨야 한다', async () => {
    let capturedBody: FormData | null = null
    const mockFetch = vi.fn().mockImplementation((_url, options) => {
      capturedBody = options.body
      return Promise.resolve({
        ok: true,
        json: async () => ({ uploaded: [] }),
      })
    })
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('../lib/api')
    const file = new File(['hello'], 'main.py', { type: 'text/plain' })
    await api.uploadFiles([file])

    expect(capturedBody).not.toBeNull()
    const entries = Array.from((capturedBody as unknown as FormData).entries())
    expect(entries.some(([key, val]) => key === 'files' && (val as File).name === 'main.py')).toBe(true)
  })

  it('복수 파일을 FormData에 모두 담아야 한다', async () => {
    let capturedBody: FormData | null = null
    const mockFetch = vi.fn().mockImplementation((_url, options) => {
      capturedBody = options.body
      return Promise.resolve({
        ok: true,
        json: async () => ({ uploaded: [] }),
      })
    })
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('../lib/api')
    const files = [
      new File(['a'], 'a.txt', { type: 'text/plain' }),
      new File(['b'], 'b.md', { type: 'text/markdown' }),
    ]
    await api.uploadFiles(files)

    const entries = Array.from((capturedBody as unknown as FormData).entries())
    const fileEntries = entries.filter(([key]) => key === 'files')
    expect(fileEntries).toHaveLength(2)
  })

  it('서버 응답의 uploaded 배열을 반환해야 한다', async () => {
    const mockResponse = {
      uploaded: [
        { file_id: 'uuid-abc', filename: 'photo.png', size: 512 },
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    }))

    const { api } = await import('../lib/api')
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    const result = await api.uploadFiles([file])

    expect(result.uploaded).toHaveLength(1)
    expect(result.uploaded[0].file_id).toBe('uuid-abc')
    expect(result.uploaded[0].filename).toBe('photo.png')
  })

  it('서버 오류(4xx/5xx) 시 에러를 throw해야 한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'bad extension' }),
    }))

    const { api } = await import('../lib/api')
    const file = new File(['x'], 'bad.exe')
    await expect(api.uploadFiles([file])).rejects.toThrow()
  })
})
