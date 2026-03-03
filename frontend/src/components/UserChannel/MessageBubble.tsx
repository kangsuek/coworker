import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

import type { TimingInfo, UserMessage } from '../../types/api'

function shortModelName(model: string | null | undefined): string | null {
  if (!model) return null
  if (model.includes('haiku')) return 'Haiku'
  if (model.includes('sonnet')) return 'Sonnet'
  if (model.includes('opus')) return 'Opus'
  return model
}

function formatTiming(timing: TimingInfo | null | undefined): string | null {
  if (!timing?.finished_at || !timing?.thinking_started_at) return null
  const total = (Date.parse(timing.finished_at) - Date.parse(timing.thinking_started_at)) / 1000
  if (timing.cli_started_at) {
    const classify =
      (Date.parse(timing.cli_started_at) - Date.parse(timing.thinking_started_at)) / 1000
    const cli = (Date.parse(timing.finished_at) - Date.parse(timing.cli_started_at)) / 1000
    return `총 ${total.toFixed(1)}s (분류: ${classify.toFixed(1)}s · CLI: ${cli.toFixed(1)}s)`
  }
  return `총 ${total.toFixed(1)}s`
}

interface Props {
  message: UserMessage
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const modelLabel = shortModelName(message.model)
  const modeLabel = message.mode === 'solo' ? 'Solo' : message.mode === 'team' ? 'Team' : null
  const timingLabel = formatTiming(message.timing)

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-sm px-4 py-3 ${
          isUser
            ? 'bg-emerald-50 border border-emerald-200 text-emerald-900 font-mono text-sm dark:bg-emerald-900/40 dark:border-emerald-500/50 dark:text-emerald-100'
            : 'bg-white dark:bg-transparent border border-gray-200 dark:border-white/10 text-gray-800 dark:text-gray-300 shadow-sm dark:shadow-none'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <div
              className="text-sm leading-relaxed max-w-none
                [&_p]:mb-2 [&_p:last-child]:mb-0
                [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2
                [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2
                [&_li]:mb-1
                [&_h1]:text-base [&_h1]:font-bold [&_h1]:mb-2
                [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mb-2
                [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1
                [&_pre]:my-2 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:bg-gray-100 [&_pre]:dark:bg-black/30 [&_pre]:p-3
                [&_code]:font-mono [&_code]:text-xs [&_pre_code]:bg-transparent [&_pre_code]:p-0
                [&_blockquote]:border-l-4 [&_blockquote]:border-gray-400 [&_blockquote]:pl-3 [&_blockquote]:text-gray-600 [&_blockquote]:dark:text-gray-400
                [&_hr]:my-3 [&_hr]:border-gray-200 [&_hr]:dark:border-white/20
                [&_a]:text-emerald-600 [&_a]:dark:text-emerald-400 [&_a]:underline [&_a]:break-all
                [&_strong]:font-semibold
                [&_table]:w-full [&_table]:my-3 [&_table]:border-collapse
                [&_th]:border [&_th]:border-gray-300 [&_th]:dark:border-white/20 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_th]:bg-gray-100 [&_th]:dark:bg-white/5
                [&_td]:border [&_td]:border-gray-300 [&_td]:dark:border-white/20 [&_td]:px-3 [&_td]:py-2
                [&_tr]:border-b [&_tr]:border-gray-200 [&_tr]:dark:border-white/10"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
            </div>
            {(modeLabel || modelLabel || timingLabel) && (
              <div className="mt-1.5 flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                {modeLabel && <span>{modeLabel}</span>}
                {modeLabel && modelLabel && <span>&middot;</span>}
                {modelLabel && <span>{modelLabel}</span>}
                {timingLabel && (modelLabel || modeLabel) && <span>&middot;</span>}
                {timingLabel && <span className="opacity-50">{timingLabel}</span>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
