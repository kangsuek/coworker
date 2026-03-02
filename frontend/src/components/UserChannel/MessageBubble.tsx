import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'

import type { UserMessage } from '../../types/api'

function shortModelName(model: string | null | undefined): string | null {
  if (!model) return null
  if (model.includes('haiku')) return 'Haiku'
  if (model.includes('sonnet')) return 'Sonnet'
  if (model.includes('opus')) return 'Opus'
  return model
}

interface Props {
  message: UserMessage
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const modelLabel = shortModelName(message.model)
  const modeLabel = message.mode === 'solo' ? 'Solo' : message.mode === 'team' ? 'Team' : null

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-sm px-4 py-3 ${
          isUser
            ? 'bg-emerald-900/20 border border-emerald-500/30 text-emerald-400 font-mono text-sm'
            : 'bg-transparent border border-white/10 text-gray-300'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <div
              className="text-sm leading-relaxed
                [&_p]:mb-2 [&_p:last-child]:mb-0
                [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:mb-2
                [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:mb-2
                [&_li]:mb-1
                [&_h1]:text-base [&_h1]:font-bold [&_h1]:mb-2
                [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mb-2
                [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mb-1
                [&_pre]:my-2 [&_pre]:rounded-lg [&_pre]:overflow-x-auto
                [&_code]:font-mono [&_code]:text-xs
                [&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:pl-3 [&_blockquote]:text-gray-600
                [&_hr]:my-3 [&_hr]:border-gray-200
                [&_a]:text-blue-600 [&_a]:underline
                [&_strong]:font-semibold"
            >
              <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
            </div>
            {(modeLabel || modelLabel) && (
              <div className="mt-1.5 flex items-center gap-1 text-xs text-gray-400">
                {modeLabel && <span>{modeLabel}</span>}
                {modeLabel && modelLabel && <span>&middot;</span>}
                {modelLabel && <span>{modelLabel}</span>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
