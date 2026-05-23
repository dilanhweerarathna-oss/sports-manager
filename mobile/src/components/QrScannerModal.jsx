// Camera-based QR scanner using jsQR. Opens as a full-screen overlay.
// Calls onScan(decodedText) when a code is detected.

import { useEffect, useRef, useState } from 'react';
import jsQR from 'jsqr';

export default function QrScannerModal({ onScan, onClose }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const rafRef    = useRef(0);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Camera not supported in this browser.');
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        video.setAttribute('playsinline', 'true');
        await video.play();
        scanFrame();
      } catch (e) {
        setError('Camera blocked. Allow camera access in your browser settings.');
      }
    }

    function scanFrame() {
      const video  = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || cancelled) return;

      if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        try {
          const code = jsQR(img.data, img.width, img.height, { inversionAttempts: 'dontInvert' });
          if (code && code.data) {
            stop();
            onScan(code.data);
            return;
          }
        } catch {/* keep scanning */}
      }
      rafRef.current = requestAnimationFrame(scanFrame);
    }

    function stop() {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
    }

    start();
    return stop;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="qr-modal">
      <div className="qr-header">
        <button type="button" className="icon-btn light" onClick={onClose}>✕</button>
        <div className="qr-title">Scan a student's QR</div>
      </div>
      <div className="qr-stage">
        <video ref={videoRef} className="qr-video" muted playsInline />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        <div className="qr-reticle" />
      </div>
      <div className="qr-hint">
        {error
          ? <span className="qr-error">{error}</span>
          : 'Point your camera at the QR code on the student card.'}
      </div>
    </div>
  );
}
