import { useState, useEffect } from 'react';
import { examineItem } from '@mabi/shared/api/items';
import { parseExamineResult } from '@mabi/shared/lib/examineResult';

export function useImageUpload({ onScanComplete, onScanError } = {}) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [ocrResult, setOcrResult] = useState(null);
  const [detectedLines, setDetectedLines] = useState([]);
  const [sessionId, setSessionId] = useState(null);

  const loadFile = (f) => {
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    setOcrResult(null);
    setDetectedLines([]);
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) loadFile(selectedFile);
  };

  // Paste handler
  useEffect(() => {
    const handlePaste = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          loadFile(item.getAsFile());
          return;
        }
      }
    };
    document.addEventListener('paste', handlePaste);
    return () => document.removeEventListener('paste', handlePaste);
  }, []);

  const handleScan = async () => {
    if (!file) return;

    setIsLoading(true);
    setLoadingStep('SEGMENTING');

    try {
      setLoadingStep('RECOGNIZING');
      const { data } = await examineItem(file);
      setOcrResult(data);

      const result = parseExamineResult(data);
      setDetectedLines(
        Object.values(result.sections).flatMap(s => s.lines || [])
      );
      setSessionId(result.sessionId);

      onScanComplete?.(result);

      setLoadingStep('COMPLETE');
      setTimeout(() => setLoadingStep(''), 2000);
    } catch (error) {
      console.error('Error processing image:', error);
      onScanError?.(error);
      setLoadingStep('ERROR');
    } finally {
      setIsLoading(false);
    }
  };

  const clearImage = () => {
    setFile(null);
    setPreviewUrl(null);
    setOcrResult(null);
    setDetectedLines([]);
  };

  const resetUpload = () => {
    clearImage();
    setSessionId(null);
  };

  return {
    file, previewUrl, isLoading, loadingStep, ocrResult, sessionId,
    handleFileChange,
    handleScan,
    clearImage,
    resetUpload,
  };
}
