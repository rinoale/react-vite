import { useState, useRef, useEffect, useCallback } from 'react'
import { Upload, Play, Pause, SkipBack, SkipForward, ChevronLeft, ChevronRight, HelpCircle, Grid2X2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

// ─── Image processing helpers (mirror the Python V3 pipeline) ───

function getPixel(data, w, x, y) {
  const i = (y * w + x) * 4
  return [data[i], data[i+1], data[i+2], data[i+3]]
}

function cloneImageData(ctx, src) {
  const dst = ctx.createImageData(src.width, src.height)
  dst.data.set(src.data)
  return dst
}

function imageDataToCanvas(imageData) {
  const c = document.createElement('canvas')
  c.width = imageData.width
  c.height = imageData.height
  c.getContext('2d').putImageData(imageData, 0, 0)
  return c
}

function canvasToDataURL(imageData) {
  return imageDataToCanvas(imageData).toDataURL()
}

function cropImageData(ctx, src, x, y, w, h) {
  const c = imageDataToCanvas(src)
  const c2 = document.createElement('canvas')
  c2.width = w
  c2.height = h
  c2.getContext('2d').drawImage(c, x, y, w, h, 0, 0, w, h)
  return c2.getContext('2d').getImageData(0, 0, w, h)
}

function drawRect(imageData, x, y, w, h, r, g, b, lineWidth = 2) {
  const d = imageData.data
  const iw = imageData.width
  const ih = imageData.height
  for (let t = 0; t < lineWidth; t++) {
    for (let px = x; px < x + w && px < iw; px++) {
      for (const py of [y + t, y + h - 1 - t]) {
        if (py >= 0 && py < ih && px >= 0) {
          const i = (py * iw + px) * 4
          d[i] = r; d[i+1] = g; d[i+2] = b; d[i+3] = 255
        }
      }
    }
    for (let py = y; py < y + h && py < ih; py++) {
      for (const px of [x + t, x + w - 1 - t]) {
        if (px >= 0 && px < iw && py >= 0) {
          const i = (py * iw + px) * 4
          d[i] = r; d[i+1] = g; d[i+2] = b; d[i+3] = 255
        }
      }
    }
  }
}

// ─── Step 1: Border detection ───

function detectBorders(imageData) {
  const { data, width: w, height: h } = imageData
  const lo = 127, hi = 137 // 132 ± 5
  const minDensity = 0.3

  // Build border mask per pixel
  const isBorder = new Uint8Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      if (data[i] >= lo && data[i] <= hi &&
          data[i+1] >= lo && data[i+1] <= hi &&
          data[i+2] >= lo && data[i+2] <= hi) {
        isBorder[y * w + x] = 1
      }
    }
  }

  // Bottom border: scan from bottom
  let bottomY = null
  const rowThresh = Math.floor(w * minDensity)
  for (let y = h - 1; y >= 0; y--) {
    let count = 0
    for (let x = 0; x < w; x++) if (isBorder[y * w + x]) count++
    if (count >= rowThresh) { bottomY = y; break }
  }

  // Vertical borders: column sums
  const colThresh = Math.floor(h * minDensity)
  let leftX = null, rightX = null
  for (let x = 0; x < w; x++) {
    let count = 0
    for (let y = 0; y < h; y++) if (isBorder[y * w + x]) count++
    if (count >= colThresh) { leftX = x; break }
  }
  for (let x = w - 1; x >= 0; x--) {
    let count = 0
    for (let y = 0; y < h; y++) if (isBorder[y * w + x]) count++
    if (count >= colThresh) { rightX = x; break }
  }

  return { bottomY, leftX, rightX }
}

// ─── Step 2: Orange header detection ───

function detectOrangeHeaders(imageData) {
  const { data, width: w, height: h } = imageData
  // Orange mask
  const orangeMask = new Uint8Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      const r = data[i], g = data[i+1], b = data[i+2]
      if (r > 150 && g > 50 && g < 180 && b < 80) {
        orangeMask[y * w + x] = 1
      }
    }
  }

  // Horizontal projection
  const rowCounts = new Uint32Array(h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      rowCounts[y] += orangeMask[y * w + x]
    }
  }

  // Find bands
  const minBandH = 8, minBandPx = 40
  const bands = []
  let inBand = false, bandStart = 0, bandPx = 0
  for (let y = 0; y < h; y++) {
    if (rowCounts[y] > 0) {
      if (!inBand) { bandStart = y; bandPx = 0; inBand = true }
      bandPx += rowCounts[y]
    } else if (inBand) {
      const bandH = y - bandStart
      if (bandH >= minBandH && bandPx >= minBandPx) {
        bands.push({ y: bandStart, h: bandH })
      }
      inBand = false
    }
  }
  if (inBand) {
    const bandH = h - bandStart
    if (bandH >= minBandH && bandPx >= minBandPx) {
      bands.push({ y: bandStart, h: bandH })
    }
  }

  return { orangeMask, bands }
}

