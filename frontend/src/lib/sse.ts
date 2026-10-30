export interface SseEvent {
  event: string;
  data: string;
}

/**
 * Incremental Server-Sent Events parser for fetch() bodies (EventSource cannot POST).
 * Feed it decoded text chunks; it returns the complete events seen so far.
 */
export function createSseParser() {
  let buffer = "";
  return (chunk: string): SseEvent[] => {
    buffer += chunk.replace(/\r\n?/g, "\n");
    const events: SseEvent[] = [];
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (!line || line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        let value = colon === -1 ? "" : line.slice(colon + 1);
        if (value.startsWith(" ")) value = value.slice(1);
        if (field === "event") event = value;
        else if (field === "data") data.push(value);
      }
      if (data.length) events.push({ event, data: data.join("\n") });
    }
    return events;
  };
}
