import { describe, expect, it } from "vitest";

import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("parses named events across chunk boundaries and CRLF line endings", () => {
    const parse = createSseParser();
    expect(parse('event: text\r\ndata: {"type":"text","del')).toEqual([]);
    expect(parse('ta":"Hi"}\r\n\r\nevent: done\r\ndata: {"type":"done"}\r\n\r\n')).toEqual([
      { event: "text", data: '{"type":"text","delta":"Hi"}' },
      { event: "done", data: '{"type":"done"}' },
    ]);
  });

  it("ignores comments and joins multi-line data", () => {
    const parse = createSseParser();
    expect(parse(": ping\n\ndata: a\ndata: b\n\n")).toEqual([{ event: "message", data: "a\nb" }]);
  });
});
