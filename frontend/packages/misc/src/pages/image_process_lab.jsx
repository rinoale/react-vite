import { useState, useRef, useCallback } from 'react'
import { Upload, Download, RotateCcw, FlipHorizontal, SlidersHorizontal, Droplets, Grid3X3, Scan, Pipette, HelpCircle, Grid2X2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

// --- Image processing kernels (pure functions on ImageData) ---

function applyGrayscale(imageData, method) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    let gray
    switch (method) {
      case 'bt601':  gray = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2]; break
      case 'bt709':  gray = 0.2126 * d[i] + 0.7152 * d[i+1] + 0.0722 * d[i+2]; break
      case 'equal':  gray = (d[i] + d[i+1] + d[i+2]) / 3; break
      case 'red':    gray = d[i]; break
      case 'green':  gray = d[i+1]; break
      case 'blue':   gray = d[i+2]; break
      default:       gray = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2]
    }
    d[i] = d[i+1] = d[i+2] = Math.round(gray)
  }
  return imageData
}

function applyThreshold(imageData, value, mode) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const avg = (d[i] + d[i+1] + d[i+2]) / 3
    let val
    if (mode === 'binary') {
      val = avg > value ? 255 : 0
    } else {
      val = avg > value ? 0 : 255
    }
    d[i] = d[i+1] = d[i+2] = val
  }
  return imageData
}

function applyColorMask(imageData, targetR, targetG, targetB, tolerance, outputBinary) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const matchR = Math.abs(d[i] - targetR) <= tolerance
    const matchG = Math.abs(d[i+1] - targetG) <= tolerance
    const matchB = Math.abs(d[i+2] - targetB) <= tolerance
    const match = matchR && matchG && matchB
    if (outputBinary) {
      const val = match ? 255 : 0
      d[i] = d[i+1] = d[i+2] = val
    } else {
      if (!match) {
        d[i] = d[i+1] = d[i+2] = 0
      }
    }
  }
  return imageData
}

function applyInvert(imageData) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    d[i] = 255 - d[i]
    d[i+1] = 255 - d[i+1]
    d[i+2] = 255 - d[i+2]
  }
  return imageData
}

function applyMorphology(imageData, width, height, op, kernelSize) {
  const half = Math.floor(kernelSize / 2)
  const src = new Uint8ClampedArray(imageData.data)
  const d = imageData.data

  const getGray = (data, x, y) => data[(y * width + x) * 4]

  const erode = (srcData, dstData) => {
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        let min = 255
        for (let ky = -half; ky <= half; ky++) {
          for (let kx = -half; kx <= half; kx++) {
            const ny = Math.min(height - 1, Math.max(0, y + ky))
            const nx = Math.min(width - 1, Math.max(0, x + kx))
            min = Math.min(min, getGray(srcData, nx, ny))
          }
        }
        const idx = (y * width + x) * 4
        dstData[idx] = dstData[idx+1] = dstData[idx+2] = min
      }
    }
  }

  const dilate = (srcData, dstData) => {
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        let max = 0
        for (let ky = -half; ky <= half; ky++) {
          for (let kx = -half; kx <= half; kx++) {
            const ny = Math.min(height - 1, Math.max(0, y + ky))
            const nx = Math.min(width - 1, Math.max(0, x + kx))
            max = Math.max(max, getGray(srcData, nx, ny))
          }
        }
        const idx = (y * width + x) * 4
        dstData[idx] = dstData[idx+1] = dstData[idx+2] = max
      }
    }
  }

  switch (op) {
    case 'erode':
      erode(src, d)
      break
    case 'dilate':
      dilate(src, d)
      break
    case 'open': {
      // erode into d, then copy d→temp, dilate temp→d
      erode(src, d)
      const temp = new Uint8ClampedArray(d)
      dilate(temp, d)
      break
    }
    case 'close': {
      dilate(src, d)
      const temp2 = new Uint8ClampedArray(d)
      erode(temp2, d)
      break
    }
  }
  return imageData
}

function applyFilter(imageData, width, height, type, kernelSize) {
  const half = Math.floor(kernelSize / 2)
  const src = new Uint8ClampedArray(imageData.data)
  const d = imageData.data

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4
      for (let c = 0; c < 3; c++) {
        const vals = []
        let sum = 0
        let wSum = 0
        for (let ky = -half; ky <= half; ky++) {
          for (let kx = -half; kx <= half; kx++) {
            const ny = Math.min(height - 1, Math.max(0, y + ky))
            const nx = Math.min(width - 1, Math.max(0, x + kx))
            const v = src[(ny * width + nx) * 4 + c]
            vals.push(v)
            if (type === 'gaussian') {
              const w = Math.exp(-(kx*kx + ky*ky) / (2 * half * half))
              sum += v * w
              wSum += w
            } else {
              sum += v
            }
          }
        }
        if (type === 'median') {
          vals.sort((a, b) => a - b)
          d[idx + c] = vals[Math.floor(vals.length / 2)]
        } else if (type === 'gaussian') {
          d[idx + c] = Math.round(sum / wSum)
        } else {
          d[idx + c] = Math.round(sum / vals.length)
        }
      }
    }
  }
  return imageData
}

