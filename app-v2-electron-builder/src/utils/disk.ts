import { readFile, writeFile } from "node:fs/promises";

export const utilsDisk = {
  replaceTextInFile: async ({
    filePath,
    toReplaceRegexp,
    replaceWithText,
  }: {
    filePath: string;
    toReplaceRegexp: RegExp;
    replaceWithText: string;
  }) => {
    const fileContent = await readFile(filePath, "utf8");
    const newFileContent = fileContent.replace(toReplaceRegexp, replaceWithText);
    await writeFile(filePath, newFileContent);
  },
};