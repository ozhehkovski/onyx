import {
  DEFAULT_SESSION_FILTERS,
  buildSessionExportUrl,
  buildSessionsExportUrl,
  buildSessionsUrl,
  buildUserChatExportUrl,
  defaultExportFilename,
  filenameFromContentDisposition,
  isSessionFeedbackFilter,
  rangeToDateParams,
} from "@/lib/chat-insights/utils";

describe("rangeToDateParams", () => {
  it("formats inclusive calendar days", () => {
    expect(
      rangeToDateParams({
        from: new Date(2026, 8, 24, 0, 0, 0),
        to: new Date(2026, 8, 30, 23, 59, 59, 999),
      })
    ).toEqual({ start: "2026-09-24", end: "2026-09-30" });
  });

  it("omits bounds for an unset range", () => {
    expect(rangeToDateParams(undefined)).toEqual({
      start: undefined,
      end: undefined,
    });
  });
});

describe("buildSessionsUrl", () => {
  it("drops default filters and keeps paging", () => {
    expect(buildSessionsUrl(DEFAULT_SESSION_FILTERS, 0)).toBe(
      "/api/admin/chat-insights/sessions?page=0&page_size=25"
    );
  });

  it("encodes every active filter", () => {
    expect(
      buildSessionsUrl(
        {
          start: "2026-09-01",
          end: "2026-09-30",
          feedback: "negative",
          userEmail: "  a+b@example.com ",
          personaId: 3,
          q: "hello world",
        },
        2,
        50
      )
    ).toBe(
      "/api/admin/chat-insights/sessions?start=2026-09-01&end=2026-09-30" +
        "&feedback=negative&user_email=a%2Bb%40example.com&persona_id=3" +
        "&q=hello%20world&page=2&page_size=50"
    );
  });
});

describe("export URLs", () => {
  it("builds the bulk export URL with filters and no paging", () => {
    expect(
      buildSessionsExportUrl(
        { ...DEFAULT_SESSION_FILTERS, feedback: "mixed", q: "x" },
        "csv"
      )
    ).toBe("/api/admin/chat-insights/export?format=csv&feedback=mixed&q=x");
  });

  it("builds the single-session export URL", () => {
    expect(buildSessionExportUrl("abc-123", "json")).toBe(
      "/api/admin/chat-insights/sessions/abc-123/export?format=json"
    );
  });

  it("builds the user self-export URL", () => {
    expect(buildUserChatExportUrl("csv")).toBe(
      "/api/user/chat-export?format=csv"
    );
  });
});

describe("filenameFromContentDisposition", () => {
  const fallback = "fallback.json";

  it("reads a quoted file name", () => {
    expect(
      filenameFromContentDisposition(
        'attachment; filename="onyx-chats-20260930-101500.csv"',
        fallback
      )
    ).toBe("onyx-chats-20260930-101500.csv");
  });

  it("reads an unquoted file name", () => {
    expect(
      filenameFromContentDisposition("attachment; filename=a.json", fallback)
    ).toBe("a.json");
  });

  it("prefers the RFC 5987 form", () => {
    expect(
      filenameFromContentDisposition(
        "attachment; filename=\"plain.csv\"; filename*=UTF-8''czat%20%C5%BC.csv",
        fallback
      )
    ).toBe("czat ż.csv");
  });

  it("falls back when the header is missing or has no name", () => {
    expect(filenameFromContentDisposition(null, fallback)).toBe(fallback);
    expect(filenameFromContentDisposition("attachment", fallback)).toBe(
      fallback
    );
  });
});

describe("defaultExportFilename", () => {
  it("stamps the UTC time", () => {
    expect(
      defaultExportFilename("json", new Date(Date.UTC(2026, 0, 2, 3, 4, 5)))
    ).toBe("onyx-chats-20260102-030405.json");
  });
});

describe("isSessionFeedbackFilter", () => {
  it("accepts known filters only", () => {
    expect(isSessionFeedbackFilter("mixed")).toBe(true);
    expect(isSessionFeedbackFilter("bogus")).toBe(false);
  });
});
