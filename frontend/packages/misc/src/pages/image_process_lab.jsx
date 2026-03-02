import { useState, useRef, useCallback } from 'react'
import { Upload, Download, RotateCcw, FlipHorizontal, SlidersHorizontal, Droplets, Grid3X3, Scan, Pipette, HelpCircle, Grid2X2, Palette, Search } from 'lucide-react'
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

function applyColorMask(imageData, targetR, targetG, targetB, tolR, tolG, tolB, outputBinary) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const matchR = Math.abs(d[i] - targetR) <= tolR
    const matchG = Math.abs(d[i+1] - targetG) <= tolG
    const matchB = Math.abs(d[i+2] - targetB) <= tolB
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

function rgbToHue(r, g, b) {
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  if (max === min) return 0
  const d = max - min
  let h
  if (max === r) h = 60 * (((g - b) / d) % 6)
  else if (max === g) h = 60 * ((b - r) / d + 2)
  else h = 60 * ((r - g) / d + 4)
  if (h < 0) h += 360
  return h
}

function applyHueRejection(imageData, hueMin, hueMax, mode, satMin) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i+1], b = d[i+2]
    const max = Math.max(r, g, b)
    const min = Math.min(r, g, b)
    const sat = max === 0 ? 0 : (max - min) / max

    // Skip low-saturation pixels (gray/white/black)
    if (sat < satMin / 100) continue

    const hue = rgbToHue(r, g, b)

    let inRange
    if (hueMin <= hueMax) {
      inRange = hue >= hueMin && hue <= hueMax
    } else {
      // Wraps around 360 (e.g., red: 330→30)
      inRange = hue >= hueMin || hue <= hueMax
    }

    if (mode === 'reject') {
      if (inRange) d[i] = d[i+1] = d[i+2] = 0
    } else {
      if (!inRange) d[i] = d[i+1] = d[i+2] = 0
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

// --- Prefix detection (Mabinogi-specific) ---

const EFFECT_BLUE = { r: 74, g: 149, b: 238 }
const EFFECT_RED = { r: 255, g: 103, b: 103 }
const EFFECT_GREY = { r: 128, g: 128, b: 128 }
const TEXT_WHITE = { r: 255, g: 255, b: 255 }
function _buildColorMask(data, w, h, color, tolerance) {
  const mask = new Uint8Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      if (Math.abs(data[i] - color.r) <= tolerance &&
          Math.abs(data[i+1] - color.g) <= tolerance &&
          Math.abs(data[i+2] - color.b) <= tolerance) {
        mask[y * w + x] = 1
      }
    }
  }
  return mask
}

function _detectLines(mask, w, h) {
  // Line detection via horizontal projection on color mask
  const rowProj = new Uint32Array(h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) rowProj[y] += mask[y * w + x]
  }
  const threshold = Math.max(3, w * 0.01)
  const hasText = new Uint8Array(h)
  for (let y = 0; y < h; y++) hasText[y] = rowProj[y] > threshold ? 1 : 0
  // Bridge gaps of ≤2 rows within a text line (thin stroke dips)
  for (let y = 1; y < h;) {
    if (!hasText[y] && hasText[y - 1]) {
      const gs = y
      while (y < h && !hasText[y]) y++
      if (y - gs <= 2 && y < h && hasText[y]) {
        for (let g = gs; g < y; g++) hasText[g] = 1
      }
    } else { y++ }
  }

  // Collect raw blocks (no height cap — split tall blocks below)
  const blocks = []
  let inLine = false, lineStart = 0
  for (let y = 0; y <= h; y++) {
    const t = y < h && hasText[y]
    if (t && !inLine) { lineStart = y; inLine = true }
    else if (!t && inLine) {
      const lh = y - lineStart
      if (lh >= 6) blocks.push({ y: lineStart, h: lh })
      inLine = false
    }
  }

  // Split tall blocks at internal zero-projection rows
  const splitBlocks = []
  for (const blk of blocks) {
    if (blk.h <= 30) {
      splitBlocks.push(blk)
      continue
    }
    // Find split points: rows with zero projection within the block
    let subStart = blk.y
    for (let y = blk.y; y < blk.y + blk.h; y++) {
      if (rowProj[y] <= threshold) {
        const subH = y - subStart
        if (subH >= 6) splitBlocks.push({ y: subStart, h: subH })
        subStart = y + 1
      }
    }
    const lastH = blk.y + blk.h - subStart
    if (lastH >= 6) splitBlocks.push({ y: subStart, h: lastH })
  }

  // Compute x bounds for each line
  const lines = []
  for (const blk of splitBlocks) {
    let xStart = -1, xEnd = -1
    for (let ly = blk.y; ly < blk.y + blk.h; ly++) {
      for (let x = 0; x < w; x++) {
        if (mask[ly * w + x]) {
          if (xStart < 0 || x < xStart) xStart = x
          if (x + 1 > xEnd) xEnd = x + 1
        }
      }
    }
    if (xStart >= 0 && xEnd - xStart >= 6) {
      lines.push({ x: xStart, y: blk.y, w: xEnd - xStart, h: blk.h })
    }
  }
  return lines
}

