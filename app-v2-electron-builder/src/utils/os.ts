import type { Logger } from "./logger";

export class UtilsOs {
  logger: Logger;
  constructor({ logger }: { logger: Logger; }) {
    this.logger = logger;
  }
  /**
   * Waits for a service to be ready on the given URL.
   */
  async waitForService(url: string, maxAttempts = 30): Promise<boolean> {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        await fetch(url);
        this.logger.log(`✓ Service ready at ${url}`);
        return true;
      } catch {
        this.logger.log(`⏳ Waiting for ${url}... (${i + 1}/${maxAttempts})`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    return false;
  }
};