function applyEdge(imageData, width, height, type, direction) {
  const src = new Uint8ClampedArray(imageData.data)
  const d = imageData.data

  const getGray = (x, y) => {
    const cx = Math.min(width - 1, Math.max(0, x))
    const cy = Math.min(height - 1, Math.max(0, y))
    return src[(cy * width + cx) * 4]
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let val
      if (type === 'sobel') {
        const gx = -getGray(x-1,y-1) + getGray(x+1,y-1)
                  - 2*getGray(x-1,y) + 2*getGray(x+1,y)
                  - getGray(x-1,y+1) + getGray(x+1,y+1)
        const gy = -getGray(x-1,y-1) - 2*getGray(x,y-1) - getGray(x+1,y-1)
                  + getGray(x-1,y+1) + 2*getGray(x,y+1) + getGray(x+1,y+1)
        if (direction === 'x') val = Math.abs(gx)
        else if (direction === 'y') val = Math.abs(gy)
        else val = Math.sqrt(gx*gx + gy*gy)
      } else {
        // Laplacian
        val = Math.abs(
          -getGray(x,y-1) - getGray(x-1,y) + 4*getGray(x,y) - getGray(x+1,y) - getGray(x,y+1)
        )
      }
      val = Math.min(255, Math.round(val))
      const idx = (y * width + x) * 4
      d[idx] = d[idx+1] = d[idx+2] = val
    }
  }
  return imageData
}

// --- Tabs ---
const TABS = [
  { id: 'grayscale',  icon: SlidersHorizontal },
  { id: 'threshold',  icon: Scan },
  { id: 'colorMask',  icon: Pipette },
  { id: 'invert',     icon: FlipHorizontal },
  { id: 'morphology', icon: Grid3X3 },
  { id: 'filter',     icon: Droplets },
  { id: 'edge',       icon: Scan },
]

