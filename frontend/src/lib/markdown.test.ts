import { describe, expect, it } from "vitest";
import { parseInline } from "./markdown";

describe("parseInline", () => {
  it("splits Lighthouse descriptions into text, links and code", () => {
    expect(parseInline("Use `srcset`. [Learn more](https://web.dev/x).")).toEqual([
      { kind: "text", text: "Use " },
      { kind: "code", text: "srcset" },
      { kind: "text", text: ". " },
      { kind: "link", text: "Learn more", href: "https://web.dev/x" },
      { kind: "text", text: "." },
    ]);
  });
  it("never turns non-http links into links", () => {
    expect(parseInline("[x](javascript:alert(1))")).toEqual([{ kind: "text", text: "[x](javascript:alert(1))" }]);
  });
  it("passes plain text through", () => {
    expect(parseInline("plain")).toEqual([{ kind: "text", text: "plain" }]);
    expect(parseInline("")).toEqual([]);
  });
});
