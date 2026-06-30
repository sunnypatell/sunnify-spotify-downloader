export class Time {
  inMs: number;
  constructor(inMs: number) {
    this.inMs = inMs;
  }
  asMs() { return this.inMs; }
  asSs() { return Math.floor(this.inMs / 1000); }
  asMMSS() {
    const fullSeconds = this.asSs();
    const mm = Math.floor(fullSeconds / 60);
    const ss = Math.floor(fullSeconds % 60);
    return {
      parts: { mm, ss },
      full: {
        /** time in seconds  @example 2, 62, 340 */
        asSeconds: fullSeconds,
        /** time as "XX:XX" @example "00:02", "10:02", "02:00" */
        asString: `${mm.toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`,
        /**  time as "XXm XXs" or "XXs" @example "2s", "10m 2s" */
        asStringNice: (
          fullSeconds < 60
            ? `${ss}s`
            : `${mm}m ${ss.toString().padStart(2, "0")}s`
        )
      },
    };
  }
}