// ─── Step 3: Grayscale BT.601 ───

function toGrayscale(imageData) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const gray = Math.round(0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2])
    d[i] = d[i+1] = d[i+2] = gray
  }
  return imageData
}

// ─── Step 4: Threshold BINARY_INV ───

function thresholdBinaryInv(imageData, thresh) {
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const val = d[i] > thresh ? 0 : 255
    d[i] = d[i+1] = d[i+2] = val
  }
  return imageData
}

// ─── Step 5: Line detection (horizontal projection) ───

function detectLines(binaryData, minHeight = 6, maxHeight = 25, minWidth = 10) {
  const { width: w, height: h } = binaryData
  const d = binaryData.data

  // Build binary array (1 = ink/white pixel on inverted image i.e. text)
  // binaryData is black-text-on-white (BINARY_INV), invert for detection
  const ink = new Uint8Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      // After BINARY_INV: text=0 (black), bg=255 (white)
      // For detection we want text=1
      if (d[(y * w + x) * 4] === 0) ink[y * w + x] = 1
    }
  }

  // Border removal: find columns with >60% density, mask narrow runs (<=3px)
  const colDensity = new Float32Array(w)
  for (let x = 0; x < w; x++) {
    let count = 0
    for (let y = 0; y < h; y++) count += ink[y * w + x]
    colDensity[x] = count / h
  }
  const cleaned = new Uint8Array(ink)
  let inRun = false, runStart = 0
  for (let x = 0; x <= w; x++) {
    const dense = x < w && colDensity[x] > 0.6
    if (dense && !inRun) { runStart = x; inRun = true }
    else if (!dense && inRun) {
      if (x - runStart <= 3) {
        for (let y = 0; y < h; y++)
          for (let cx = runStart; cx < x; cx++)
            cleaned[y * w + cx] = 0
      }
      inRun = false
    }
  }

  // Horizontal projection on cleaned
  const projection = new Uint32Array(h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) projection[y] += cleaned[y * w + x]
  }

  const threshold = Math.max(3, w * 0.015)
  const hasText = new Uint8Array(h)
  for (let y = 0; y < h; y++) hasText[y] = projection[y] > threshold ? 1 : 0

  // Gap closure (tolerance=2)
  for (let y = 1; y < h; ) {
    if (!hasText[y] && hasText[y - 1]) {
      const gs = y
      while (y < h && !hasText[y]) y++
      if (y - gs <= 2 && y < h && hasText[y]) {
        for (let g = gs; g < y; g++) hasText[g] = 1
      }
    } else { y++ }
  }

  // Find contiguous text runs
  const lines = []
  let inLine = false, lineStart = 0
  for (let y = 0; y <= h; y++) {
    const t = y < h && hasText[y]
    if (t && !inLine) { lineStart = y; inLine = true }
    else if (!t && inLine) {
      const lineH = y - lineStart
      if (lineH >= minHeight && lineH <= maxHeight) {
        // Compute horizontal extent
        const rowSlice = ink.subarray(lineStart * w, y * w)
        const colProj = new Uint32Array(w)
        for (let ly = 0; ly < y - lineStart; ly++) {
          for (let x = 0; x < w; x++) {
            colProj[x] += rowSlice[ly * w + x]
          }
        }
        let xStart = -1, xEnd = -1
        for (let x = 0; x < w; x++) if (colProj[x] > 0) { xStart = x; break }
        for (let x = w - 1; x >= 0; x--) if (colProj[x] > 0) { xEnd = x + 1; break }
        if (xStart >= 0 && xEnd - xStart >= minWidth) {
          lines.push({ x: xStart, y: lineStart, width: xEnd - xStart, height: lineH })
        }
      } else if (lineH > maxHeight) {
        // Split tall block: local re-projection with lower threshold
        const block = cleaned.subarray(lineStart * w, y * w)
        const bProj = new Uint32Array(lineH)
        for (let ly = 0; ly < lineH; ly++) {
          for (let x = 0; x < w; x++) bProj[ly] += block[ly * w + x]
        }
        let median = 0
        const nonzero = Array.from(bProj).filter(v => v > 0).sort((a, b) => a - b)
        if (nonzero.length) median = nonzero[Math.floor(nonzero.length / 2)]
        const bThresh = Math.max(1, median * 0.1)
        let subIn = false, subStart = 0
        for (let ly = 0; ly <= lineH; ly++) {
          const tt = ly < lineH && bProj[ly] > bThresh
          if (tt && !subIn) { subStart = ly; subIn = true }
          else if (!tt && subIn) {
            const sh = ly - subStart
            if (sh >= minHeight && sh <= maxHeight) {
              const absY = lineStart + subStart
              const absYEnd = lineStart + ly
              const rs2 = ink.subarray(absY * w, absYEnd * w)
              const cp2 = new Uint32Array(w)
              for (let sly = 0; sly < sh; sly++)
                for (let x = 0; x < w; x++) cp2[x] += rs2[sly * w + x]
              let xs2 = -1, xe2 = -1
              for (let x = 0; x < w; x++) if (cp2[x] > 0) { xs2 = x; break }
              for (let x = w - 1; x >= 0; x--) if (cp2[x] > 0) { xe2 = x + 1; break }
              if (xs2 >= 0 && xe2 - xs2 >= minWidth) {
                lines.push({ x: xs2, y: absY, width: xe2 - xs2, height: sh })
              }
            }
            subIn = false
          }
        }
      }
      inLine = false
    }
  }

  lines.sort((a, b) => a.y - b.y || a.x - b.x)
  return lines
}

