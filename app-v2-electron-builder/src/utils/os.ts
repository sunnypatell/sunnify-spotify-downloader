import { createServer } from "node:net";

export const utilsOs = {
  getOSInfo() {
    return {
      platform: process.platform,
      arch: process.arch,
    };
  },
  /**
   * Waits for a service to be ready on the given URL.
   */
  async waitForService(url: string, maxAttempts = 50): Promise<boolean> {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        await fetch(url);
        console.log(`✓ Service ready at ${url}`);
        return true;
      } catch {
        console.log(`⏳ Waiting for ${url}... (${i + 1}/${maxAttempts})`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    return false;
  },

  /**
   * Get a free port on localhost
   */
  async getFreePort() {
    return new Promise<number>((resolve, reject) => {
      const server = createServer();
      server.listen(
        0,
        () => {
          const address = server.address();
          if (!address || typeof address === "string") {
            reject(new Error("Unable to get port"));
            return;
          }
          const port = address.port;
          server.close(() => resolve(port));
        }
      );
      server.on("error", reject);
    });
  },
};
