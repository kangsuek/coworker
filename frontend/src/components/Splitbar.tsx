import { useCallback, useRef } from 'react'

interface Props {
  onResize: (deltaX: number) => void
  className?: string
}

/**
 * 세로 스플릿바. 드래그 시 onResize(deltaX) 호출.
 * deltaX > 0 = 오른쪽으로 드래그.
 */
export default function Splitbar({ onResize, className = '' }: Props) {
  const startX = useRef(0)

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      startX.current = e.clientX

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const deltaX = moveEvent.clientX - startX.current
        startX.current = moveEvent.clientX
        onResize(deltaX)
      }

      const handleMouseUp = () => {
        document.body.classList.remove('select-none', 'cursor-col-resize')
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }

      document.body.classList.add('select-none', 'cursor-col-resize')
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    },
    [onResize],
  )

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      className={`w-1 shrink-0 bg-gray-200 dark:bg-white/10 hover:bg-emerald-500 transition-colors cursor-col-resize flex-shrink-0 ${className}`}
      onMouseDown={handleMouseDown}
      title="드래그하여 너비 조절"
    />
  )
}
