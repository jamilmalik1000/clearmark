import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Check, Download, Film, Image as ImageIcon, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react'
import { deleteJob, getJob, startProcessing, uploadMedia } from './api'
import MaskEditor from './components/MaskEditor'
import UploadPanel from './components/UploadPanel'
import { getMaskDataUrl } from './maskCanvas'

function App() {
  const [job, setJob] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [hasMask, setHasMask] = useState(false)
  const [method, setMethod] = useState('telea')
  const [radius, setRadius] = useState(3)
  const [error, setError] = useState('')
  const pollRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current)
    pollRef.current = null
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  const upload = async (file) => {
    setError('')
    setUploading(true)
    setUploadProgress(0)
    try {
      const created = await uploadMedia(file, setUploadProgress)
      setJob(created)
    } catch (uploadError) {
      setError(uploadError.message)
    } finally {
      setUploading(false)
    }
  }

  const poll = (jobId) => {
    stopPolling()
    pollRef.current = window.setInterval(async () => {
      try {
        const current = await getJob(jobId)
        setJob(current)
        if (current.status === 'complete' || current.status === 'failed') stopPolling()
      } catch (pollError) {
        setError(pollError.message)
        stopPolling()
      }
    }, 700)
  }

  const process = async () => {
    if (!job || !hasMask) return
    setError('')
    try {
      const current = await startProcessing(job.id, {
        mask_data_url: getMaskDataUrl(),
        method,
        radius,
      })
      setJob(current)
      poll(job.id)
    } catch (processError) {
      setError(processError.message)
    }
  }

  const reset = async () => {
    stopPolling()
    if (job && job.status !== 'processing') deleteJob(job.id).catch(() => {})
    setJob(null)
    setHasMask(false)
    setError('')
  }

  const processing = job?.status === 'processing'
  const complete = job?.status === 'complete'

  return (
    <div className="app-shell">
      <header className="site-header">
        <button className="brand" type="button" onClick={job ? reset : undefined}>
          <span className="brand-mark"><Sparkles size={19} /></span>
          <span>ClearMark</span>
        </button>
        <div className="header-badge"><ShieldCheck size={15} /> Private by design</div>
      </header>

      <main>
        {!job ? (
          <UploadPanel onFile={upload} uploading={uploading} progress={uploadProgress} />
        ) : (
          <section className="workspace">
            <div className="workspace-heading">
              <button className="back-button" type="button" onClick={reset} disabled={processing}><ArrowLeft size={18} /> New file</button>
              <div>
                <span className="step-label">{complete ? 'Result ready' : 'Step 2 of 2'}</span>
                <h1>{complete ? 'Your clean copy is ready.' : 'Mark the area to remove.'}</h1>
              </div>
              <div className="file-chip">
                {job.media_type === 'video' ? <Film size={16} /> : <ImageIcon size={16} />}
                <span>{job.filename}</span>
                <small>{job.width} × {job.height}</small>
              </div>
            </div>

            {complete ? (
              <ResultView job={job} onReset={reset} />
            ) : (
              <div className="workspace-grid">
                <MaskEditor
                  key={job.id}
                  previewUrl={`${job.preview_url}?v=${job.id}`}
                  width={job.width}
                  height={job.height}
                  disabled={processing}
                  onMaskChange={setHasMask}
                />
                <aside className="settings-panel">
                  <div>
                    <span className="panel-number">01</span>
                    <h2>Refine the fill</h2>
                    <p>Choose how OpenCV rebuilds the painted area.</p>
                  </div>
                  <div className="setting-block">
                    <span className="setting-label">Method</span>
                    <label className={`method-card ${method === 'telea' ? 'selected' : ''}`}>
                      <input type="radio" name="method" value="telea" checked={method === 'telea'} disabled={processing} onChange={() => setMethod('telea')} />
                      <span><strong>Fast fill</strong><small>Best for text and small logos</small></span>
                      {method === 'telea' && <Check size={17} />}
                    </label>
                    <label className={`method-card ${method === 'ns' ? 'selected' : ''}`}>
                      <input type="radio" name="method" value="ns" checked={method === 'ns'} disabled={processing} onChange={() => setMethod('ns')} />
                      <span><strong>Fluid fill</strong><small>Useful around soft gradients</small></span>
                      {method === 'ns' && <Check size={17} />}
                    </label>
                  </div>
                  <label className="radius-control">
                    <span><span className="setting-label">Fill radius</span><output>{radius}px</output></span>
                    <input type="range" min="1" max="12" step="1" value={radius} disabled={processing} onChange={(event) => setRadius(Number(event.target.value))} />
                    <small>Increase for larger or softer marks.</small>
                  </label>
                  {job.media_type === 'video' && (
                    <div className="video-note"><Film size={18} /><span>The same mask will be applied to every frame. This works best for a stationary mark.</span></div>
                  )}
                  <button className="process-button" type="button" disabled={!hasMask || processing} onClick={process}>
                    {processing ? <><LoaderCircle className="spin" size={19} /> Processing {Math.round(job.progress)}%</> : <><Sparkles size={18} /> Remove marked area</>}
                  </button>
                  {processing && <div className="process-track"><span style={{ width: `${job.progress}%` }} /></div>}
                  {!hasMask && !processing && <span className="button-help">Paint on the image to enable processing.</span>}
                  {job.status === 'failed' && <div className="inline-error">{job.error}</div>}
                </aside>
              </div>
            )}
          </section>
        )}
        {error && <div className="toast" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}
      </main>

      <footer><span>Powered by OpenCV inpainting</span><span>Use only on media you own or have permission to edit.</span></footer>
    </div>
  )
}

function ResultView({ job, onReset }) {
  const resultUrl = `${job.result_url}?v=${job.id}`
  return (
    <div className="result-layout">
      <div className="result-media">
        {job.media_type === 'image' ? (
          <img src={resultUrl} alt="Processed result" />
        ) : (
          <video src={resultUrl} controls autoPlay playsInline />
        )}
      </div>
      <aside className="result-panel">
        <div className="success-mark"><Check size={28} /></div>
        <h2>Finished processing</h2>
        <p>Your {job.media_type} has been reconstructed around the area you painted.</p>
        <a className="download-button" href={resultUrl} download={job.media_type === 'image' ? 'clearmark-result.png' : 'clearmark-result.mp4'}><Download size={19} /> Download result</a>
        <button className="secondary-button" type="button" onClick={onReset}>Process another file</button>
      </aside>
    </div>
  )
}

export default App

