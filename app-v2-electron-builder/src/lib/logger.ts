import fs from "node:fs";
import path from "node:path";

// main class

export class Logger {
  key: string;
  transports: LoggerTransport[];
  constructor({
    key,
    transports,
  }: {
    key: string;
    transports: LoggerTransport[],
  }) {
    this.key = key;
    this.transports = transports;
  }

  get keyNice() {
    return `[${this.key}]`;
  }
  log(...args: Parameters<typeof console.log>) {
    this.transports.forEach(t => t.printLog(this.keyNice, ...args));
  }
  error(...args: Parameters<typeof console.error>) {
    this.transports.forEach(t => t.printLog(this.keyNice, ...args));
  }
}

// sub classes

export type LoggerTransport = {
  printLog: (key: string, ...args: Parameters<typeof console.log>) => void;
};

export class LoggerTransportConsole implements LoggerTransport {
  color: Color;
  constructor({
    color
  }: {
    color: Color;
  }) {
    this.color = color;
  }
  printLog(key: string, ...args: Parameters<typeof console.log>) {
    const keyNice = color[this.color](key);
    const parts = [keyNice, ...args];
    console.log(...parts);
  }
}
export class LoggerTransportFile implements LoggerTransport {
  filePath: string;
  constructor(filePath: string) {
    this.filePath = filePath;
    this.createDirIfNotExists();
  }
  printLog(key: string, ...args: Parameters<typeof console.log>) {
    const parts = [key, ...args];
    fs.appendFileSync(this.filePath, parts.join(' ') + '\n');
  }
  private createDirIfNotExists() {
    const dirPath = path.dirname(this.filePath);
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
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
