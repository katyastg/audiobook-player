/**
 * Cloudflare Worker that re-serves the audiobook release assets as playable
 * audio.
 *
 * GitHub rewrites every release-asset download to
 * `Content-Type: application/octet-stream` + `Content-Disposition: attachment`,
 * regardless of the content type the asset was uploaded with. Desktop Chrome
 * ignores that and plays the file anyway; iOS Safari refuses it outright with
 * MEDIA_ERR_SRC_NOT_SUPPORTED, so the books would not play on an iPhone at all.
 *
 * This proxy streams the asset through untouched and only fixes the headers.
 * Range requests are forwarded so seeking (and the random-start button) keeps
 * working without downloading the whole file.
 *
 * Deploy: Cloudflare dashboard -> Workers & Pages -> Create -> Worker, then
 * paste this file in and deploy. The app then points AUDIO_BASE at the
 * resulting *.workers.dev URL.
 */

const REPO = "katyastg/audiobook-player";
const ALLOWED = /^book-[1-7]\.mp3$/;

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const name = url.pathname.replace(/^\/+/, "");

    if (!ALLOWED.test(name)) {
      return new Response("Not found", { status: 404 });
    }

    const tag = name.replace(/\.mp3$/, "");
    const target =
      "https://github.com/" + REPO + "/releases/download/" + tag + "/" + name;

    // Only the Range header matters upstream; forwarding the rest can make
    // GitHub's signed redirect reject the request.
    const upstreamHeaders = new Headers();
    const range = request.headers.get("Range");
    if (range) upstreamHeaders.set("Range", range);

    const upstream = await fetch(target, {
      method: "GET",
      headers: upstreamHeaders,
      redirect: "follow",
    });

    if (!upstream.ok && upstream.status !== 206) {
      return new Response("Upstream error " + upstream.status, {
        status: upstream.status,
      });
    }

    const headers = new Headers();
    headers.set("Content-Type", "audio/mpeg");
    headers.set("Accept-Ranges", "bytes");
    headers.set("Access-Control-Allow-Origin", "*");
    headers.set("Cache-Control", "public, max-age=3600");
    for (const name of ["Content-Length", "Content-Range", "ETag", "Last-Modified"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }

    if (request.method === "HEAD") {
      return new Response(null, { status: upstream.status, headers });
    }

    return new Response(upstream.body, { status: upstream.status, headers });
  },
};