function detectPrefixesWithConfig(imageData, config, tolerance) {
  const { data, width: w, height: h } = imageData
  const mask = _buildConfigMask(data, w, h, config, tolerance)
  const lines = _detectLines(mask, w, h)
  return _detectPrefixesShapeWalker(lines, mask, w, h, config.shapes, config.name)
    .filter(r => r.prefix?.type === config.name)
}

function drawPrefixVisualization(imageData, detections) {
  const { data, width: w } = imageData

  const drawBox = (bx, by, bw, bh, r, g, b) => {
    for (let t = 0; t < 1; t++) {
      for (let px = bx; px < bx + bw && px < w; px++) {
        for (const py of [by + t, by + bh - 1 - t]) {
          if (py >= 0 && py < imageData.height && px >= 0) {
            const i = (py * w + px) * 4
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = 255
          }
        }
      }
      for (let py = by; py < by + bh && py < imageData.height; py++) {
        for (const px of [bx + t, bx + bw - 1 - t]) {
          if (px >= 0 && px < w && py >= 0) {
            const i = (py * w + px) * 4
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = 255
          }
        }
      }
    }
  }

  for (const det of detections) {
    if (det.prefix) {
      // Prefix box: red for bullet, orange for subbullet
      const isSubbullet = det.prefix.type === 'subbullet'
      drawBox(det.prefix.x, det.prefix.y, det.prefix.w, det.prefix.h,
        isSubbullet ? 255 : 255, isSubbullet ? 160 : 60, 60)
      // Main text box: cyan for blue lines, green for white lines
      const mainW = det.line.x + det.line.w - det.mainX
      const isWhite = det.color === 'white'
      drawBox(det.mainX, det.line.y, mainW, det.line.h,
        isWhite ? 60 : 60, isWhite ? 200 : 200, isWhite ? 200 : 60)
    } else {
      drawBox(det.line.x, det.line.y, det.line.w, det.line.h, 200, 200, 60)
    }
  }
  return imageData
}

// --- Shape Walker (directional shape detection) ---
// JS port of backend/lib/shape_walker.py — classifies prefix marks by tracing
// ink pixels in directional segments (DOWN→RIGHT for ㄴ, flood fill for ·).

const SW_DELTAS = { down: [1, 0], right: [0, 1], up: [-1, 0], left: [0, -1] }
const SW_PERP = { down: [0, 1], right: [1, 0], up: [0, 1], left: [1, 0] }
const SW_NIEUN = { name: 'ㄴ', segments: [{ dir: 'down', min: 3 }, { dir: 'right', min: 3 }] }
const SW_DOT = { name: '·', segments: [{ dir: 'dot', min: 1, max: 4 }] }

// Config-driven detector definitions — mirrors backend PrefixDetectorConfig
const BULLET_DETECTOR = { name: 'bullet', colors: [EFFECT_BLUE, EFFECT_RED, EFFECT_GREY], shapes: [SW_DOT] }
const SUBBULLET_DETECTOR = { name: 'subbullet', colors: [TEXT_WHITE, EFFECT_RED], shapes: [SW_NIEUN] }

