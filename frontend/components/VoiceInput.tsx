"use client";

import { useEffect, useRef, useState } from "react";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
}

export default function VoiceInput({
  onTranscript,
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const [micError, setMicError] = useState<"denied" | "">("")

  const recognitionRef = useRef<any>(null);
  const finalTranscriptRef = useRef("");

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = true;

    // Important: allow us to distinguish temporary speech
    // from confirmed speech.
    recognition.interimResults = true;

    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsListening(true);
      finalTranscriptRef.current = "";
    };

    recognition.onresult = (event: any) => {
      let interimTranscript = "";

      for (
        let i = event.resultIndex;
        i < event.results.length;
        i++
      ) {
        const transcript =
          event.results[i][0].transcript;

        if (event.results[i].isFinal) {
          // Store only confirmed speech
          finalTranscriptRef.current += transcript + " ";
        } else {
          // Temporary speech
          interimTranscript += transcript;
        }
      }

      // Send the complete current transcript,
      // NOT an appended copy.
      const completeTranscript =
        finalTranscriptRef.current + interimTranscript;

      onTranscript(completeTranscript.trim());
    };

    recognition.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);

      // BUG-06 FIX: Handle permission dismissed/denied with actionable UI
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setMicError("denied");
      }

      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
    };
  }, [onTranscript]);

  if (!supported) {
    return (
      <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-3">
        <p className="text-xs text-yellow-300">
          Voice input is not supported in this browser.
          Please use the text answer box.
        </p>
      </div>
    );
  }

  function startListening() {
    try {
      setMicError("");
      finalTranscriptRef.current = "";
      recognitionRef.current?.start();
    } catch {
      console.log("Speech recognition is already running.");
    }
  }

  function stopListening() {
    recognitionRef.current?.stop();
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        {!isListening ? (
          <button
            type="button"
            onClick={startListening}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500"
          >
            <span>🎤</span>
            Start Speaking
          </button>
        ) : (
          <button
            type="button"
            onClick={stopListening}
            className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-red-500"
          >
            <span className="animate-pulse">●</span>
            Stop Speaking
          </button>
        )}

        {isListening && (
          <div className="flex items-center gap-2 text-xs text-green-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-green-400" />
            Listening...
          </div>
        )}
      </div>

      {/* BUG-06 FIX: Show actionable message when mic permission is denied */}
      {micError === "denied" && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          🎤 Microphone access was denied. Click the mic icon 🔒 in your browser address bar and select “Allow”, then click Start Speaking again.
        </div>
      )}
    </div>
  );
}