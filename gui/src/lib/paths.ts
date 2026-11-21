function isAbsolutePath(path: string): boolean {
  return /^[a-zA-Z]:[\\/]/.test(path) || path.startsWith("\\\\") || path.startsWith("/");
}

/** Resolves `target` against `baseDir` using Windows path conventions. Pure/sync so it can run inside render. */
export function resolveRelativePath(baseDir: string, target: string): string {
  if (isAbsolutePath(target)) {
    return target;
  }

  const parts = baseDir.split(/[\\/]/).filter(Boolean);
  for (const segment of target.split(/[\\/]/).filter(Boolean)) {
    if (segment === ".") continue;
    if (segment === "..") {
      if (parts.length > 1) parts.pop();
    } else {
      parts.push(segment);
    }
  }

  if (parts.length === 0) return baseDir;
  let result = parts[0];
  for (let i = 1; i < parts.length; i++) {
    result += "\\" + parts[i];
  }
  if (/^[a-zA-Z]:$/.test(result)) {
    result += "\\";
  }
  return result;
}

export function hasUriScheme(path: string): boolean {
  return !isAbsolutePath(path) && /^[a-z][a-z0-9+.-]*:/i.test(path);
}

export { isAbsolutePath };