// ─── Step: Oreo flip (enchant white mask) ───

function oreoFlip(imageData) {
  const { data, width: w, height: h } = imageData
  const whiteMask = new Uint8Array(w * h)

  // White mask: max_ch > 150 AND max/min ratio < 1.4
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      const r = data[i], g = data[i+1], b = data[i+2]
      const maxCh = Math.max(r, g, b)
      const minCh = Math.min(r, g, b)
      if (maxCh > 150 && (maxCh / (minCh + 1)) < 1.4) {
        whiteMask[y * w + x] = 1
      }
    }
  }

  // Strip border columns: left/right 3 cols with >50% density
  const edgeCols = 3
  const colsToCheck = []
  for (let c = 0; c < Math.min(edgeCols, w); c++) colsToCheck.push(c)
  for (let c = Math.max(0, w - edgeCols); c < w; c++) colsToCheck.push(c)
  for (const c of colsToCheck) {
    let count = 0
    for (let y = 0; y < h; y++) count += whiteMask[y * w + c]
    if (count / h > 0.5) {
      for (let y = 0; y < h; y++) whiteMask[y * w + c] = 0
    }
  }

  return whiteMask
}

function detectEnchantSlotHeaders(whiteMask, w, h) {
  // Horizontal projection of white mask
  const wpr = new Uint32Array(h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) wpr[y] += whiteMask[y * w + x]
  }

  const ROW_THRESHOLD = 10
  const GAP_TOLERANCE = 2

  // Find runs
  const runs = []
  let inRun = false, runStart = 0
  for (let y = 0; y < h; y++) {
    if (wpr[y] >= ROW_THRESHOLD) {
      if (!inRun) { runStart = y; inRun = true }
    } else if (inRun) {
      runs.push([runStart, y])
      inRun = false
    }
  }
  if (inRun) runs.push([runStart, h])

  // Merge small gaps
  const merged = []
  for (const [s, e] of runs) {
    if (merged.length > 0 && s - merged[merged.length - 1][1] <= GAP_TOLERANCE) {
      merged[merged.length - 1][1] = e
    } else {
      merged.push([s, e])
    }
  }

  // Filter: 8 <= h <= 15, total px >= 150
  const bands = []
  for (const [s, e] of merged) {
    const bh = e - s
    let totalPx = 0
    for (let y = s; y < e; y++) totalPx += wpr[y]
    if (bh >= 8 && bh <= 15 && totalPx >= 150) {
      bands.push({ y: s, h: bh })
    }
  }
  return bands
}