const ImageProcessLab = () => {
  const { t } = useTranslation()
  const [image, setImage] = useState(null)
  const [processedDataURL, setProcessedDataURL] = useState(null)
  const [activeTab, setActiveTab] = useState('grayscale')
  const [showHelp, setShowHelp] = useState(null)
  const [pixelated, setPixelated] = useState(false)

  // Per-panel parameters
  const [grayscaleMethod, setGrayscaleMethod] = useState('bt601')
  const [thresholdValue, setThresholdValue] = useState(80)
  const [thresholdMode, setThresholdMode] = useState('binary_inv')
  const [maskR, setMaskR] = useState(255)
  const [maskG, setMaskG] = useState(252)
  const [maskB, setMaskB] = useState(157)
  const [maskTolerance, setMaskTolerance] = useState(2)
  const [maskBinary, setMaskBinary] = useState(false)
  const [morphOp, setMorphOp] = useState('erode')
  const [morphKernel, setMorphKernel] = useState(3)
  const [filterType, setFilterType] = useState('gaussian')
  const [filterKernel, setFilterKernel] = useState(3)
  const [edgeType, setEdgeType] = useState('sobel')
  const [edgeDir, setEdgeDir] = useState('both')

  const canvasRef = useRef(null)
  const fileInputRef = useRef(null)

  const getProcessedImageData = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const ctx = canvas.getContext('2d')

    // If we have a processed image, draw it; otherwise draw the original
    const src = processedDataURL || image?.src
    if (!src) return null

    return new Promise(resolve => {
      const img = new Image()
      img.onload = () => {
        canvas.width = img.width
        canvas.height = img.height
        ctx.drawImage(img, 0, 0)
        resolve(ctx.getImageData(0, 0, canvas.width, canvas.height))
      }
      img.src = src
    })
  }, [processedDataURL, image])

  const commitImageData = useCallback((imageData) => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.width = imageData.width
    canvas.height = imageData.height
    const ctx = canvas.getContext('2d')
    ctx.putImageData(imageData, 0, 0)
    setProcessedDataURL(canvas.toDataURL())
  }, [])

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (event) => {
      const img = new Image()
      img.onload = () => {
        setImage(img)
        setProcessedDataURL(null)
      }
      img.src = event.target.result
    }
    reader.readAsDataURL(file)
  }

  const handleApply = async () => {
    const data = await getProcessedImageData()
    if (!data) return
    const { width, height } = data

    switch (activeTab) {
      case 'grayscale':  applyGrayscale(data, grayscaleMethod); break
      case 'threshold':  applyThreshold(data, thresholdValue, thresholdMode); break
      case 'colorMask':  applyColorMask(data, maskR, maskG, maskB, maskTolerance, maskBinary); break
      case 'invert':     applyInvert(data); break
      case 'morphology': applyMorphology(data, width, height, morphOp, morphKernel); break
      case 'filter':     applyFilter(data, width, height, filterType, filterKernel); break
      case 'edge':       applyEdge(data, width, height, edgeType, edgeDir); break
    }
    commitImageData(data)
  }

  const handleReset = () => setProcessedDataURL(null)

  const handleDownload = () => {
    const src = processedDataURL || image?.src
    if (!src) return
    const a = document.createElement('a')
    a.href = src
    a.download = 'processed.png'
    a.click()
  }

  const displaySrc = processedDataURL || image?.src

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-cyan-400">{t('imageProcessLab.title')}</h1>
        <p className="text-gray-400 mb-6">{t('imageProcessLab.subtitle')}</p>

        {/* Rendering toggle */}
        {image && (
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setPixelated(p => !p)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pixelated
                  ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-600/40'
                  : 'bg-gray-800 text-gray-400 border border-gray-700 hover:text-gray-200'
              }`}
            >
              <Grid2X2 className="w-4 h-4" />
              {t('imageProcessLab.pixelated')}
            </button>
          </div>
        )}

        {/* Image panels */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Original */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">{t('imageProcessLab.originalImage')}</h2>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageUpload}
              accept="image/*"
              className="hidden"
            />
            {image ? (
              <img src={image.src} alt="Original" className="w-full border border-gray-700 rounded" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
            ) : (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full h-64 border-2 border-dashed border-gray-600 rounded-lg flex flex-col items-center justify-center gap-3 hover:border-cyan-500 transition-colors"
              >
                <Upload className="w-10 h-10 text-gray-500" />
                <span className="text-gray-400">{t('imageProcessLab.uploadImage')}</span>
              </button>
            )}
            {image && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-3 w-full bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg flex items-center justify-center gap-2 text-sm"
              >
                <Upload className="w-4 h-4" />
                {t('imageProcessLab.changeImage')}
              </button>
            )}
          </div>

          {/* Processed */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">{t('imageProcessLab.processedImage')}</h2>
            {displaySrc ? (
              <img src={displaySrc} alt="Processed" className="w-full border border-gray-700 rounded" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
            ) : (
              <div className="w-full h-64 border-2 border-dashed border-gray-600 rounded-lg flex items-center justify-center">
                <span className="text-gray-500">{t('imageProcessLab.noImage')}</span>
              </div>
            )}
            <div className="flex gap-3 mt-3">
              <button
                onClick={handleReset}
                disabled={!processedDataURL}
                className="flex-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2 rounded-lg flex items-center justify-center gap-2 text-sm"
              >
                <RotateCcw className="w-4 h-4" />
                {t('imageProcessLab.reset')}
              </button>
              <button
                onClick={handleDownload}
                disabled={!displaySrc}
                className="flex-1 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2 rounded-lg flex items-center justify-center gap-2 text-sm"
              >
                <Download className="w-4 h-4" />
                {t('imageProcessLab.download')}
              </button>
            </div>
          </div>
        </div>

        {/* Operation tabs */}
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex flex-wrap gap-2 mb-6">
            {TABS.map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-cyan-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {t(`imageProcessLab.tabs.${tab.id}`)}
                </button>
              )
            })}
          </div>

          {/* Panel content */}
          <div className="border border-gray-700 rounded-lg p-4 mb-4">
            {/* Help toggle */}
            <div className="flex justify-end mb-3">
              <button
                onClick={() => setShowHelp(showHelp === activeTab ? null : activeTab)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  showHelp === activeTab
                    ? 'bg-cyan-600/20 text-cyan-400'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <HelpCircle className="w-4 h-4" />
                {t('imageProcessLab.help')}
              </button>
            </div>

            {/* Collapsible help box */}
            {showHelp === activeTab && (
              <div className="mb-4 p-3 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-300 whitespace-pre-line">
                {t(`imageProcessLab.helpContent.${activeTab}`)}
              </div>
            )}

            {activeTab === 'grayscale' && (
              <div className="space-y-3">
                <label className="block text-sm font-medium mb-1">{t('imageProcessLab.grayscale.method')}</label>
                <select
                  value={grayscaleMethod}
                  onChange={e => setGrayscaleMethod(e.target.value)}
                  className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                >
                  <option value="bt601">BT.601 (0.299R + 0.587G + 0.114B)</option>
                  <option value="bt709">BT.709 (0.2126R + 0.7152G + 0.0722B)</option>
                  <option value="equal">Equal (avg)</option>
                  <option value="red">Red channel</option>
                  <option value="green">Green channel</option>
                  <option value="blue">Blue channel</option>
                </select>
              </div>
            )}

            {activeTab === 'threshold' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {t('imageProcessLab.threshold.value')}: {thresholdValue}
                  </label>
                  <input
                    type="range" min="0" max="255" step="1"
                    value={thresholdValue}
                    onChange={e => setThresholdValue(parseInt(e.target.value))}
                    className="w-full max-w-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.threshold.mode')}</label>
                  <select
                    value={thresholdMode}
                    onChange={e => setThresholdMode(e.target.value)}
                    className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                  >
                    <option value="binary">BINARY (&gt; T → 255, else 0)</option>
                    <option value="binary_inv">BINARY_INV (&gt; T → 0, else 255)</option>
                  </select>
                </div>
              </div>
            )}

            {activeTab === 'colorMask' && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-4">
                  {[
                    ['R', maskR, setMaskR],
                    ['G', maskG, setMaskG],
                    ['B', maskB, setMaskB],
                  ].map(([label, val, setter]) => (
                    <div key={label}>
                      <label className="block text-sm font-medium mb-1">{label}</label>
                      <input
                        type="number" min="0" max="255"
                        value={val}
                        onChange={e => setter(Math.min(255, Math.max(0, parseInt(e.target.value) || 0)))}
                        className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                      />
                    </div>
                  ))}
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('imageProcessLab.colorMask.preview')}</label>
                    <div
                      className="w-20 h-8 rounded border border-gray-600"
                      style={{ backgroundColor: `rgb(${maskR},${maskG},${maskB})` }}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {t('imageProcessLab.colorMask.tolerance')}: {maskTolerance}
                  </label>
                  <input
                    type="range" min="0" max="100" step="1"
                    value={maskTolerance}
                    onChange={e => setMaskTolerance(parseInt(e.target.value))}
                    className="w-full max-w-md"
                  />
                </div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={maskBinary}
                    onChange={e => setMaskBinary(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('imageProcessLab.colorMask.binaryOutput')}</span>
                </label>
              </div>
            )}

            {activeTab === 'invert' && (
              <p className="text-sm text-gray-400">{t('imageProcessLab.invert.description')}</p>
            )}

            {activeTab === 'morphology' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.morphology.operation')}</label>
                  <select
                    value={morphOp}
                    onChange={e => setMorphOp(e.target.value)}
                    className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                  >
                    <option value="erode">Erode</option>
                    <option value="dilate">Dilate</option>
                    <option value="open">Open (erode → dilate)</option>
                    <option value="close">Close (dilate → erode)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {t('imageProcessLab.morphology.kernelSize')}: {morphKernel}
                  </label>
                  <input
                    type="range" min="3" max="9" step="2"
                    value={morphKernel}
                    onChange={e => setMorphKernel(parseInt(e.target.value))}
                    className="w-full max-w-md"
                  />
                </div>
              </div>
            )}

            {activeTab === 'filter' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.filter.type')}</label>
                  <select
                    value={filterType}
                    onChange={e => setFilterType(e.target.value)}
                    className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                  >
                    <option value="gaussian">Gaussian</option>
                    <option value="median">Median</option>
                    <option value="box">Box (Mean)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {t('imageProcessLab.filter.kernelSize')}: {filterKernel}
                  </label>
                  <input
                    type="range" min="3" max="11" step="2"
                    value={filterKernel}
                    onChange={e => setFilterKernel(parseInt(e.target.value))}
                    className="w-full max-w-md"
                  />
                </div>
              </div>
            )}

            {activeTab === 'edge' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.edge.type')}</label>
                  <select
                    value={edgeType}
                    onChange={e => setEdgeType(e.target.value)}
                    className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                  >
                    <option value="sobel">Sobel</option>
                    <option value="laplacian">Laplacian</option>
                  </select>
                </div>
                {edgeType === 'sobel' && (
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('imageProcessLab.edge.direction')}</label>
                    <select
                      value={edgeDir}
                      onChange={e => setEdgeDir(e.target.value)}
                      className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                    >
                      <option value="both">Both (X + Y)</option>
                      <option value="x">X (horizontal edges)</option>
                      <option value="y">Y (vertical edges)</option>
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>

          <button
            onClick={handleApply}
            disabled={!image}
            className="bg-cyan-600 hover:bg-cyan-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-medium"
          >
            {t('imageProcessLab.apply')}
          </button>
        </div>

        {/* Hidden work canvas */}
        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  )
}

export default ImageProcessLab
