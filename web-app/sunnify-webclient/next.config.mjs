import { fileURLToPath } from "node:url"
import { dirname } from "node:path"

const projectRoot = dirname(fileURLToPath(import.meta.url))
const BACKEND = "https://sunnify-spotify-downloader.onrender.com"

// Covers come from Spotify's CDNs; the only API the page calls is the backend.
// Next's bootstrap and React's style props are inline, hence 'unsafe-inline';
// every other source is pinned. Dev keeps Next's eval + websocket HMR working.
const isDev = process.env.NODE_ENV !== "production"
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://i.scdn.co https://*.scdn.co https://*.spotifycdn.com",
  "font-src 'self'",
  `connect-src 'self' ${BACKEND}${isDev ? " ws: http://localhost:5000" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ")

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root to this app so Next doesn't infer the monorepo root
  // (there are lockfiles further up) and warn on every build. Turbopack, the
  // default bundler since Next 16, reads its own key; file tracing reads the other.
  outputFileTracingRoot: projectRoot,
  turbopack: { root: projectRoot },
  // covers come straight from spotify's cdn, already sized; the optimizer
  // endpoint would only be quota and attack surface nobody uses
  images: { unoptimized: true },
  // no framework fingerprint in every response
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }]
  },
}

export default nextConfig
