"use client";

import { useState } from "react";
import { reflect, ReflectApiError } from "@/lib/api";
import type { ReflectResponse } from "@/lib/types";
import { SourceCard } from "./SourceCard";
import { VideoGrid } from "./VideoGrid";

const EMOTIONS = [
  "Anxious",
  "Sad",
  "Grateful",
  "Angry",
  "Lonely",
  "Guilty",
  "Confused",
  "Hopeful",
  "Stressed",
  "Afraid",
];

export function ReflectionApp() {
  const [freeText, setFreeText] = useState("");
  const [feelingText, setFeelingText] = useState<string | null>(null);
  const [result, setResult] = useState<ReflectResponse | null>(null);
  const [shownIds, setShownIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    try {
      const data = await reflect(trimmed);
      setFeelingText(trimmed);
      setResult(data);
      setShownIds(new Set(data.sources.map((s) => s.id)));
    } catch (err) {
      setError(err instanceof ReflectApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function anotherReminder() {
    if (!feelingText) return;
    setLoadingMore(true);
    setError(null);
    try {
      const data = await reflect(feelingText, Array.from(shownIds));
      if (data.sources.length > 0) {
        setResult(data);
        setShownIds((prev) => new Set([...prev, ...data.sources.map((s) => s.id)]));
      } else {
        setError("No further verified reminders found in the current library for this feeling.");
      }
    } catch (err) {
      setError(err instanceof ReflectApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold mb-2">How are you feeling?</h1>
        <p className="text-black/70 dark:text-white/70">
          Share a feeling and receive a grounded reminder from the Qur&apos;an, authentic hadith, and
          du&apos;a — never invented, always cited from a curated library.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-5 gap-2">
          {EMOTIONS.map((emotion) => (
            <button
              key={emotion}
              onClick={() => submit(`I feel ${emotion.toLowerCase()}.`)}
              disabled={loading}
              className="rounded-lg border border-black/10 dark:border-white/20 px-2 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-50 transition-colors"
            >
              {emotion}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="free-text" className="text-sm text-black/70 dark:text-white/70">
            Or describe it in your own words
          </label>
          <textarea
            id="free-text"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="e.g. I feel anxious about whether I'll succeed..."
            rows={3}
            className="rounded-lg border border-black/10 dark:border-white/20 px-3 py-2 bg-transparent"
          />
          <button
            onClick={() => submit(freeText)}
            disabled={loading || !freeText.trim()}
            className="self-start rounded-lg bg-black text-white dark:bg-white dark:text-black px-4 py-2 text-sm font-semibold disabled:opacity-50 transition-opacity"
          >
            {loading ? "Finding a grounded reminder…" : "Reflect"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/30 dark:border-red-800 px-4 py-3 text-sm text-red-800 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-6 border-t border-black/10 dark:border-white/15 pt-6">
          {result.reflection.opening && <p className="text-lg">{result.reflection.opening}</p>}

          {result.sources.length === 0 ? (
            <div className="rounded-lg border border-black/10 dark:border-white/15 px-4 py-3 text-sm">
              I couldn&apos;t find a verified reminder in the library for exactly this feeling. Closest
              themes identified: {result.classification.themes.join(", ") || "none identified"}. The
              library is still small — try describing it a bit differently, or explore sabr (patience)
              and tawakkul (trust in Allah).
            </div>
          ) : (
            <>
              <h2 className="text-lg font-semibold -mb-2">
                A reminder for {result.classification.emotion}
              </h2>
              {result.sources.map((source) => (
                <SourceCard
                  key={source.id}
                  source={source}
                  explanation={result.reflection.explanations[source.id] ?? ""}
                />
              ))}
              <button
                onClick={anotherReminder}
                disabled={loadingMore}
                className="self-start rounded-lg border border-black/20 dark:border-white/30 px-4 py-2 text-sm font-medium disabled:opacity-50"
              >
                {loadingMore ? "Looking for another angle…" : "Give me another reminder"}
              </button>
            </>
          )}

          <VideoGrid videos={result.videos} />

          <p className="text-xs text-black/50 dark:text-white/50">
            This tool only ever presents Qur&apos;an verses, hadith, and du&apos;a already stored in its
            curated, cited library — it never asks the AI model to generate scripture from memory.
          </p>
        </div>
      )}
    </div>
  );
}
