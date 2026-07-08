import path from "node:path";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";

import type { Logger } from "./logger";

type WebServerInitOptions = {
  /** Path to directory to serve, all files inside will be served */
  dirPathToServe: string;
  /** Port to expose */
  port: number;
  /** logger instance */
  logger: Logger;
};

/**
 * Simple static web server, that serves static files from a given directory.
 */
export class WebServer {
  dirPathToServe: string;
  port: number;
  private server: ReturnType<typeof createServer> | null;
  private logger: Logger;
  private loggerResponse: WebServerLoggerResponse;

  constructor({
    dirPathToServe,
    port,
    logger,
  }: WebServerInitOptions) {
    this.dirPathToServe = dirPathToServe;
    this.port = port;
    this.server = null;
    this.logger = logger;
    this.loggerResponse = new WebServerLoggerResponse({ logger });
  }

  launch() {
    const BASE_DIR_PATH = this.dirPathToServe;
    const PORT = this.port;

    this.server = createServer(
      async (req, res) => {

        let method: string = '';
        let pathname: string = '';

        try {

          // if not method or not url -> 400
          if (!req.method || !req.url) {
            res.writeHead(400);
            res.end('Bad Request');
            this.loggerResponse.logResponse({
              status: 400,
              method: req.method ?? '',
              pathname: req.url ?? '',
            });
            return;
          }

          // parse request data
          method = req.method;
          pathname = new URL(req.url, 'http://localhost').pathname;

          // if method is not GET -> Method Not Allowed (405)
          if (method !== 'GET') {
            res.writeHead(405);
            res.end('Method Not Allowed');
            this.loggerResponse.logResponse({ status: 405, method, pathname });
            return;
          }

          // derive file to serve path from pathname (to know which file to serve)
          const filePath = path.join(BASE_DIR_PATH, pathname === '/' ? 'index.html' : pathname);

          // if file does not exists -> 404
          const fileExists = await utilsDisk.checkIfFileExists(filePath);
          if (!fileExists) {
            res.writeHead(404);
            res.end('Not Found');
            this.loggerResponse.logResponse({ status: 404, method, pathname });
            return;
          }

          // if file content is not readable -> 404
          const fileContent = await utilsDisk.getFileContent(filePath);
          if (fileContent.status === 'error') {
            res.writeHead(404);
            res.end('Not Found');
            this.loggerResponse.logResponse({ status: 404, method, pathname });
            return;
          }

          // serve file -> 200
          const fileMymeType = utilsDisk.deriveFileMimeTypeByFilePath(filePath);
          res.writeHead(200, { 'Content-Type': fileMymeType });
          res.end(fileContent.buffer);
          this.loggerResponse.logResponse({ status: 200, method, pathname });

        }
        // catch all errors -> 500
        catch {
          res.writeHead(500);
          res.end('Internal Server Error');
          this.loggerResponse.logResponse({ status: 500, method, pathname });
        }
      }
    );

    this.server.listen(PORT, () => {
      this.logger.log(`Server running on http://localhost:${PORT}`);
    });
    this.server.on('error', (err) => {
      this.logger.error('Web server error:', err);
    });

  }
  kill() {
    this.server?.close();
  }

}

class WebServerLoggerResponse {
  logger: Logger;
  constructor({
    logger
  }: {
    logger: Logger;
  }) {
    this.logger = logger;
  }
  logResponse({
    status,
    method,
    pathname,
  }: {
    status: 200 | 400 | 404 | 405 | 500,
    method: string,
    pathname: string,
  }) {
    this.logger.log(`${status} ${method} ${pathname}`);
  }
}

const utilsDisk = {
  deriveFileMimeTypeByFilePath: (filePath: string): string => {
    const ext = path.extname(filePath).toLowerCase();
    const types: Record<string, string> = {
      '.html': 'text/html',
      '.css': 'text/css',
      '.js': 'application/javascript',
      '.json': 'application/json',
      '.svg': 'image/svg+xml',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.gif': 'image/gif',
      '.woff': 'font/woff',
      '.woff2': 'font/woff2',
      '.ttf': 'font/ttf',
    };
    return types[ext] || 'application/octet-stream';
  },
  checkIfFileExists: async (filePath: string): Promise<boolean> => {
    try {
      await stat(filePath);
      return true;
    } catch {
      return false;
    }
  },
  getFileContent: async (filePath: string) => {
    try {
      return {
        status: 'success' as const,
        buffer: await readFile(filePath),
      };
    } catch {
      return {
        status: 'error' as const,
        error: 'File not found',
      };
    }
  },
};