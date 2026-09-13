import type { Source } from "@/lib/types";

export function SourceCard({ source, explanation }: { source: Source; explanation: string }) {
  const caption = source.authenticity ? `${source.citation} — ${source.authenticity}` : source.citation;

  return (
    <div className="rounded-xl border border-black/10 dark:border-white/15 p-5 flex flex-col gap-3">
      <p className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50">{caption}</p>

      {source.arabic && (
        <p
          dir="rtl"
          className="text-right text-2xl leading-loose"
          style={{ fontFamily: '"Traditional Arabic", "Amiri", serif' }}
        >
          {source.arabic}
        </p>
      )}

      {source.transliteration && (
        <p className="italic text-sm text-black/70 dark:text-white/70">{source.transliteration}</p>
      )}

      <p className="text-base leading-relaxed">{source.translation}</p>

      {explanation && (
        <p className="text-sm text-black/70 dark:text-white/70">
          <span className="font-semibold text-black dark:text-white">Why this may help: </span>
          {explanation}
        </p>
      )}

      {!source.verified_against_source && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          ⚠️ Wording pending verification against Quran.com / Sunnah.com — see README.
        </p>
      )}
    </div>
  );
}
