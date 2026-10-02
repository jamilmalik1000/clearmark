import { useRef, useState } from 'react'
import { FileImage, Film, UploadCloud } from 'lucide-react'

const ACCEPTED = 'image/png,image/jpeg,image/webp,image/bmp,video/mp4,video/quicktime,video/x-msvideo,video/webm,.mkv,.m4v'

export default function UploadPanel({ onFile, uploading, progress }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const choose = (files) => {
    const file = files?.[0]
    if (file && !uploading) onFile(file)
  }

  return (
    <section className="upload-section" aria-labelledby="upload-title">
      <div className="intro-copy">
        <span className="eyebrow">Local visual cleanup</span>
        <h1 id="upload-title">Remove what doesn’t belong.</h1>
        <p>Upload an image or video, brush over the unwanted mark, and reconstruct the area with computer vision.</p>
      </div>

      <button
        className={`drop-zone ${dragging ? 'is-dragging' : ''}`}
        type="button"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files) }}
      >
        <input ref={inputRef} hidden type="file" accept={ACCEPTED} onChange={(event) => choose(event.target.files)} />
        <span className="upload-icon"><UploadCloud size={30} /></span>
        {uploading ? (
          <>
            <strong>Uploading… {progress}%</strong>
            <span className="upload-track"><span style={{ width: `${progress}%` }} /></span>
          </>
        ) : (
          <>
            <strong>Drop a file here</strong>
            <span>or click to browse · up to 500 MB</span>
            <div className="format-pills">
              <span><FileImage size={15} /> PNG · JPG · WEBP</span>
              <span><Film size={15} /> MP4 · MOV · WEBM</span>
            </div>
          </>
        )}
      </button>

      <div className="privacy-note">
        <span className="pulse-dot" />
        Files stay in your local server workspace and expire automatically.
      </div>
    </section>
  )
}

