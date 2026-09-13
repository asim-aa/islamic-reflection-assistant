import type { ReflectResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ReflectApiError extends Error {}

export async function reflect(
  feelingText: string,
  excludeIds: string[] = []
): Promise<ReflectResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/reflect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feeling_text: feelingText, exclude_ids: excludeIds }),
    });
  } catch {
    throw new ReflectApiError(
      "Couldn't reach the reflection service. Check your connection and try again."
    );
  }

  if (!res.ok) {
    throw new ReflectApiError(
      "Something went wrong while looking for a reminder (the reminder library or the AI model may be temporarily unreachable). Please try again shortly."
    );
  }

  return res.json();
}
