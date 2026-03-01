import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'

import type { UserMessage } from '../../types/api'

interface Props {
  message: UserMessage
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-900 shadow-sm'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
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
        )}
      </div>
    </div>
  )
}
