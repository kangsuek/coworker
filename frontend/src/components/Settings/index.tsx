import { useEffect, useRef, useState } from 'react'
import { X, RotateCcw, Save, ChevronRight } from 'lucide-react'
import { api } from '../../lib/api'

interface Props {
  theme: 'light' | 'dark'
  onClose: () => void
}

type TabKey = 'cli' | 'agents' | 'keywords' | 'prompts'

interface TabDef {
  key: TabKey
  label: string
  fields: FieldDef[]
}

interface FieldDef {
  key: string
  label: string
  description?: string
  multiline?: boolean
  placeholder?: string
}

const TABS: TabDef[] = [
  {
    key: 'cli',
    label: 'CLI 경로',
    fields: [
      {
        key: 'claude_cli_path',
        label: 'Claude CLI 경로',
        description: 'claude 명령어 실행 경로 (예: /usr/local/bin/claude)',
        placeholder: 'claude',
      },
      {
        key: 'gemini_cli_path',
        label: 'Gemini CLI 경로',
        description: 'gemini 명령어 실행 경로 (예: /usr/local/bin/gemini)',
        placeholder: 'gemini',
      },
    ],
  },
  {
    key: 'agents',
    label: '에이전트 설정',
    fields: [
      {
        key: 'team_trigger_header',
        label: 'Team 모드 트리거',
        description: '메시지가 이 값으로 시작하면 Team 모드 실행 (예: (팀모드))',
        placeholder: '(팀모드)',
      },
      {
        key: 'max_sub_agents',
        label: '최대 Sub-Agent 수',
        description: 'Team 모드에서 동시 실행 가능한 최대 에이전트 수',
        placeholder: '5',
      },
      {
        key: 'role_add_trigger',
        label: '역할 추가 트리거',
        description: '세션 내 커스텀 역할 정의 트리거 키워드',
        placeholder: '(역할추가)',
      },
      {
        key: 'memory_trigger',
        label: '메모리 저장 트리거',
        description: '전역 메모리 저장 트리거 키워드',
        placeholder: '(기억)',
      },
    ],
  },
  {
    key: 'keywords',
    label: '역할 키워드',
    fields: [
      {
        key: 'role_researcher_keywords',
        label: 'Researcher 키워드',
        description: '쉼표로 구분 — 이 키워드가 포함된 태스크는 Researcher 역할로 분류됩니다',
        multiline: true,
      },
      {
        key: 'role_writer_keywords',
        label: 'Writer 키워드',
        multiline: true,
      },
      {
        key: 'role_planner_keywords',
        label: 'Planner 키워드',
        multiline: true,
      },
      {
        key: 'role_coder_keywords',
        label: 'Coder 키워드',
        multiline: true,
      },
      {
        key: 'role_reviewer_keywords',
        label: 'Reviewer 키워드',
        multiline: true,
      },
    ],
  },
  {
    key: 'prompts',
    label: '시스템 프롬프트',
    fields: [
      {
        key: 'prompt_agent_common',
        label: '공통 지침',
        description: '모든 에이전트 프롬프트 뒤에 자동으로 추가됩니다',
        multiline: true,
      },
      {
        key: 'prompt_researcher',
        label: 'Researcher 프롬프트',
        multiline: true,
      },
      {
        key: 'prompt_researcher_web_search',
        label: 'Researcher (웹 검색) 프롬프트',
        description: 'Gemini CLI 사용 시 Researcher에 적용됩니다',
        multiline: true,
      },
      {
        key: 'prompt_coder',
        label: 'Coder 프롬프트',
        multiline: true,
      },
      {
        key: 'prompt_reviewer',
        label: 'Reviewer 프롬프트',
        multiline: true,
      },
      {
        key: 'prompt_writer',
        label: 'Writer 프롬프트',
        multiline: true,
      },
      {
        key: 'prompt_planner',
        label: 'Planner 프롬프트',
        multiline: true,
      },
    ],
  },
]

