import fs from "node:fs";

// main class

export class Logger {
  key: string;
  color: Color;
  transports: LoggerTransport[];
  constructor({
    key,
    color,
    transports,
  }: {
    key: string;
    color: Color;
    transports: LoggerTransport[],
  }) {
    this.key = key;
    this.color = color;
    this.transports = transports;
  }
  get keyNice() {
    return color[this.color](`[${this.key}]`);
  }
  log(...args: Parameters<typeof console.log>) {
    const parts = [this.keyNice, ...args];
    this.transports.forEach(t => t.printLog(...parts));
  }
  error(...args: Parameters<typeof console.error>) {
    const parts = [this.keyNice, ...args];
    this.transports.forEach(t => t.printLog(...parts));
  }
}

// sub classes

export type LoggerTransport = {
  printLog: (...args: Parameters<typeof console.log>) => void;
};

export class LoggerTransportConsole implements LoggerTransport {
  printLog(...args: Parameters<typeof console.log>) {
    console.log(...args);
  }
}
export class LoggerTransportFile implements LoggerTransport {
  filePath: string;
  constructor(filePath: string) {
    this.filePath = filePath;
  }
  printLog(...args: Parameters<typeof console.log>) {
    // print to file (append)
    fs.appendFileSync(this.filePath, args.join(' ') + '\n');
  }
}

// utils
const color = {
  red: (s: string) => `\x1b[31m${s}\x1b[0m`,
  green: (s: string) => `\x1b[32m${s}\x1b[0m`,
  yellow: (s: string) => `\x1b[33m${s}\x1b[0m`,
  blue: (s: string) => `\x1b[34m${s}\x1b[0m`,
  cyan: (s: string) => `\x1b[36m${s}\x1b[0m`,
  bold: (s: string) => `\x1b[1m${s}\x1b[0m`,
};

type Color = keyof typeof color;
