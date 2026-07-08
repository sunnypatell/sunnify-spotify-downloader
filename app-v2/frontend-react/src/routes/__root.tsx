import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router';

import type { EnvVarsInput } from "@/constants";
import { RootLayout } from '@/components/views/root/root-layout';
import { RootProviders } from '@/components/views/root/root-providers';
import appCss from '../styles.css?url';

const THEME_INIT_SCRIPT = `(function(){try{var stored=window.localStorage.getItem('theme');var mode=(stored==='light'||stored==='dark'||stored==='auto')?stored:'auto';var prefersDark=window.matchMedia('(prefers-color-scheme: dark)').matches;var resolved=mode==='auto'?(prefersDark?'dark':'light'):mode;var root=document.documentElement;root.classList.remove('light','dark');root.classList.add(resolved);if(mode==='auto'){root.removeAttribute('data-theme')}else{root.setAttribute('data-theme',mode)}root.style.colorScheme=resolved;}catch(e){}})();`;
const CONFIG_INIT_SCRIPT = `
// This script is used to pass SAFE environment variables to the frontend, by augmenting the window object
// The frontend index.html file load this script because is part of the <head>
//
// IN DEV: this script is used 
// IN PROD (electron bundle): this script is overwritted by electron main

// FRONTEND_CONFIG_START 
// Following values:
// - are injected in src/routes/__root > CONFIG_INIT_SCRIPT 
// - are DEV only
window.FRONTEND_SAFE_ENV_VARS = ${JSON.stringify({
  BACKEND_HTTP_API_URL: "http://localhost:8000",
  BACKEND_WS_API_URL: "ws://localhost:8000",
  APP_VERSION: "0.0.1",
  FRONTEND_APP_MODE: "DEV",
} satisfies EnvVarsInput)}
// FRONTEND_CONFIG_END 
`;

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: 'utf-8',
      },
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1',
      },
      {
        title: 'SpotiDisk',
      },
    ],
    links: [
      {
        rel: 'stylesheet',
        href: appCss,
      },
    ],
  }),
  shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode; }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: CONFIG_INIT_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <HeadContent />
      </head>
      <body className="font-sans antialiased [overflow-wrap:anywhere] selection:bg-[rgba(79,184,178,0.24)]">
        <RootProviders>
          <RootLayout>
            {children}
          </RootLayout>
        </RootProviders>
        <Scripts />
      </body>
    </html>
  );
}
