<div align="center">

# Sunnify Web Client (Next.js)

<em>Frontend for the Sunnify stack. Built with Next.js 14, Tailwind CSS, and shadcn/ui.</em>

</div>

---

## Prerequisites

- Node.js 18 or newer
- A running backend API (Render deployment or local Flask)

---

## Local Development

1. Install dependencies

```bash
npm install
```

2. Start the dev server

```bash
npm run dev
```

Open `http://localhost:3000`.

---

## API Endpoint

The client points to the Render-hosted backend by default:

```
https://sunnify-spotify-downloader.onrender.com/api/scrape-playlist
```

For local development, update `components/sunnify-app.tsx` or use environment variables.

---

## Scripts

- `npm run dev` start Next.js dev server
- `npm run build` production build
- `npm start` run the production server
- `npm run lint` lint the codebase
- `npm run typecheck` run TypeScript type checking
- `npm run format` format code with Prettier

---

## Troubleshooting

- **Cold starts**: The Render free tier spins down after inactivity. First request may take up to 50 seconds.
- **CORS errors**: The Flask backend uses `flask-cors` which allows all origins by default.
- **Build failures**: Ensure Node.js 18+ and run `npm install` first.

---

## License

See the repository root `LICENSE`.
