import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

// All values in these fixtures are SYNTHETIC; they are not BPS observations.
const session = "11111111-1111-4111-8111-111111111111";
const idLog = "22222222-2222-4222-8222-222222222222";
const evidence = (code = "SYNTHETIC_A") => ({
  candidate: { code, canonical_name: code, unit: "%" },
  result: { candidate_code: code, columns: ["nilai"], rows: [[5.25]], structure: "NUMBER" as const, unit: "%", error: null },
});
const answer = () => ({ id_sesi: session, id_log: idLog, decision: {
  decision: "JAWAB", answer: evidence(), evidence: [] as ReturnType<typeof evidence>[], reason_code: null, suggestion: null, period_used: "2025-09",
}});
function respond(data: unknown, status = 200) {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(data), { status }));
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());

describe("API boundary", () => {
  it("accepts wilayah text labels on NUMBER lookups but not text values", async () => {
    const data = answer();
    Object.assign(data.decision.answer.result, { columns: ["wilayah", "nilai"], rows: [["SYNTHETIC", 5.25]] });
    respond(data);
    expect((await api.tanya("SYNTHETIC question", session)).decision.answer?.result.rows).toEqual([["SYNTHETIC", 5.25]]);
    (data.decision.answer.result.rows as unknown[][])[0][1] = "5,25";
    respond(data);
    await expect(api.tanya("SYNTHETIC question", session)).rejects.toBeInstanceOf(ApiError);
  });
  it("posts exactly the approved fields to a relative URL without caching", async () => {
    const fetcher = respond(answer());
    const result = await api.tanya("SYNTHETIC question", session);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("/api/tanya");
    expect(JSON.parse(init.body)).toEqual({ pertanyaan: "SYNTHETIC question", id_sesi: session });
    expect(init.cache).toBe("no-store");
    expect(result.decision.answer?.result.rows).toEqual([[5.25]]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each(["session", "uuid", "shape", "branch", "numeric", "candidate", "duplicate"])("rejects malformed or uncorrelated %s responses", async (fault) => {
    const data = answer();
    if (fault === "session") data.id_sesi = "33333333-3333-4333-8333-333333333333";
    if (fault === "uuid") data.id_log = "not-a-uuid";
    if (fault === "shape") data.decision.answer.result.rows = [[1, 2]];
    if (fault === "branch") data.decision.evidence = [evidence()];
    if (fault === "numeric") (data.decision.answer.result.rows as unknown[][])[0][0] = "5,25";
    if (fault === "candidate") data.decision.answer.result.candidate_code = "OTHER";
    if (fault === "duplicate") Object.assign(data.decision, { decision: "TANYA", answer: null, evidence: [evidence(), evidence()] });
    respond(data);
    await expect(api.tanya("SYNTHETIC", session)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("preserves all TANYA evidence and null SQL cells", async () => {
    const data = answer();
    const items = ["SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"].map(evidence);
    (items[0].result.rows as (number | null)[][])[0][0] = null;
    Object.assign(data.decision, { decision: "TANYA", answer: null, evidence: items });
    respond(data);
    const result = await api.tanya("SYNTHETIC", session);
    expect(result.decision.evidence).toHaveLength(3);
    expect(result.decision.evidence[0].result.rows[0][0]).toBeNull();
  });
  it("sends the session in the log header, never in a query", async () => {
    const fetcher = respond({});
    await expect(api.log(idLog, session)).rejects.toBeInstanceOf(ApiError);
    expect(fetcher.mock.calls[0][0]).toBe("/api/log/" + idLog);
    expect(fetcher.mock.calls[0][1].headers["X-Session-ID"]).toBe(session);
  });
  it("uses health payload on HTTP 503 and never treats UNKNOWN as available", async () => {
    respond({ model: { status: "UNKNOWN", checked_at: null, diagnostic_code: null },
      database: { status: "UNAVAILABLE", checked_at: "2026-10-19T00:00:00+00:00", diagnostic_code: "DATABASE_UNAVAILABLE" } }, 503);
    expect((await api.kesehatan()).model.status).toBe("UNKNOWN");
  });
  it("rejects AVAILABLE health without a real check timestamp", async () => {
    respond({ model: { status: "AVAILABLE", checked_at: null }, database: { status: "AVAILABLE", checked_at: null } });
    await expect(api.kesehatan()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("checks clarification candidate, period and log correlation", async () => {
    const data = answer(); data.decision.period_used = "2024";
    respond(data);
    await expect(api.klarifikasi(session, idLog, "SYNTHETIC_A", "2025-09", evidence())).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("does not retry POST or expose arbitrary server error text", async () => {
    const fetcher = respond({ error: { code: "INTERNAL_ERROR", message: "SECRET TRACE /private/path" } }, 500);
    await expect(api.tanya("SYNTHETIC", session)).rejects.toMatchObject({ status: 500, code: "HTTP_500" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    try { await api.tanya("SYNTHETIC", session); } catch (error) { expect(String(error)).not.toContain("SECRET"); }
  });
  it("handles invalid JSON and network errors safely", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>SECRET</html>")));
    await expect(api.tanya("SYNTHETIC", session)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("SECRET network path")));
    await expect(api.tanya("SYNTHETIC", session)).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
  it("validates catalog metadata instead of accepting the old mock array", async () => {
    respond([{ nama: "SYNTHETIC" }]);
    await expect(api.katalog()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
});

it("rejects a 503 health response that falsely declares both services available", async () => {
  const service = { status: "AVAILABLE", checked_at: "2026-10-19T00:00:00Z", diagnostic_code: null };
  respond({ model: service, database: service }, 503);
  await expect(api.kesehatan()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
it.each(["candidate", "log", "branch", "evidence"])("rejects clarification with mismatched %s", async (fault) => {
  const data = answer();
  if (fault === "candidate") data.decision.answer = evidence("SYNTHETIC_B");
  if (fault === "log") data.id_log = "33333333-3333-4333-8333-333333333333";
  if (fault === "branch") Object.assign(data.decision, { decision: "TANYA", answer: null, evidence: [evidence(), evidence("SYNTHETIC_B")] });
  if (fault === "evidence") data.decision.answer.result.rows = [[999]];
  respond(data);
  await expect(api.klarifikasi(session, idLog, "SYNTHETIC_A", "2025-09", evidence())).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
it("reads an actual LogRecord shape and rejects another session", async () => {
  const record = { run_id: "synthetic-run", session_id: session, question: "SYNTHETIC question",
    extraction: null, k: ["SYNTHETIC_A"], k_prime: ["SYNTHETIC_A"], skeletons: [], votes: [],
    decision: answer().decision, mode: "K3", latency_ms: {}, model_name: null, prompt_version: null, dictionary_hash: null };
  respond({ id_log: idLog, record });
  expect((await api.log(idLog, session)).record.latency_ms).toEqual({});
  respond({ id_log: idLog, record: { ...record, session_id: "33333333-3333-4333-8333-333333333333" } });
  await expect(api.log(idLog, session)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