function _buildConfigMask(data, w, h, config, tolerance) {
  const mask = new Uint8Array(w * h)
  for (const color of config.colors) {
    const m = _buildColorMask(data, w, h, color, tolerance)
    for (let i = 0; i < mask.length; i++) if (m[i]) mask[i] = 1
  }
  return mask
}

function _swFindSeeds(mask, w, h) {
  let leftCol = -1
  for (let c = 0; c < w && leftCol < 0; c++) {
    for (let r = 0; r < h; r++) {
      if (mask[r * w + c] > 0) { leftCol = c; break }
    }
  }
  if (leftCol < 0) return []
  const seeds = []
  let inRun = false
  for (let r = 0; r < h; r++) {
    if (mask[r * w + leftCol] > 0) {
      if (!inRun) { seeds.push([r, leftCol]); inRun = true }
    } else { inRun = false }
  }
  return seeds
}

function _swStrokeWidth(mask, w, h, row, col, dir) {
  const [pr, pc] = SW_PERP[dir]
  let width = 1
  for (const sign of [1, -1]) {
    for (let step = 1; ; step++) {
      const nr = row + pr * sign * step, nc = col + pc * sign * step
      if (nr >= 0 && nr < h && nc >= 0 && nc < w && mask[nr * w + nc] > 0) width++
      else break
    }
  }
  return width
}

function _swWalkSegment(mask, w, h, row, col, dir, minPx, maxPx) {
  const [dr, dc] = SW_DELTAS[dir]
  const [pr, pc] = SW_PERP[dir]
  const halfW = Math.floor(_swStrokeWidth(mask, w, h, row, col, dir) / 2)
  let cr = row, cc = col, length = 0
  while (true) {
    const nr = cr + dr, nc = cc + dc
    if (nr < 0 || nr >= h || nc < 0 || nc >= w) break
    let bandHasInk = false
    for (let off = -halfW; off <= halfW; off++) {
      const br = nr + pr * off, bc = nc + pc * off
      if (br >= 0 && br < h && bc >= 0 && bc < w && mask[br * w + bc] > 0) { bandHasInk = true; break }
    }
    if (!bandHasInk) break
    cr = nr; cc = nc; length++
    if (maxPx != null && length >= maxPx) break
  }
  return length < minPx ? null : { row: cr, col: cc, length }
}

function _swCheckDot(mask, w, h, row, col, minPx, maxPx) {
  if (mask[row * w + col] === 0) return null
  const visited = new Set([row * w + col])
  const queue = [[row, col]]
  let minR = row, minC = col, maxR = row, maxC = col
  while (queue.length > 0) {
    const [r, c] = queue.shift()
    minR = Math.min(minR, r); minC = Math.min(minC, c)
    maxR = Math.max(maxR, r); maxC = Math.max(maxC, c)
    for (const [dr, dc] of [[0,1],[0,-1],[1,0],[-1,0]]) {
      const nr = r + dr, nc = c + dc, key = nr * w + nc
      if (nr >= 0 && nr < h && nc >= 0 && nc < w && !visited.has(key) && mask[key] > 0) {
        visited.add(key); queue.push([nr, nc])
      }
    }
  }
  const extMax = Math.max(maxR - minR + 1, maxC - minC + 1)
  if (extMax < minPx || (maxPx != null && extMax > maxPx)) return null
  return { name: '·' }
}

function _swTryShape(mask, w, h, seed, shapeDef) {
  let [row, col] = seed
  if (mask[row * w + col] === 0) return null
  for (let i = 0; i < shapeDef.segments.length; i++) {
    const seg = shapeDef.segments[i]
    if (seg.dir === 'dot') {
      return _swCheckDot(mask, w, h, row, col, seg.min, seg.max) ? { name: shapeDef.name } : null
    }
    const result = _swWalkSegment(mask, w, h, row, col, seg.dir, seg.min, seg.max)
    if (!result) return null
    if (i < shapeDef.segments.length - 1) {
      const nextSeg = shapeDef.segments[i + 1]
      if (nextSeg.dir === 'dot') { row = result.row; col = result.col; continue }
      const [ndr, ndc] = SW_DELTAS[nextSeg.dir]
      const tol = Math.max(1, Math.floor(_swStrokeWidth(mask, w, h, seed[0], seed[1], seg.dir) / 2))
      const [pr, pc] = SW_PERP[nextSeg.dir]
      let found = null
      for (let off = -tol; off <= tol && !found; off++) {
        const sr = result.row + ndr + pr * off, sc = result.col + ndc + pc * off
        if (sr >= 0 && sr < h && sc >= 0 && sc < w && mask[sr * w + sc] > 0) found = [sr, sc]
      }
      if (!found) {
        const sr = result.row + ndr, sc = result.col + ndc
        if (sr >= 0 && sr < h && sc >= 0 && sc < w && mask[sr * w + sc] > 0) found = [sr, sc]
      }
      if (!found) return null
      row = found[0]; col = found[1]
    }
  }
  return { name: shapeDef.name }
}

