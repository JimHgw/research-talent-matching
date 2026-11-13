type Guard<T> = (value: unknown) => value is T;
type Shape = Record<string, Guard<unknown>>;

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export const string = (value: unknown): value is string => typeof value === 'string';
export const id = (value: unknown): value is string =>
  string(value) && /^[A-Za-z0-9_-]{1,64}$/.test(value);
export const revision = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
export const dateTime = (value: unknown): value is string =>
  string(value) && Number.isFinite(Date.parse(value));

export function nullable<T>(guard: Guard<T>): Guard<T | null> {
  return (value): value is T | null => value === null || guard(value);
}

export function optional<T>(guard: Guard<T>): Guard<T | undefined> {
  return (value): value is T | undefined => value === undefined || guard(value);
}

export function arrayOf<T>(guard: Guard<T>): Guard<T[]> {
  return (value): value is T[] => Array.isArray(value) && value.every(guard);
}

export function oneOf<const T extends string | number | boolean>(...options: T[]): Guard<T> {
  return (value): value is T => options.some((option) => option === value);
}

export function numberBetween(min: number, max: number): Guard<number> {
  return (value): value is number =>
    typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

export function objectOf<T extends Shape>(fields: T) {
  return (value: unknown): value is { [K in keyof T]: T[K] extends Guard<infer V> ? V : never } =>
    isObject(value) && Object.entries(fields).every(([key, guard]) => guard(value[key]));
}

export type Validated<T> = T extends Guard<infer Value> ? Value : never;
