import { fileURLToPath } from "node:url"
import { dirname } from "node:path"

const projectRoot = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the file-tracing root to this app so Next 15 doesn't infer the
  // monorepo root (multiple lockfiles upstream) and warn on every build.
  outputFileTracingRoot: projectRoot,
  // covers come straight from spotify's cdn, already sized; the optimizer
  // endpoint would only be quota and attack surface nobody uses
  images: { unoptimized: true },
}

export default nextConfig
