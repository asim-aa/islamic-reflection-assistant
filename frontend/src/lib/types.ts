export type Classification = {
  emotion: string;
  secondary_emotions: string[];
  intent: string;
  themes: string[];
};

export type Source = {
  id: string;
  source_type: "quran" | "hadith" | "dua";
  citation: string;
  authenticity?: string;
  arabic?: string;
  transliteration?: string;
  translation: string;
  themes: string[];
  intents: string[];
  verified_against_source?: boolean;
};

export type Reflection = {
  opening: string;
  explanations: Record<string, string>;
};

export type Video = {
  video_id: string;
  title: string;
  channel_title: string;
  channel_id?: string;
  thumbnail?: string;
  url: string;
};

export type ReflectResponse = {
  classification: Classification;
  sources: Source[];
  reflection: Reflection;
  videos: Video[];
};