export default function SettingsModal({ theme, onClose }: Props) {
  const isDark = theme === 'dark'
  const [activeTab, setActiveTab] = useState<TabKey>('cli')
  const [values, setValues] = useState<Record<string, string>>({})
  const [defaults, setDefaults] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.getSettings()
      .then((res) => {
        setValues(res.settings)
        setDefaults(res.defaults)
      })
      .catch(() => setError('설정을 불러오지 못했습니다.'))
      .finally(() => setLoading(false))
  }, [])

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const res = await api.updateSettings(values)
      setValues(res.settings)
      setDefaults(res.defaults)
      // 저장 완료 표시 (1.5초)
      const keys = new Set(Object.keys(values))
      setSavedKeys(keys)
      setTimeout(() => setSavedKeys(new Set()), 1500)
    } catch {
      setError('설정 저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('모든 설정을 기본값으로 초기화하시겠습니까?')) return
    setSaving(true)
    try {
      await api.resetSettings()
      const res = await api.getSettings()
      setValues(res.settings)
      setDefaults(res.defaults)
    } catch {
      setError('초기화에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const handleResetField = (key: string) => {
    setValues((prev) => ({ ...prev, [key]: defaults[key] ?? '' }))
  }

  const currentTab = TABS.find((t) => t.key === activeTab)!
  const hasChanges = Object.entries(values).some(([k, v]) => v !== (defaults[k] ?? ''))

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div
        className={`relative flex flex-col w-full max-w-3xl max-h-[90vh] rounded-2xl shadow-2xl overflow-hidden
          ${isDark ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-zinc-200'}
        `}
      >
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b shrink-0
          ${isDark ? 'border-zinc-800' : 'border-zinc-200'}
        `}>
          <h2 className="text-base font-semibold">환경설정</h2>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors ${isDark ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-500'}`}
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* Sidebar tabs */}
          <div className={`w-40 shrink-0 flex flex-col gap-0.5 p-3 border-r overflow-y-auto
            ${isDark ? 'border-zinc-800 bg-zinc-950/50' : 'border-zinc-200 bg-zinc-50'}
          `}>
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center justify-between w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors
                  ${activeTab === tab.key
                    ? isDark
                      ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/20'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : isDark
                      ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                      : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
                  }
                `}
              >
                {tab.label}
                {activeTab === tab.key && <ChevronRight size={14} />}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            {loading ? (
              <div className={`text-sm ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>불러오는 중...</div>
            ) : (
              currentTab.fields.map((field) => {
                const isDefault = values[field.key] === (defaults[field.key] ?? '')
                return (
                  <div key={field.key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className={`text-sm font-medium ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}>
                        {field.label}
                      </label>
                      {!isDefault && (
                        <button
                          onClick={() => handleResetField(field.key)}
                          className={`flex items-center gap-1 text-xs transition-colors
                            ${isDark ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'}
                          `}
                          title="기본값으로 되돌리기"
                        >
                          <RotateCcw size={11} />
                          기본값
                        </button>
                      )}
                    </div>
                    {field.description && (
                      <p className={`text-xs mb-2 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                        {field.description}
                      </p>
                    )}
                    {field.multiline ? (
                      <textarea
                        value={values[field.key] ?? ''}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        placeholder={field.placeholder ?? defaults[field.key] ?? ''}
                        rows={4}
                        className={`w-full rounded-lg border px-3 py-2 text-sm resize-y outline-none transition-colors
                          ${isDark
                            ? 'bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/50'
                            : 'bg-white border-zinc-300 text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-400'
                          }
                          ${!isDefault ? (isDark ? 'border-amber-500/40' : 'border-amber-400') : ''}
                        `}
                      />
                    ) : (
                      <input
                        type="text"
                        value={values[field.key] ?? ''}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        placeholder={field.placeholder ?? defaults[field.key] ?? ''}
                        className={`w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors
                          ${isDark
                            ? 'bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/50'
                            : 'bg-white border-zinc-300 text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-400'
                          }
                          ${!isDefault ? (isDark ? 'border-amber-500/40' : 'border-amber-400') : ''}
                        `}
                      />
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={`flex items-center justify-between px-6 py-4 border-t shrink-0
          ${isDark ? 'border-zinc-800 bg-zinc-950/50' : 'border-zinc-100 bg-zinc-50'}
        `}>
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              disabled={saving}
              className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors
                ${isDark ? 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800' : 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100'}
              `}
            >
              <RotateCcw size={14} />
              전체 초기화
            </button>
            {error && <span className="text-xs text-red-400">{error}</span>}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className={`px-4 py-1.5 rounded-lg text-sm transition-colors
                ${isDark ? 'text-zinc-400 hover:bg-zinc-800' : 'text-zinc-500 hover:bg-zinc-100'}
              `}
            >
              닫기
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium transition-all
                ${savedKeys.size > 0
                  ? 'bg-emerald-600 text-white'
                  : hasChanges && !saving
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md'
                    : isDark ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed' : 'bg-zinc-200 text-zinc-400 cursor-not-allowed'
                }
              `}
            >
              <Save size={14} />
              {savedKeys.size > 0 ? '저장됨' : saving ? '저장 중...' : '저장'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
