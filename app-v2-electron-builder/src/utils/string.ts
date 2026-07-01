export const utilsString = {
  slugify: (str: string) => {
    return str
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, '') // remove non-word, non-whitespace, non-hyphen characters
      .replace(/[\s_-]+/g, '-') // replace spaces, underscores, and hyphens with a single hyphen
      .replace(/^-+/, '') // trim leading hyphens
      .replace(/-+$/, '') // trim trailing hyphens
      .replace(/:/g, '-'); // replace colons with hyphens
  },
};