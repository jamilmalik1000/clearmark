async function readError(response) {
  try {
    const payload = await response.json()
    return payload.detail || payload.message || 'Something went wrong.'
  } catch {
    return `Request failed (${response.status}).`
  }
}

export async function uploadMedia(file, onProgress) {
  const form = new FormData()
  form.append('file', file)

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', '/api/jobs')
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100))
    }
    request.onload = async () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(JSON.parse(request.responseText))
      } else {
        try {
          const payload = JSON.parse(request.responseText)
          reject(new Error(payload.detail || 'Upload failed.'))
        } catch {
          reject(new Error(`Upload failed (${request.status}).`))
        }
      }
    }
    request.onerror = () => reject(new Error('Could not reach the API. Is FastAPI running?'))
    request.send(form)
  })
}

export async function startProcessing(jobId, options) {
  const response = await fetch(`/api/jobs/${jobId}/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function getJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function deleteJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 404) throw new Error(await readError(response))
}

