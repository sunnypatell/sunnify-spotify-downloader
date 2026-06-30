export const isNull = (value: unknown): value is null => value === null;
export const isUndefined = (value: unknown): value is undefined => typeof value === 'undefined';
export const isNullOrUndefined = (value: unknown): value is null | undefined => isNull(value) || isUndefined(value);