function classifyEnchantLine(imageData, bounds, bands) {
  const { data, width: w } = imageData

  // Band overlap → header
  const ly = bounds.y, lh = bounds.height
  for (const band of bands) {
    const overlap = Math.min(ly + lh, band.y + band.h) - Math.max(ly, band.y)
    if (overlap > 0) return 'header'
  }

  // Saturation of text pixels (foreground: max_channel > 40)
  let satSum = 0, count = 0
  for (let y = bounds.y; y < bounds.y + bounds.height; y++) {
    for (let x = bounds.x; x < bounds.x + bounds.width; x++) {
      const i = (y * w + x) * 4
      const r = data[i], g = data[i+1], b = data[i+2]
      const maxCh = Math.max(r, g, b)
      if (maxCh > 40) {
        const minCh = Math.min(r, g, b)
        satSum += (maxCh - minCh) / (maxCh + 1)
        count++
      }
    }
  }
  if (count === 0) return 'grey'
  return (satSum / count) < 0.15 ? 'grey' : 'effect'
}

// ─── Pipeline runner ───

function runPipeline(ctx, originalImageData) {
  const steps = []
  const w = originalImageData.width
  const h = originalImageData.height

  // Step 0: Original
  steps.push({ id: 'original', dataURL: canvasToDataURL(originalImageData) })

  // Step 1: Border detection (visualize borders on original)
  const borders = detectBorders(originalImageData)
  const borderVis = cloneImageData(ctx, originalImageData)
  if (borders.bottomY !== null) {
    drawRect(borderVis, 0, borders.bottomY, w, 3, 0, 255, 255, 2)
  }
  if (borders.leftX !== null) {
    drawRect(borderVis, borders.leftX, 0, 3, h, 0, 255, 255, 2)
  }
  if (borders.rightX !== null) {
    drawRect(borderVis, borders.rightX, 0, 3, h, 0, 255, 255, 2)
  }
  steps.push({ id: 'borderDetection', dataURL: canvasToDataURL(borderVis) })

  // Step 2: Tooltip crop
  const cropX = borders.leftX !== null ? borders.leftX + 1 : 0
  const cropXEnd = borders.rightX !== null ? borders.rightX : w
  const cropY = 0
  const cropYEnd = borders.bottomY !== null ? borders.bottomY : h
  const cropW = cropXEnd - cropX
  const cropH = cropYEnd - cropY
  const cropped = cropImageData(ctx, originalImageData, cropX, cropY, cropW, cropH)
  steps.push({ id: 'tooltipCrop', dataURL: canvasToDataURL(cropped) })

  // Step 3: Orange mask
  const { orangeMask, bands } = detectOrangeHeaders(cropped)
  const orangeVis = ctx.createImageData(cropW, cropH)
  for (let i = 0; i < cropW * cropH; i++) {
    const idx = i * 4
    if (orangeMask[i]) {
      orangeVis.data[idx] = 255
      orangeVis.data[idx+1] = 140
      orangeVis.data[idx+2] = 0
    }
    orangeVis.data[idx+3] = 255
  }
  steps.push({ id: 'orangeMask', dataURL: canvasToDataURL(orangeVis) })

  // Step 4: Header bands (draw rectangles on cropped)
  const headerVis = cloneImageData(ctx, cropped)
  bands.forEach(band => {
    drawRect(headerVis, 0, band.y, cropW, band.h, 255, 140, 0, 2)
  })
  steps.push({ id: 'headerBands', dataURL: canvasToDataURL(headerVis) })

  // Step 5: Segmentation (color-coded regions)
  const segments = []
  if (bands.length > 0 && bands[0].y > 0) {
    segments.push({ y: 0, h: bands[0].y, type: 'pre_header' })
  }
  bands.forEach((band, i) => {
    const contentY = band.y + band.h
    const nextY = i + 1 < bands.length ? bands[i+1].y : cropH
    segments.push({ y: band.y, h: band.h, type: 'header' })
    if (nextY > contentY) {
      segments.push({ y: contentY, h: nextY - contentY, type: 'content' })
    }
  })
  const segVis = cloneImageData(ctx, cropped)
  const colors = {
    pre_header: [100, 200, 255],
    header: [255, 140, 0],
    content: [0, 200, 120],
  }
  segments.forEach(seg => {
    const [cr, cg, cb] = colors[seg.type]
    for (let y = seg.y; y < seg.y + seg.h && y < cropH; y++) {
      for (let x = 0; x < cropW; x++) {
        const i = (y * cropW + x) * 4
        segVis.data[i] = Math.round(segVis.data[i] * 0.5 + cr * 0.5)
        segVis.data[i+1] = Math.round(segVis.data[i+1] * 0.5 + cg * 0.5)
        segVis.data[i+2] = Math.round(segVis.data[i+2] * 0.5 + cb * 0.5)
      }
    }
  })
  steps.push({ id: 'segmentation', dataURL: canvasToDataURL(segVis) })

  // Step 6: Header OCR preprocessing (grayscale → threshold=50 BINARY_INV)
  // Each header crop is extracted and binarized independently
  const headerCrops = bands.map(band => {
    const crop = cropImageData(ctx, cropped, 0, band.y, cropW, band.h)
    const gray = cloneImageData(ctx, crop)
    toGrayscale(gray)
    thresholdBinaryInv(gray, 50)
    return canvasToDataURL(gray)
  })
  // Also show on the full image: overlay binarized headers at their positions
  const headerPreVis = cloneImageData(ctx, cropped)
  bands.forEach(band => {
    const crop = cropImageData(ctx, cropped, 0, band.y, cropW, band.h)
    const gray = cloneImageData(ctx, crop)
    toGrayscale(gray)
    thresholdBinaryInv(gray, 50)
    // Write binarized header back into the vis
    for (let ly = 0; ly < band.h && band.y + ly < cropH; ly++) {
      for (let x = 0; x < cropW; x++) {
        const srcIdx = (ly * cropW + x) * 4
        const dstIdx = ((band.y + ly) * cropW + x) * 4
        headerPreVis.data[dstIdx] = gray.data[srcIdx]
        headerPreVis.data[dstIdx+1] = gray.data[srcIdx+1]
        headerPreVis.data[dstIdx+2] = gray.data[srcIdx+2]
      }
    }
    drawRect(headerPreVis, 0, band.y, cropW, band.h, 255, 200, 0, 1)
  })
  steps.push({
    id: 'headerPreprocess',
    dataURL: canvasToDataURL(headerPreVis),
    headerCrops,
    headerCount: bands.length,
  })

  // ─── Per-segment processing ───
  // Process each non-header segment independently (matching the real V3 pipeline)
  let processableSegments = segments.filter(s => s.type !== 'header')
  if (processableSegments.length === 0) {
    processableSegments = [{ y: 0, h: cropH, type: 'pre_header' }]
  }

  processableSegments.forEach((seg, segIdx) => {
    const label = seg.type
    const segW = cropW
    const segH = seg.h

    // Content crop extraction
    const contentCrop = cropImageData(ctx, cropped, 0, seg.y, segW, segH)
    steps.push({ id: 'contentCrop', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(contentCrop) })

    // Grayscale
    const gray = cloneImageData(ctx, contentCrop)
    toGrayscale(gray)
    steps.push({ id: 'segGrayscale', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(gray) })

    // Binarization
    const binary = cloneImageData(ctx, gray)
    thresholdBinaryInv(binary, 80)
    steps.push({ id: 'segBinarization', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(binary) })

    // Enchant detection: run oreo flip on this segment's color crop
    const whiteMask = oreoFlip(contentCrop)
    const segEnchantBands = detectEnchantSlotHeaders(whiteMask, segW, segH)
    const isEnchant = segEnchantBands.length > 0

    if (isEnchant) {
      // White mask visualization
      const whiteMaskVis = ctx.createImageData(segW, segH)
      for (let i = 0; i < segW * segH; i++) {
        const idx = i * 4
        const v = whiteMask[i] ? 255 : 0
        whiteMaskVis.data[idx] = v
        whiteMaskVis.data[idx+1] = v
        whiteMaskVis.data[idx+2] = v
        whiteMaskVis.data[idx+3] = 255
      }
      steps.push({ id: 'enchantWhiteMask', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(whiteMaskVis) })

      // Oreo flip (inverted: black text on white) + slot header bands
      const oreoVis = ctx.createImageData(segW, segH)
      for (let i = 0; i < segW * segH; i++) {
        const idx = i * 4
        const v = whiteMask[i] ? 0 : 255
        oreoVis.data[idx] = v
        oreoVis.data[idx+1] = v
        oreoVis.data[idx+2] = v
        oreoVis.data[idx+3] = 255
      }
      const oreoWithBands = cloneImageData(ctx, oreoVis)
      segEnchantBands.forEach(band => {
        drawRect(oreoWithBands, 0, band.y, segW, band.h, 0, 180, 255, 2)
      })
      steps.push({ id: 'enchantOreoFlip', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(oreoWithBands), enchantBandCount: segEnchantBands.length })

      // Enchant line classification
      const enchantLines = detectLines(oreoVis)
      const classVis = cloneImageData(ctx, contentCrop)
      const classColors = {
        header: [0, 180, 255],
        effect: [255, 100, 200],
        grey: [160, 160, 160],
      }
      const classifiedLines = enchantLines.map(line => {
        const cls = classifyEnchantLine(contentCrop, line, segEnchantBands)
        return { ...line, cls }
      })
      classifiedLines.forEach(line => {
        const [cr, cg, cb] = classColors[line.cls]
        for (let y = line.y; y < line.y + line.height && y < segH; y++) {
          for (let x = line.x; x < line.x + line.width && x < segW; x++) {
            const i = (y * segW + x) * 4
            classVis.data[i] = Math.round(classVis.data[i] * 0.4 + cr * 0.6)
            classVis.data[i+1] = Math.round(classVis.data[i+1] * 0.4 + cg * 0.6)
            classVis.data[i+2] = Math.round(classVis.data[i+2] * 0.4 + cb * 0.6)
          }
        }
        const [br, bg, bb] = classColors[line.cls]
        drawRect(classVis, line.x, line.y, line.width, line.height, br, bg, bb, 1)
      })
      steps.push({ id: 'enchantClassification', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(classVis), classifiedLines })
    }

    // Line detection
    const lines = detectLines(binary)
    const lineVis = cloneImageData(ctx, binary)
    const lineColors = [
      [0, 200, 255], [255, 100, 100], [100, 255, 100],
      [255, 200, 0], [200, 100, 255], [255, 150, 200],
    ]
    lines.forEach((line, i) => {
      const [cr, cg, cb] = lineColors[i % lineColors.length]
      const padX = Math.max(2, Math.floor(line.height / 3))
      const padY = Math.max(1, Math.floor(line.height / 5))
      drawRect(lineVis,
        Math.max(0, line.x - padX), Math.max(0, line.y - padY),
        line.width + padX * 2, line.height + padY * 2,
        cr, cg, cb, 2)
    })
    steps.push({ id: 'segLineDetection', segmentIndex: segIdx, segmentLabel: label, dataURL: canvasToDataURL(lineVis), lineCount: lines.length })

    // Line crops
    const lineCrops = lines.map(line => {
      const padX = Math.max(2, Math.floor(line.height / 3))
      const padY = Math.max(1, Math.floor(line.height / 5))
      const cx = Math.max(0, line.x - padX)
      const cy = Math.max(0, line.y - padY)
      const cw = Math.min(segW - cx, line.width + padX * 2)
      const ch = Math.min(segH - cy, line.height + padY * 2)
      const crop = cropImageData(ctx, binary, cx, cy, cw, ch)
      return canvasToDataURL(crop)
    })
    steps.push({ id: 'segLineCrops', segmentIndex: segIdx, segmentLabel: label, dataURL: lineCrops.length > 0 ? lineCrops[0] : null, lineCrops })
  })

  return steps
}

