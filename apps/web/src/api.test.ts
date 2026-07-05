import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDashboardSync } from "./api";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const provider = {
  configured: true,
  mode: "live",
  text_model: "qwen3.7-plus",
  vision_model: "qwen3-vl-plus",
};

const proof = {
  provider: "qwen-cloud",
  verified: true,
  model: "qwen3.7-plus",
  base_url: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
  provider_request_id: "chatcmpl-proof",
  latency_ms: 142,
  response_sha256: "a".repeat(64),
  verified_at: "2026-07-05T01:30:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchDashboardSync", () => {
  it("starts provider and proof requests together and returns verified proof", async () => {
    let resolveProvider: (response: Response) => void = () => undefined;
    let resolveProof: (response: Response) => void = () => undefined;
    const fetchMock = vi.fn((url: string) => {
      return new Promise<Response>((resolve) => {
        if (url.endsWith("/api/qwen/status")) {
          resolveProvider = resolve;
        } else {
          resolveProof = resolve;
        }
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const resultPromise = fetchDashboardSync();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    resolveProvider(jsonResponse(provider));
    resolveProof(jsonResponse(proof));

    const result = await resultPromise;
    expect(result.proofState).toBe("verified");
    expect(result.proof?.provider_request_id).toBe("chatcmpl-proof");
  });

  it("treats a missing receipt as not verified", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(provider))
        .mockResolvedValueOnce(jsonResponse({ code: "not_found" }, 404)),
    );

    const result = await fetchDashboardSync();

    expect(result.provider.mode).toBe("live");
    expect(result.proof).toBeNull();
    expect(result.proofState).toBe("not-verified");
  });

  it("keeps provider status when proof storage is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(provider))
        .mockResolvedValueOnce(jsonResponse({ code: "unavailable" }, 503)),
    );

    const result = await fetchDashboardSync();

    expect(result.provider.mode).toBe("live");
    expect(result.proof).toBeNull();
    expect(result.proofState).toBe("unavailable");
  });
});
