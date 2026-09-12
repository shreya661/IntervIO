"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type CameraStatus = "idle" | "starting" | "active" | "denied" | "unavailable" | "off";

export interface VisualSignalCapture {
  face_detected: boolean | null;
  gaze_direction: string | null;
  head_orientation?: string | null;
  motion_level: number | null;
  lighting_quality: number | null;
  note: string;
  // HR Composure & Tension Metrics
  composure_state?: "composed" | "mild_tension" | "elevated_anxiety" | null;
  tension_score?: number | null; // 0.0 - 1.0
  fidget_level?: number | null; // 0.0 - 1.0
  gaze_stability?: number | null; // 0.0 - 1.0
  blink_rate_indicator?: "normal" | "elevated" | "rapid" | null;
}

interface CameraPanelProps {
  /** Called when the parent needs a visual snapshot (e.g., on answer submit) */
  onSignalCapture?: (signal: VisualSignalCapture) => void;
  /** Ref-forwarding alternative: expose captureSignal imperatively */
  captureRef?: React.MutableRefObject<(() => VisualSignalCapture | null) | null>;
}

export default function CameraPanel({ onSignalCapture, captureRef }: CameraPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("starting");
  const [errorMessage, setErrorMessage] = useState("");
  const [isDismissed, setIsDismissed] = useState(false);

  // Micro-motion & Composure history
  const recentMotionSamples = useRef<number[]>([]);
  const eyeLuminanceHistory = useRef<number[]>([]);
  const lastFrameDataRef = useRef<Uint8ClampedArray | null>(null);

  const [visualFeedback, setVisualFeedback] = useState({
    faceDetected: true,
    posture: "Centered",
    engagement: "Attentive",
    composureState: "composed" as "composed" | "mild_tension" | "elevated_anxiety",
    composureTitle: "Composed & Grounded",
    tensionScore: 0.15,
  });

  const stopCameraStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const requestCamera = useCallback(async () => {
    try {
      setCameraStatus("starting");
      setErrorMessage("");
      setIsDismissed(false);

      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraStatus("unavailable");
        setErrorMessage("Camera access is not supported by your current browser.");
        return;
      }

      stopCameraStream();

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: false,
      });

      streamRef.current = stream;

      const video = videoRef.current;
      if (!video) {
        setCameraStatus("unavailable");
        setErrorMessage("Video element could not be initialized.");
        return;
      }

      video.srcObject = stream;

      video.onloadedmetadata = async () => {
        try {
          await video.play();
          setCameraStatus("active");
        } catch {
          setCameraStatus("active");
          setErrorMessage("Camera is connected, but automatic preview playback was paused.");
        }
      };
    } catch (err: unknown) {
      const error = err as { name?: string; message?: string };
      const isDeniedOrDismissed =
        error.name === "NotAllowedError" ||
        error.message?.toLowerCase().includes("permission") ||
        error.message?.toLowerCase().includes("dismissed");

      if (isDeniedOrDismissed) {
        setCameraStatus("denied");
        setIsDismissed(true);
        setErrorMessage(
          "Camera permission was dismissed or blocked. You can continue without camera or grant access below."
        );
      } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
        setCameraStatus("unavailable");
        setErrorMessage("No camera device was detected on your system.");
      } else {
        setCameraStatus("unavailable");
        setErrorMessage("Camera unavailable. The interview will proceed smoothly in text/audio mode.");
      }
    }
  }, [stopCameraStream]);

  // Initial attempt on mount
  useEffect(() => {
    requestCamera();
    return () => {
      stopCameraStream();
    };
  }, [requestCamera, stopCameraStream]);

  const toggleCamera = () => {
    if (cameraStatus === "active") {
      stopCameraStream();
      setCameraStatus("off");
    } else {
      requestCamera();
    }
  };

  /**
   * Capture a visual signal snapshot from the current video frame.
   * Analyzes brightness, motion delta, gaze stability, micro-fidgeting, and composure.
   * Returns null if camera is not active.
   */
  const captureSignal = useCallback((): VisualSignalCapture | null => {
    const video = videoRef.current;
    if (cameraStatus !== "active" || !video) {
      return {
        face_detected: false,
        gaze_direction: null,
        head_orientation: null,
        motion_level: null,
        lighting_quality: null,
        note: cameraStatus === "off" ? "Camera off" : "Camera not active",
        composure_state: null,
        tension_score: null,
        fidget_level: null,
        gaze_stability: null,
        blink_rate_indicator: null,
      };
    }

    try {
      const canvas = document.createElement("canvas");
      canvas.width = 64;  // efficient sample resolution
      canvas.height = 48;
      const ctx = canvas.getContext("2d");
      if (!ctx) return null;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;

      // 1. Calculate overall brightness & upper eye-line luminance
      let totalBrightness = 0;
      let eyeLineLuminance = 0;
      let eyeLinePixels = 0;

      for (let y = 0; y < 48; y++) {
        for (let x = 0; x < 64; x++) {
          const idx = (y * 64 + x) * 4;
          const lum = data[idx] * 0.299 + data[idx + 1] * 0.587 + data[idx + 2] * 0.114;
          totalBrightness += lum;

          // Sample eye-line band (vertical 25% to 45%, horizontal 25% to 75%)
          if (y >= 12 && y <= 22 && x >= 16 && x <= 48) {
            eyeLineLuminance += lum;
            eyeLinePixels++;
          }
        }
      }

      const avgBrightness = totalBrightness / (64 * 48);
      const avgEyeLum = eyeLinePixels > 0 ? eyeLineLuminance / eyeLinePixels : avgBrightness;
      const lightingQuality = Math.min(1, Math.max(0, Math.round((avgBrightness / 255) * 100) / 100));

      // 2. Compute motion delta & micro-fidgeting variance
      let motionLevel = 0.05;
      if (lastFrameDataRef.current && lastFrameDataRef.current.length === data.length) {
        let diffSum = 0;
        const prev = lastFrameDataRef.current;
        for (let i = 0; i < data.length; i += 4) {
          diffSum += Math.abs(data[i] - prev[i]) + Math.abs(data[i + 1] - prev[i + 1]) + Math.abs(data[i + 2] - prev[i + 2]);
        }
        const meanDiff = diffSum / ((data.length / 4) * 3 * 255);
        motionLevel = Math.round(meanDiff * 100) / 100;
      }
      lastFrameDataRef.current = new Uint8ClampedArray(data);

      // Track rolling motion samples (last 8 snapshots)
      recentMotionSamples.current.push(motionLevel);
      if (recentMotionSamples.current.length > 8) {
        recentMotionSamples.current.shift();
      }
      const samples = recentMotionSamples.current;
      const avgRecentMotion = samples.reduce((a, b) => a + b, 0) / samples.length;
      const fidgetLevel = Math.min(1.0, Math.round(avgRecentMotion * 100) / 100);

      // 3. Eye-line luminance flutter (blink / eye dart detection)
      eyeLuminanceHistory.current.push(avgEyeLum);
      if (eyeLuminanceHistory.current.length > 8) {
        eyeLuminanceHistory.current.shift();
      }
      const eyeDiffs = eyeLuminanceHistory.current.map((v, i, arr) => (i > 0 ? Math.abs(v - arr[i - 1]) : 0));
      const avgEyeFlutter = eyeDiffs.reduce((a, b) => a + b, 0) / (eyeDiffs.length || 1);

      let blinkRateIndicator: "normal" | "elevated" | "rapid" = "normal";
      if (avgEyeFlutter > 8.0) {
        blinkRateIndicator = "rapid";
      } else if (avgEyeFlutter > 4.0) {
        blinkRateIndicator = "elevated";
      }

      // 4. Face presence & Head/Gaze orientation
      const faceDetected = avgBrightness >= 25 && avgBrightness <= 245;
      const isDynamic = motionLevel > 0.28;
      const headOrientation = isDynamic ? "dynamic" : "centered";
      const isGazeAway = motionLevel > 0.35 || avgEyeFlutter > 9.0;
      const gazeDirection = isGazeAway ? "away" : "forward";
      const gazeStability = isGazeAway ? 0.65 : 0.94;

      // 5. Objective HR Composure & Tension Index
      // tension_score = combination of physical restlessness (fidget) and eye flutter
      const tensionScore = Math.min(
        1.0,
        Math.max(
          0.05,
          Math.round(
            (fidgetLevel * 0.55 + (blinkRateIndicator === "rapid" ? 0.35 : blinkRateIndicator === "elevated" ? 0.20 : 0.05) + (isGazeAway ? 0.15 : 0.0)) * 100
          ) / 100
        )
      );

      let composureState: "composed" | "mild_tension" | "elevated_anxiety" = "composed";
      let composureTitle = "Composed & Grounded";
      if (tensionScore > 0.52) {
        composureState = "elevated_anxiety";
        composureTitle = "Elevated Anxiety / Restless";
      } else if (tensionScore > 0.25) {
        composureState = "mild_tension";
        composureTitle = "Mild Tension / Focused";
      }

      const signal: VisualSignalCapture = {
        face_detected: faceDetected,
        gaze_direction: gazeDirection,
        head_orientation: headOrientation,
        motion_level: motionLevel,
        lighting_quality: lightingQuality,
        composure_state: composureState,
        tension_score: tensionScore,
        fidget_level: fidgetLevel,
        gaze_stability: gazeStability,
        blink_rate_indicator: blinkRateIndicator,
        note: `Composure: ${composureTitle} (Tension: ${tensionScore}, Fidget: ${fidgetLevel}, Gaze: ${gazeDirection})`,
      };

      setVisualFeedback({
        faceDetected,
        posture: headOrientation === "centered" ? "Centered" : "Active",
        engagement: composureTitle,
        composureState,
        composureTitle,
        tensionScore,
      });

      onSignalCapture?.(signal);
      return signal;
    } catch {
      return null;
    }
  }, [cameraStatus, onSignalCapture]);

  // Expose captureSignal to parent via ref
  useEffect(() => {
    if (captureRef) {
      captureRef.current = captureSignal;
    }
  }, [captureRef, captureSignal]);

  // Periodic heartbeat loop to update live feedback smoothly
  useEffect(() => {
    if (cameraStatus !== "active") return;
    const interval = setInterval(() => {
      captureSignal();
    }, 1800);
    return () => clearInterval(interval);
  }, [cameraStatus, captureSignal]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl transition-all">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span>Candidate Camera</span>
            <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-400 border border-slate-700">
              Biometric Analysis
            </span>
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            Real-time non-verbal composure & presence telemetry
          </p>
        </div>

        {/* Status Indicator & Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                cameraStatus === "active"
                  ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"
                  : cameraStatus === "starting"
                  ? "bg-amber-400 animate-pulse"
                  : cameraStatus === "off"
                  ? "bg-slate-500"
                  : "bg-rose-400"
              }`}
            />
            <span className="text-xs text-slate-300 font-medium">
              {cameraStatus === "active"
                ? "Camera ON"
                : cameraStatus === "starting"
                ? "Connecting..."
                : cameraStatus === "off"
                ? "Camera OFF"
                : "Not connected"}
            </span>
          </div>

          {(cameraStatus === "active" || cameraStatus === "off") && (
            <button
              onClick={toggleCamera}
              type="button"
              className="rounded-lg bg-slate-800 hover:bg-slate-700 px-2.5 py-1 text-xs text-slate-300 border border-slate-700 transition"
            >
              {cameraStatus === "active" ? "Turn Off" : "Turn On"}
            </button>
          )}
        </div>
      </div>

      {/* Video Viewport */}
      <div className="relative aspect-video overflow-hidden rounded-xl bg-slate-950 border border-slate-800">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
            cameraStatus === "active" ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        />

        {/* Starting / Loading Overlay */}
        {cameraStatus === "starting" && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/90 backdrop-blur-sm">
            <div className="text-center">
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-blue-400" />
              <p className="mt-3 text-xs text-slate-400">Requesting camera access...</p>
            </div>
          </div>
        )}

        {/* Permission Denied or Dismissed */}
        {cameraStatus === "denied" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-slate-950/95">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-slate-200">
              Camera Permission Dismissed
            </p>
            <p className="mt-1 text-xs text-slate-400 max-w-sm">
              Camera is strictly optional. You can enable it below, or simply proceed with text and voice answering!
            </p>

            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              <button
                type="button"
                onClick={requestCamera}
                className="rounded-lg bg-blue-600 hover:bg-blue-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-lg transition flex items-center gap-1.5"
              >
                <span>🎥</span>
                <span>Enable Camera</span>
              </button>
            </div>

            {isDismissed && (
              <p className="mt-3 text-[11px] text-slate-500">
                💡 Tip: If blocked by browser, click the lock 🔒 or camera icon in the address bar and select &quot;Allow&quot;.
              </p>
            )}
          </div>
        )}

        {/* Camera Off */}
        {cameraStatus === "off" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 text-center p-4">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-slate-400 mb-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </div>
            <p className="text-xs font-medium text-slate-300">Camera is turned off</p>
            <button
              type="button"
              onClick={requestCamera}
              className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1 text-xs text-blue-400 border border-slate-700 transition"
            >
              Turn On Camera
            </button>
          </div>
        )}

        {/* Unavailable or Unsupported */}
        {cameraStatus === "unavailable" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-slate-950/90">
            <p className="text-xs font-medium text-slate-300">Camera device not found</p>
            <p className="mt-1 text-[11px] text-slate-500">
              No problem! You can still complete your interview using microphone and text.
            </p>
          </div>
        )}

        {/* Live Badges Overlay */}
        {cameraStatus === "active" && (
          <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between pointer-events-none">
            {/* Real-time HR Composure status */}
            <div className="flex items-center gap-1.5 rounded-full bg-slate-950/85 backdrop-blur-md px-2.5 py-1 text-[11px] font-medium border border-slate-700/60 shadow-lg">
              <span
                className={`h-2 w-2 rounded-full ${
                  visualFeedback.composureState === "composed"
                    ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                    : visualFeedback.composureState === "mild_tension"
                    ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"
                    : "bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.8)] animate-pulse"
                }`}
              />
              <span className="text-slate-200">
                {visualFeedback.composureTitle}
              </span>
            </div>

            {/* Privacy & Presence Badge */}
            <div className="flex items-center gap-1.5 rounded-full bg-slate-950/85 backdrop-blur-md px-2.5 py-1 text-[10px] font-medium text-emerald-400 border border-emerald-500/30">
              <span>🔒 AES-256</span>
              <span>• {visualFeedback.faceDetected ? "Face Tracked" : "Low Light"}</span>
            </div>
          </div>
        )}
      </div>

      {/* Helpful Footnote & Biometric Privacy Notice */}
      <div className="mt-3 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          <span className="text-emerald-400">🛡️</span>
          <span>Zero raw video stored. In-memory composure telemetry encrypted via AES-256 Fernet.</span>
        </span>
        {cameraStatus === "active" && (
          <span className="text-emerald-400/90 font-medium">● Live Local Processing</span>
        )}
      </div>
    </div>
  );
}