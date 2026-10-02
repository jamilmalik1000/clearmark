export function getMaskDataUrl() {
  const canvas = document.querySelector('.canvas-stack canvas')
  return canvas?.toDataURL('image/png')
}

