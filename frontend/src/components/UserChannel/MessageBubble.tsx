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
    <div className="flex flex-col mb-6">
      {isUser ? (
        <div className="p-4 rounded-xl border bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-950/20 dark:border-emerald-900/50 dark:text-emerald-50 text-[15px] leading-relaxed shadow-sm">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      ) : (
        <div className="flex justify-start mt-2">
          <div className="px-4 py-3 rounded-xl border bg-zinc-100 border-zinc-200 text-zinc-700 dark:bg-zinc-900/80 dark:border-zinc-800 dark:text-zinc-300 text-[14px] max-w-[85%] sm:max-w-[80%]">
            <div
              className="leading-relaxed max-w-none
                [&_p]:mb-2 [&_p:last-child]:mb-0
                [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2
                [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2
                [&_li]:mb-1
                [&_h1]:text-base [&_h1]:font-bold [&_h1]:mb-2
                [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mb-2
                [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1
                [&_pre]:my-2 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:bg-zinc-200 [&_pre]:dark:bg-black/30 [&_pre]:p-3
                [&_code]:font-mono [&_code]:text-[13px] [&_pre_code]:bg-transparent [&_pre_code]:p-0
                [&_blockquote]:border-l-4 [&_blockquote]:border-zinc-400 [&_blockquote]:pl-3 [&_blockquote]:text-zinc-600 [&_blockquote]:dark:text-zinc-400
                [&_hr]:my-3 [&_hr]:border-zinc-300 [&_hr]:dark:border-white/20
                [&_a]:text-emerald-600 [&_a]:dark:text-emerald-400 [&_a]:underline [&_a]:break-all
                [&_strong]:font-semibold
                [&_table]:w-full [&_table]:my-3 [&_table]:border-collapse
                [&_th]:border [&_th]:border-zinc-300 [&_th]:dark:border-white/20 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold [&_th]:bg-zinc-200 [&_th]:dark:bg-white/5
                [&_td]:border [&_td]:border-zinc-300 [&_td]:dark:border-white/20 [&_td]:px-3 [&_td]:py-2
                [&_tr]:border-b [&_tr]:border-zinc-200 [&_tr]:dark:border-white/10"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
            </div>
            {(modeLabel || modelLabel || timingLabel) && (
              <div className="mt-2 flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                {modeLabel && <span>{modeLabel}</span>}
                {modeLabel && modelLabel && <span>&middot;</span>}
                {modelLabel && <span>{modelLabel}</span>}
                {timingLabel && (modelLabel || modeLabel) && <span>&middot;</span>}
                {timingLabel && <span className="opacity-70">{timingLabel}</span>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
