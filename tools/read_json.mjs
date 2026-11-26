import { closeSync, constants, fstatSync, openSync, readSync } from "node:fs";

function rejectDuplicateKeys(text) {
  // JSON.parse has already checked the grammar. A colon outside a string
  // always follows a key in the current object, even inside an array.
  const objects = [];
  let string;
  for (const [token] of text.matchAll(/"(?:[^"\\]|\\[\s\S])*"|[{}:]/g)) {
    if (token === "{") objects.push(new Set());
    else if (token === "}") objects.pop();
    else if (token === ":") {
      const key = JSON.parse(string);
      const keys = objects.at(-1);
      if (keys.has(key)) throw Error("DUPLICATE_JSON_KEY");
      keys.add(key);
    } else {
      string = token;
    }
  }
}

export function readUtf8(path, limit) {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NONBLOCK);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile()) throw Error("JSON_INPUT_NOT_REGULAR_FILE");
    if (stat.size > limit) throw Error("JSON_INPUT_TOO_LARGE");

    // A file can grow after fstat. Bound reads independently of its size.
    const buffer = Buffer.alloc(limit + 1);
    let size = 0;
    while (size < buffer.length) {
      const count = readSync(fd, buffer, size, buffer.length - size, null);
      if (count === 0) break;
      size += count;
    }
    if (size > limit) throw Error("JSON_INPUT_TOO_LARGE");
    try {
      return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(buffer.subarray(0, size));
    } catch {
      throw Error("INVALID_UTF8_INPUT");
    }
  } finally {
    closeSync(fd);
  }
}

export function readJson(path, limit) {
  const text = readUtf8(path, limit);
  let value;
  try {
    value = JSON.parse(text);
  } catch {
    throw Error("INVALID_JSON_INPUT");
  }
  rejectDuplicateKeys(text);
  return value;
}