function _swClassifyCluster(mask, w, h, shapes) {
  const seeds = _swFindSeeds(mask, w, h)
  for (const seed of seeds) {
    for (const shape of shapes) {
      const match = _swTryShape(mask, w, h, seed, shape)
      if (match) return match
    }
  }
  return null
}

function _detectPrefixesShapeWalker(lines, prefixMask, w, h, shapes = [SW_NIEUN, SW_DOT], configName = null) {
  const results = []
  for (const line of lines) {
    const padX = Math.max(2, Math.floor(line.h / 3))
    const padY = Math.max(1, Math.floor(line.h / 5))
    const y0 = Math.max(0, line.y - padY)
    const y1 = Math.min(h, line.y + line.h + padY)
    const x0 = Math.max(0, line.x - padX)
    const x1 = Math.min(w, line.x + line.w + padX)
    const regionW = x1 - x0
    const lineH = y1 - y0

    const colProj = new Uint32Array(regionW)
    for (let ly = y0; ly < y1; ly++) {
      for (let lx = 0; lx < regionW; lx++) colProj[lx] += prefixMask[ly * w + (x0 + lx)]
    }
    let firstStart = -1, firstEnd = -1, mainStart = -1
    for (let x = 0; x < regionW; x++) {
      const hasInk = colProj[x] > 0
      if (firstStart < 0) { if (hasInk) firstStart = x }
      else if (firstEnd < 0) { if (!hasInk) firstEnd = x }
      else if (mainStart < 0) { if (hasInk) { mainStart = x; break } }
    }

    if (firstStart >= 0 && firstEnd >= 0 && mainStart >= 0) {
      const firstW = firstEnd - firstStart
      const gapW = mainStart - firstEnd
      const maxPrefixW = Math.max(8, Math.floor(lineH * 0.7))
      const minGap = Math.max(2, Math.floor(lineH * 0.2))
      if (firstW <= maxPrefixW && gapW >= minGap) {
        const clW = firstW, clH = lineH
        const clMask = new Uint8Array(clW * clH)
        for (let r = 0; r < clH; r++) {
          for (let c = 0; c < clW; c++) clMask[r * clW + c] = prefixMask[(y0 + r) * w + (x0 + firstStart + c)]
        }
        const match = _swClassifyCluster(clMask, clW, clH, shapes)
        if (match) {
          const prefixType = configName || (match.name === 'ㄴ' ? 'subbullet' : 'bullet')
          results.push({
            color: prefixType,
            line: { x: x0, y: y0, w: regionW, h: lineH },
            prefix: { type: prefixType, x: x0 + firstStart, y: y0, w: firstW, h: lineH },
            mainX: x0 + mainStart,
          })
          continue
        }
      }
    }
    results.push({ color: 'none', line: { x: x0, y: y0, w: regionW, h: lineH }, prefix: null, mainX: x0 })
  }
  return results
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
  { id: 'hueReject',  icon: Palette },
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
  const [maskTolR, setMaskTolR] = useState(2)
  const [maskTolG, setMaskTolG] = useState(2)
  const [maskTolB, setMaskTolB] = useState(2)
  const [maskPerChannel, setMaskPerChannel] = useState(false)
  const [maskBinary, setMaskBinary] = useState(false)
  const [morphOp, setMorphOp] = useState('erode')
  const [morphKernel, setMorphKernel] = useState(3)
  const [filterType, setFilterType] = useState('gaussian')
  const [filterKernel, setFilterKernel] = useState(3)
  const [edgeType, setEdgeType] = useState('sobel')
  const [edgeDir, setEdgeDir] = useState('both')
  const [hueMin, setHueMin] = useState(210)
  const [hueMax, setHueMax] = useState(330)
  const [hueMode, setHueMode] = useState('reject')
  const [hueSatMin, setHueSatMin] = useState(10)

  // Prefix detection
  const [bulletTol, setBulletTol] = useState(15)
  const [subbulletTol, setSubbulletTol] = useState(10)
  const [bulletResults, setBulletResults] = useState(null)
  const [subbulletResults, setSubbulletResults] = useState(null)

  // Shape walker detection
  const [shapeWalkerTol, setShapeWalkerTol] = useState(15)
  const [shapeWalkerResults, setShapeWalkerResults] = useState(null)

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

  const getOriginalImageData = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !image) return null
    canvas.width = image.naturalWidth
    canvas.height = image.naturalHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(image, 0, 0)
    return ctx.getImageData(0, 0, canvas.width, canvas.height)
  }, [image])

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
      case 'colorMask':  applyColorMask(data, maskR, maskG, maskB, maskTolR, maskTolG, maskTolB, maskBinary); break
      case 'invert':     applyInvert(data); break
      case 'morphology': applyMorphology(data, width, height, morphOp, morphKernel); break
      case 'filter':     applyFilter(data, width, height, filterType, filterKernel); break
      case 'edge':       applyEdge(data, width, height, edgeType, edgeDir); break
      case 'hueReject':  applyHueRejection(data, hueMin, hueMax, hueMode, hueSatMin); break
    }
    commitImageData(data)
  }

  const handleReset = () => { setProcessedDataURL(null); setBulletResults(null); setSubbulletResults(null); setShapeWalkerResults(null) }

  const handleDetectBullet = async () => {
    const data = await getOriginalImageData()
    if (!data) return
    const results = detectPrefixesWithConfig(data, BULLET_DETECTOR, bulletTol)
    setBulletResults(results)
    const vizData = await getProcessedImageData()
    drawPrefixVisualization(vizData, results)
    commitImageData(vizData)
  }

  const handleDetectSubbullet = async () => {
    const data = await getOriginalImageData()
    if (!data) return
    const results = detectPrefixesWithConfig(data, SUBBULLET_DETECTOR, subbulletTol)
    setSubbulletResults(results)
    const vizData = await getProcessedImageData()
    drawPrefixVisualization(vizData, results)
    commitImageData(vizData)
  }

  const handleShapeWalker = async () => {
    const data = await getOriginalImageData()
    if (!data) return
    const bulletResults = detectPrefixesWithConfig(data, BULLET_DETECTOR, shapeWalkerTol)
    const subbulletResults = detectPrefixesWithConfig(data, SUBBULLET_DETECTOR, shapeWalkerTol)
    const prefixResults = [...bulletResults, ...subbulletResults]
    setShapeWalkerResults(prefixResults)
    const vizData = await getProcessedImageData()
    drawPrefixVisualization(vizData, prefixResults)
    commitImageData(vizData)
  }

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
      <div className="max-w-[1600px] mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-cyan-400">{t('imageProcessLab.title')}</h1>
        <p className="text-gray-400 mb-6">{t('imageProcessLab.subtitle')}</p>

        <div className="flex gap-6">
          {/* Left sidebar — Mabinogi Tools (always visible) */}
          <div className="w-56 shrink-0">
            <div className="sticky top-6 bg-gray-800/60 rounded-lg p-4 border border-indigo-900/40 space-y-4">
              <h3 className="text-sm font-semibold text-indigo-300">Mabinogi Tools</h3>

              {/* Bullet (·) Detector */}
              <div className="space-y-2">
                <button
                  onClick={handleDetectBullet}
                  disabled={!image}
                  className="w-full px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium flex items-center gap-2 transition-colors"
                >
                  <Search className="w-3.5 h-3.5" />
                  Detect Bullet ·
                </button>
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Tol: {bulletTol}</label>
                  <input
                    type="range" min="5" max="40" step="1"
                    value={bulletTol}
                    onChange={e => setBulletTol(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-xs text-gray-500">blue + red</div>
                </div>
                {bulletResults && (
                  <div className="text-xs text-blue-400">{bulletResults.length} found</div>
                )}
              </div>

              <div className="border-t border-indigo-900/40" />

              {/* Subbullet (ㄴ) Detector */}
              <div className="space-y-2">
                <button
                  onClick={handleDetectSubbullet}
                  disabled={!image}
                  className="w-full px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium flex items-center gap-2 transition-colors"
                >
                  <Search className="w-3.5 h-3.5" />
                  Detect Subbullet ㄴ
                </button>
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Tol: {subbulletTol}</label>
                  <input
                    type="range" min="3" max="30" step="1"
                    value={subbulletTol}
                    onChange={e => setSubbulletTol(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-xs text-gray-500">white</div>
                </div>
                {subbulletResults && (
                  <div className="text-xs text-orange-400">{subbulletResults.length} found</div>
                )}
              </div>

              <div className="border-t border-indigo-900/40" />

              {/* Shape Walker (combined · + ㄴ via directional walk) */}
              <div className="space-y-2">
                <button
                  onClick={handleShapeWalker}
                  disabled={!image}
                  className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium flex items-center gap-2 transition-colors"
                >
                  <Search className="w-3.5 h-3.5" />
                  Shape Walker
                </button>
                <div className="space-y-1">
                  <label className="text-xs text-gray-400">Tol: {shapeWalkerTol}</label>
                  <input
                    type="range" min="5" max="40" step="1"
                    value={shapeWalkerTol}
                    onChange={e => setShapeWalkerTol(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-xs text-gray-500">all colors</div>
                </div>
                {shapeWalkerResults && (
                  <div className="text-xs space-y-0.5">
                    <div className="text-emerald-400">{shapeWalkerResults.length} found</div>
                    <div className="text-blue-400 pl-2">· {shapeWalkerResults.filter(r => r.prefix?.type === 'bullet').length}</div>
                    <div className="text-orange-400 pl-2">ㄴ {shapeWalkerResults.filter(r => r.prefix?.type === 'subbullet').length}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Main content */}
          <div className="flex-1 min-w-0">
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

            {/* Operation tabs — sticky so controls are always visible */}
        <div className="bg-gray-800 rounded-lg p-6 sticky bottom-0 z-10 shadow-[0_-4px_20px_rgba(0,0,0,0.5)] border-t border-gray-700">
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
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={maskPerChannel}
                    onChange={e => {
                      setMaskPerChannel(e.target.checked)
                      if (!e.target.checked) {
                        // Sync all to R value when switching back
                        setMaskTolG(maskTolR)
                        setMaskTolB(maskTolR)
                      }
                    }}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('imageProcessLab.colorMask.perChannel')}</span>
                </label>
                {maskPerChannel ? (
                  <div className="flex flex-wrap gap-4">
                    {[
                      ['R', maskTolR, setMaskTolR, 'text-red-400'],
                      ['G', maskTolG, setMaskTolG, 'text-green-400'],
                      ['B', maskTolB, setMaskTolB, 'text-blue-400'],
                    ].map(([label, val, setter, color]) => (
                      <div key={label} className="flex-1 min-w-[120px] max-w-[200px]">
                        <label className={`block text-sm font-medium mb-1 ${color}`}>
                          {t('imageProcessLab.colorMask.tolerance')} {label}: {val}
                        </label>
                        <input
                          type="range" min="0" max="255" step="1"
                          value={val}
                          onChange={e => setter(parseInt(e.target.value))}
                          className="w-full"
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      {t('imageProcessLab.colorMask.tolerance')}: {maskTolR}
                    </label>
                    <input
                      type="range" min="0" max="255" step="1"
                      value={maskTolR}
                      onChange={e => {
                        const v = parseInt(e.target.value)
                        setMaskTolR(v); setMaskTolG(v); setMaskTolB(v)
                      }}
                      className="w-full max-w-md"
                    />
                  </div>
                )}
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

            {activeTab === 'hueReject' && (
              <div className="space-y-3">
                {/* Hue spectrum bar */}
                <div>
                  <label className="block text-sm font-medium mb-2">{t('imageProcessLab.hueReject.range')}</label>
                  <div className="relative w-full max-w-md">
                    <div
                      className="h-6 rounded border border-gray-600"
                      style={{
                        background: 'linear-gradient(to right, hsl(0,100%,50%), hsl(60,100%,50%), hsl(120,100%,50%), hsl(180,100%,50%), hsl(240,100%,50%), hsl(300,100%,50%), hsl(360,100%,50%))'
                      }}
                    />
                    {/* Selected range overlay */}
                    {(() => {
                      const pMin = (hueMin / 360) * 100
                      const pMax = (hueMax / 360) * 100
                      if (hueMin <= hueMax) {
                        return (
                          <div
                            className="absolute top-0 h-6 border-2 border-white rounded"
                            style={{ left: `${pMin}%`, width: `${pMax - pMin}%`, background: 'rgba(0,0,0,0.4)' }}
                          />
                        )
                      } else {
                        return (
                          <>
                            <div
                              className="absolute top-0 h-6 border-l-2 border-y-2 border-white rounded-l"
                              style={{ left: `${pMin}%`, width: `${100 - pMin}%`, background: 'rgba(0,0,0,0.4)' }}
                            />
                            <div
                              className="absolute top-0 h-6 border-r-2 border-y-2 border-white rounded-r"
                              style={{ left: '0%', width: `${pMax}%`, background: 'rgba(0,0,0,0.4)' }}
                            />
                          </>
                        )
                      }
                    })()}
                    {/* Degree labels */}
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>0</span><span>60</span><span>120</span><span>180</span><span>240</span><span>300</span><span>360</span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('imageProcessLab.hueReject.hueMin')}</label>
                    <input
                      type="number" min="0" max="360"
                      value={hueMin}
                      onChange={e => setHueMin(Math.min(360, Math.max(0, parseInt(e.target.value) || 0)))}
                      className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('imageProcessLab.hueReject.hueMax')}</label>
                    <input
                      type="number" min="0" max="360"
                      value={hueMax}
                      onChange={e => setHueMax(Math.min(360, Math.max(0, parseInt(e.target.value) || 0)))}
                      className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      OpenCV
                    </label>
                    <span className="text-xs text-gray-400">{Math.round(hueMin / 2)}–{Math.round(hueMax / 2)}</span>
                  </div>
                </div>
                {/* Presets */}
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.hueReject.presets')}</label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: 'Blue+AA (210-330)', min: 210, max: 330, color: 'bg-blue-600' },
                      { label: 'Blue only (210-270)', min: 210, max: 270, color: 'bg-blue-500' },
                      { label: 'Red (330-30)', min: 330, max: 30, color: 'bg-red-500' },
                      { label: 'Green (90-150)', min: 90, max: 150, color: 'bg-green-500' },
                      { label: 'Yellow (30-90)', min: 30, max: 90, color: 'bg-yellow-500' },
                    ].map(p => (
                      <button
                        key={p.label}
                        onClick={() => { setHueMin(p.min); setHueMax(p.max) }}
                        className={`px-2 py-1 rounded text-xs font-medium text-white ${p.color} hover:opacity-80 transition-opacity`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    {t('imageProcessLab.hueReject.satMin')}: {hueSatMin}%
                  </label>
                  <input
                    type="range" min="0" max="100" step="1"
                    value={hueSatMin}
                    onChange={e => setHueSatMin(parseInt(e.target.value))}
                    className="w-full max-w-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">{t('imageProcessLab.hueReject.mode')}</label>
                  <select
                    value={hueMode}
                    onChange={e => setHueMode(e.target.value)}
                    className="w-full max-w-xs bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                  >
                    <option value="reject">{t('imageProcessLab.hueReject.modeReject')}</option>
                    <option value="isolate">{t('imageProcessLab.hueReject.modeIsolate')}</option>
                  </select>
                </div>
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
          </div>{/* /main content */}
        </div>{/* /flex */}

        {/* Hidden work canvas */}
        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  )
}

export default ImageProcessLab
