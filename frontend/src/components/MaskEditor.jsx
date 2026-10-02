import { useCallback, useEffect, useRef, useState } from 'react'
import { Brush, Eraser, Redo2, RotateCcw, Trash2 } from 'lucide-react'

export default function MaskEditor({ previewUrl, width, height, disabled, onMaskChange }) {
  const wrapRef = useRef(null)
  const imageRef = useRef(null)
  const canvasRef = useRef(null)
  const drawing = useRef(false)
  const history = useRef([])
  const historyIndex = useRef(-1)
  const [tool, setTool] = useState('brush')
  const [brushSize, setBrushSize] = useState(36)
  const [ready, setReady] = useState(false)

  const notify = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
    let hasPaint = false
    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] > 8) { hasPaint = true; break }
    }
    onMaskChange(hasPaint)
  }, [onMaskChange])

  const snapshot = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const state = canvas.toDataURL('image/png')
    const next = history.current.slice(0, historyIndex.current + 1)
    next.push(state)
    if (next.length > 30) next.shift()
    history.current = next
    historyIndex.current = next.length - 1
    notify()
  }, [notify])

  const restore = useCallback((state) => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context || !state) return
    const image = new Image()
    image.onload = () => {
      context.clearRect(0, 0, canvas.width, canvas.height)
      context.drawImage(image, 0, 0)
      notify()
    }
    image.src = state
  }, [notify])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.width = Math.max(1, width)
    canvas.height = Math.max(1, height)
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
    history.current = [canvas.toDataURL('image/png')]
    historyIndex.current = 0
    setReady(true)
    onMaskChange(false)
  }, [height, onMaskChange, previewUrl, width])

  const position = (event) => {
    const canvas = canvasRef.current
    const bounds = canvas.getBoundingClientRect()
    return {
      x: (event.clientX - bounds.left) * (canvas.width / bounds.width),
      y: (event.clientY - bounds.top) * (canvas.height / bounds.height),
    }
  }

  const begin = (event) => {
    if (disabled || !ready) return
    event.currentTarget.setPointerCapture(event.pointerId)
    drawing.current = true
    const context = canvasRef.current.getContext('2d')
    const point = position(event)
    context.beginPath()
    context.moveTo(point.x, point.y)
    context.lineTo(point.x + 0.01, point.y + 0.01)
    paint(context)
  }

  const paint = (context) => {
    const scale = width / Math.max(1, canvasRef.current.getBoundingClientRect().width)
    context.lineWidth = brushSize * scale
    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over'
    context.strokeStyle = 'rgba(255, 78, 61, 0.62)'
    context.stroke()
  }

  const move = (event) => {
    if (!drawing.current) return
    const context = canvasRef.current.getContext('2d')
    const point = position(event)
    context.lineTo(point.x, point.y)
    paint(context)
  }

  const end = () => {
    if (!drawing.current) return
    drawing.current = false
    snapshot()
  }

  const undo = () => {
    if (historyIndex.current <= 0) return
    historyIndex.current -= 1
    restore(history.current[historyIndex.current])
  }

  const redo = () => {
    if (historyIndex.current >= history.current.length - 1) return
    historyIndex.current += 1
    restore(history.current[historyIndex.current])
  }

  const clear = () => {
    const canvas = canvasRef.current
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
    snapshot()
  }

  return (
    <div className="editor-shell">
      <div className="editor-toolbar">
        <div className="tool-group" aria-label="Drawing tools">
          <button className={tool === 'brush' ? 'active' : ''} type="button" onClick={() => setTool('brush')} disabled={disabled} title="Brush"><Brush size={18} /><span>Brush</span></button>
          <button className={tool === 'eraser' ? 'active' : ''} type="button" onClick={() => setTool('eraser')} disabled={disabled} title="Eraser"><Eraser size={18} /><span>Eraser</span></button>
        </div>
        <label className="brush-control">
          <span>Size</span>
          <input type="range" min="8" max="100" value={brushSize} disabled={disabled} onChange={(event) => setBrushSize(Number(event.target.value))} />
          <output>{brushSize}px</output>
        </label>
        <div className="icon-tools">
          <button type="button" onClick={undo} disabled={disabled} title="Undo"><RotateCcw size={18} /></button>
          <button type="button" onClick={redo} disabled={disabled} title="Redo"><Redo2 size={18} /></button>
          <button type="button" onClick={clear} disabled={disabled} title="Clear mask"><Trash2 size={18} /></button>
        </div>
      </div>
      <div className="canvas-stage" ref={wrapRef}>
        <div className="canvas-stack" style={{ aspectRatio: `${width} / ${height}` }}>
          <img ref={imageRef} src={previewUrl} alt="Media preview" draggable="false" />
          <canvas
            ref={canvasRef}
            aria-label="Paint the area to remove"
            onPointerDown={begin}
            onPointerMove={move}
            onPointerUp={end}
            onPointerCancel={end}
            onPointerLeave={end}
          />
        </div>
      </div>
      <div className="editor-hint"><span className="hint-swatch" /> Paint a little beyond the mark’s edges for a smoother result.</div>
    </div>
  )
}