// ─── Step translation helper ───

const PER_SEG_STEP_IDS = ['contentCrop', 'segGrayscale', 'segBinarization', 'segLineDetection', 'segLineCrops']

function stepTranslationKey(s) {
  if (s.segmentIndex != null && PER_SEG_STEP_IDS.includes(s.id)) {
    return `v3Pipeline.perSegSteps.${s.id}`
  }
  return `v3Pipeline.steps.${s.id}`
}

// ─── Component ───

const V3PipelineViewer = () => {
  const { t } = useTranslation()
  const [image, setImage] = useState(null)
  const [steps, setSteps] = useState(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [interval, setInterval_] = useState(2000)
  const [showHelp, setShowHelp] = useState(false)
  const [pixelated, setPixelated] = useState(false)

  const canvasRef = useRef(null)
  const fileInputRef = useRef(null)
  const timerRef = useRef(null)

  const handleUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const img = new Image()
      img.onload = () => {
        setImage(img)
        setSteps(null)
        setCurrentStep(0)
        setPlaying(false)
      }
      img.src = ev.target.result
    }
    reader.readAsDataURL(file)
  }

  const handleRun = useCallback(() => {
    if (!image || !canvasRef.current) return
    const canvas = canvasRef.current
    canvas.width = image.width
    canvas.height = image.height
    const ctx = canvas.getContext('2d')
    ctx.drawImage(image, 0, 0)
    const imageData = ctx.getImageData(0, 0, image.width, image.height)
    const result = runPipeline(ctx, imageData)
    setSteps(result)
    setCurrentStep(0)
    setPlaying(true)
  }, [image])

  // Slideshow timer
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (playing && steps && steps.length > 0) {
      timerRef.current = setInterval(() => {
        setCurrentStep(prev => {
          if (prev >= steps.length - 1) {
            setPlaying(false)
            return prev
          }
          return prev + 1
        })
      }, interval)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [playing, steps, interval])

  const goPrev = () => { setPlaying(false); setCurrentStep(s => Math.max(0, s - 1)) }
  const goNext = () => { setPlaying(false); setCurrentStep(s => steps ? Math.min(steps.length - 1, s + 1) : s) }
  const goFirst = () => { setPlaying(false); setCurrentStep(0) }
  const goLast = () => { setPlaying(false); setCurrentStep(steps ? steps.length - 1 : 0) }

  const step = steps?.[currentStep]

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-cyan-400">{t('v3Pipeline.title')}</h1>
        <p className="text-gray-400 mb-6">{t('v3Pipeline.subtitle')}</p>

        {/* Upload + Run */}
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <input type="file" ref={fileInputRef} onChange={handleUpload} accept="image/*" className="hidden" />
          <div className="flex flex-wrap gap-3 items-center">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {t('v3Pipeline.uploadImage')}
            </button>
            {image && (
              <button
                onClick={handleRun}
                className="bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-2 rounded-lg font-medium"
              >
                {t('v3Pipeline.runPipeline')}
              </button>
            )}
            {image && !steps && (
              <span className="text-gray-400 text-sm">{image.width} x {image.height}</span>
            )}
          </div>
        </div>

        {/* Slideshow display */}
        {steps && step && (
          <div className="bg-gray-800 rounded-lg p-6 mb-6">
            {/* Step title + help */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-cyan-400">
                  {t('v3Pipeline.step')} {currentStep + 1}/{steps.length}:{' '}
                  {step.segmentIndex != null
                    ? t('v3Pipeline.segmentStepTitle', { index: step.segmentIndex + 1, label: step.segmentLabel, step: t(`${stepTranslationKey(step)}.title`) })
                    : t(`${stepTranslationKey(step)}.title`)}
                </h2>
                <p className="text-gray-400 text-sm mt-1">{t(`${stepTranslationKey(step)}.description`)}</p>
              </div>
              <button
                onClick={() => setShowHelp(!showHelp)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  showHelp ? 'bg-cyan-600/20 text-cyan-400' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <HelpCircle className="w-4 h-4" />
                {t('v3Pipeline.help')}
              </button>
            </div>

            {showHelp && (
              <div className="mb-4 p-3 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-300 whitespace-pre-line">
                {t(`${stepTranslationKey(step)}.help`)}
              </div>
            )}

            {/* Image display */}
            <div className="border border-gray-700 rounded-lg p-2 bg-gray-950 mb-4 flex justify-center">
              {step.id === 'headerPreprocess' ? (
                <div className="w-full space-y-4 p-2">
                  {step.dataURL && (
                    <img src={step.dataURL} alt={step.id} className="max-w-full max-h-[400px] object-contain mx-auto" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
                  )}
                  {step.headerCrops && step.headerCrops.length > 0 && (
                    <div className="space-y-2 border-t border-gray-700 pt-3">
                      <p className="text-xs text-gray-500">{t('v3Pipeline.headerCropsLabel')}</p>
                      {step.headerCrops.map((crop, i) => (
                        <div key={i} className="flex items-center gap-3">
                          <span className="text-xs text-gray-500 w-8 text-right shrink-0">{i + 1}</span>
                          <img src={crop} alt={`Header ${i + 1}`} className="border border-gray-700 rounded max-h-10" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : step.id === 'segLineCrops' ? (
                <div className="w-full max-h-[600px] overflow-y-auto space-y-2 p-2">
                  {step.lineCrops && step.lineCrops.length > 0 ? (
                    step.lineCrops.map((crop, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <span className="text-xs text-gray-500 w-8 text-right shrink-0">{i + 1}</span>
                        <img src={crop} alt={`Line ${i + 1}`} className="border border-gray-700 rounded max-h-12" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500 text-sm">{t('v3Pipeline.noLines')}</p>
                  )}
                </div>
              ) : step.dataURL ? (
                <img src={step.dataURL} alt={step.id} className="max-w-full max-h-[600px] object-contain" style={{ imageRendering: pixelated ? 'pixelated' : 'auto' }} />
              ) : null}
            </div>

            {/* Extra info */}
            {step.lineCount !== undefined && (
              <p className="text-sm text-gray-400 mb-4">
                {t('v3Pipeline.linesDetected', { count: step.lineCount })}
              </p>
            )}
            {step.headerCount !== undefined && (
              <p className="text-sm text-gray-400 mb-4">
                {t('v3Pipeline.headersProcessed', { count: step.headerCount })}
              </p>
            )}
            {step.enchantBandCount !== undefined && (
              <p className="text-sm text-gray-400 mb-4">
                {t('v3Pipeline.enchantBandsDetected', { count: step.enchantBandCount })}
              </p>
            )}
            {step.classifiedLines && (
              <div className="flex flex-wrap gap-4 text-sm mb-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm" style={{backgroundColor: 'rgb(0,180,255)'}} />
                  <span className="text-gray-400">{t('v3Pipeline.enchantHeader')} ({step.classifiedLines.filter(l => l.cls === 'header').length})</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm" style={{backgroundColor: 'rgb(255,100,200)'}} />
                  <span className="text-gray-400">{t('v3Pipeline.enchantEffect')} ({step.classifiedLines.filter(l => l.cls === 'effect').length})</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm" style={{backgroundColor: 'rgb(160,160,160)'}} />
                  <span className="text-gray-400">{t('v3Pipeline.enchantGrey')} ({step.classifiedLines.filter(l => l.cls === 'grey').length})</span>
                </span>
              </div>
            )}

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-4">
              {/* Navigation */}
              <div className="flex items-center gap-1">
                <button onClick={goFirst} className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white" title="First">
                  <SkipBack className="w-4 h-4" />
                </button>
                <button onClick={goPrev} className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white" title="Previous">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => setPlaying(!playing)}
                  className="p-2 rounded hover:bg-gray-700 text-cyan-400 hover:text-cyan-300"
                  title={playing ? 'Pause' : 'Play'}
                >
                  {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                </button>
                <button onClick={goNext} className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white" title="Next">
                  <ChevronRight className="w-5 h-5" />
                </button>
                <button onClick={goLast} className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white" title="Last">
                  <SkipForward className="w-4 h-4" />
                </button>
              </div>

              {/* Interval slider */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400">{t('v3Pipeline.interval')}:</label>
                <input
                  type="range" min="500" max="5000" step="250"
                  value={interval}
                  onChange={e => setInterval_(parseInt(e.target.value))}
                  className="w-32"
                />
                <span className="text-sm text-gray-400 w-14">{(interval / 1000).toFixed(1)}s</span>
              </div>

              {/* Pixelated toggle */}
              <button
                onClick={() => setPixelated(p => !p)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  pixelated
                    ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-600/40'
                    : 'text-gray-400 hover:text-gray-200 border border-gray-700'
                }`}
              >
                <Grid2X2 className="w-3.5 h-3.5" />
                {t('v3Pipeline.pixelated')}
              </button>

              {/* Step dots */}
              <div className="flex gap-1 ml-auto">
                {steps.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => { setPlaying(false); setCurrentStep(i) }}
                    className={`w-2.5 h-2.5 rounded-full transition-colors ${
                      i === currentStep ? 'bg-cyan-400' : i < currentStep ? 'bg-gray-500' : 'bg-gray-700'
                    }`}
                    title={s.segmentIndex != null
                      ? t('v3Pipeline.segmentStepTitle', { index: s.segmentIndex + 1, label: s.segmentLabel, step: t(`${stepTranslationKey(s)}.title`) })
                      : t(`${stepTranslationKey(s)}.title`)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  )
}

export default V3PipelineViewer
