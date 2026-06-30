#!/bin/bash

# Nella root della tua app
rm -rf ./.bin
mkdir -p ./.bin

# =============
# Scarica Deno
# =============
# 1. Scarica
# - macOS (Universal - funziona su Intel e Apple Silicon):
# curl -L https://github.com/denoland/deno/releases/download/v2.8.2/deno-aarch64-apple-darwin.zip -o ./.bin/deno.zip
# - macOS (Intel - vecchi Mac):
curl -L https://github.com/denoland/deno/releases/download/v2.8.2/deno-x86_64-apple-darwin.zip -o ./.bin/deno.zip
# 2. Estrai
unzip ./.bin/deno.zip -d ./.bin
rm ./.bin/deno.zip
# 3. Rendi eseguibile
chmod +x ./.bin/deno
# 4. Verifica
./.bin/deno --version