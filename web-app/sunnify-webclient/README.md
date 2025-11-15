<div align="center">

# Sunnify Web Client (Next.js)

<em>Frontend for the Sunnify stack. Built with Next.js 14, Tailwind CSS, and shadcn/ui.</em>

</div>

---

## Prerequisites

- Node.js 18 or newer
- A running backend API
	- Local Flask: `http://127.0.0.1:5000`
	- Or the hosted Lambda used by default in `components/sunnify-app.tsx`

---

## Local Development

1) Install dependencies

```bash
npm install
```

2) Configure API base URL via `.env.local` (recommended)

```dotenv
NEXT_PUBLIC_API_BASE=http://127.0.0.1:5000
```

3) Start the dev server

```bash
npm run dev
```

Open `http://localhost:3000`.

---

## Local Production Simulation

```bash
npm run build
npm start
```

---

## Switching API Endpoints

This client currently points at a hosted AWS Lambda URL in `components/sunnify-app.tsx`. For local development, switch to:

```ts
const base = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:5000';
const url = `${base}/api/scrape-playlist`;
```

If you plan to consume realtime progress from the Flask backend, implement an SSE client using `EventSource` or a streaming fetch and update the UI as events arrive.

---

## Scripts

- `npm run dev` start Next.js dev server
- `npm run build` production build
- `npm start` run the production server
- `npm run lint` lint the codebase

---

## Troubleshooting

- 404 from backend: ensure the Flask server is running at `NEXT_PUBLIC_API_BASE` and that CORS is enabled
- CORS errors: Flask backend uses `flask-cors` by default; double check `app.py`
- Windows path issues: ensure the download path you enter is writable

---

## License

See the repository root `LICENSE`.
