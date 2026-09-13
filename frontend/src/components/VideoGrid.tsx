import type { Video } from "@/lib/types";

export function VideoGrid({ videos }: { videos: Video[] }) {
  if (videos.length === 0) return null;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Related videos from trusted channels</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {videos.map((video) => (
          <VideoCard key={video.video_id} video={video} />
        ))}
      </div>
    </div>
  );
}

function VideoCard({ video }: { video: Video }) {
  const initial = (video.channel_title || "?").slice(0, 1).toUpperCase();

  return (
    <a
      href={video.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block no-underline text-inherit"
    >
      <div className="relative w-full pt-[56.25%] rounded-xl overflow-hidden bg-neutral-900 mb-2">
        {video.thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnail}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
          />
        )}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[46px] h-8 bg-black/75 rounded-lg flex items-center justify-center">
          <div
            className="ml-0.5"
            style={{
              width: 0,
              height: 0,
              borderTop: "7px solid transparent",
              borderBottom: "7px solid transparent",
              borderLeft: "12px solid white",
            }}
          />
        </div>
      </div>
      <div className="flex gap-2.5 items-start">
        <div className="shrink-0 w-8 h-8 rounded-full bg-red-700 text-white flex items-center justify-center text-sm font-semibold">
          {initial}
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-sm leading-snug line-clamp-2">{video.title}</p>
          <p className="text-xs opacity-65 truncate">{video.channel_title}</p>
        </div>
      </div>
    </a>
  );
}
