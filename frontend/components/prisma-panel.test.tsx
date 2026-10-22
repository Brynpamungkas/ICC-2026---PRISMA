import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import PrismaPanel, { formatCell } from "./prisma-panel";
import { api, ApiError, type Evidence, type QuestionResponse, type HealthResponse } from "../lib/api";

vi.mock("../lib/api", async (original) => ({ ...await original<typeof import("../lib/api")>(), api: {
  tanya: vi.fn(), klarifikasi: vi.fn(), katalog: vi.fn(), kesehatan: vi.fn(), log: vi.fn(),
} }));
// SYNTHETIC fixtures only, never presented as real BPS data.
const session = "11111111-1111-4111-8111-111111111111";
const idLog = "22222222-2222-4222-8222-222222222222";
const item = (code: string): Evidence => ({ candidate: { code, canonical_name: "SYNTHETIC " + code, unit: "%" },
  result: { candidate_code: code, columns: ["nilai"], rows: [[5.25], [1234.5], [null]], structure: "NUMBER", unit: "%", error: null } });
const items = ["A", "B", "C"].map(item);
const ready: HealthResponse = { model: { status: "AVAILABLE", checked_at: "2026-10-19T00:00:00Z", diagnostic_code: null },
  database: { status: "AVAILABLE", checked_at: "2026-10-19T00:00:00Z", diagnostic_code: null } };
function result(kind: "JAWAB" | "TANYA" | "TAHAN" = "JAWAB"): QuestionResponse {
  return { id_sesi: session, id_log: idLog, decision: { decision: kind, answer: kind === "JAWAB" ? items[0] : null,
    evidence: kind === "TANYA" ? items : [], reason_code: kind === "TAHAN" ? "T1" : null,
    suggestion: kind === "TAHAN" ? "SYNTHETIC saran" : null, period_used: kind === "TAHAN" ? null : "2025-09" } };
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((r) => { resolve = r; }); return { promise, resolve }; }
async function start() {
  render(<PrismaPanel />);
  await screen.findByRole("heading", { name: "Masuk sebagai tamu" });
  fireEvent.click(screen.getByRole("button", { name: "Lewati" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(false));
}
async function submit() {
  fireEvent.change(screen.getByLabelText("Pertanyaan"), { target: { value: "SYNTHETIC pertanyaan" } });
  fireEvent.click(screen.getByRole("button", { name: "Kirim pertanyaan" }));
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(crypto, "randomUUID").mockReturnValue(session);
  vi.mocked(api.kesehatan).mockResolvedValue(ready);
  vi.mocked(api.katalog).mockResolvedValue({ indikator: [] });
  vi.mocked(api.tanya).mockResolvedValue(result());
});
afterEach(cleanup);

it("opens the legacy question screen after guest entry without fabricated results", async () => {
  await start();
  expect(screen.queryByRole("heading", { name: "JAWAB" })).toBeNull();
  expect(screen.getByRole("heading", { name: "Halo!" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Contoh pertanyaan" })).toBeTruthy();
  expect(api.tanya).not.toHaveBeenCalled();
});
it("rejects whitespace locally and submits exact session fields only once while pending", async () => {
  await start();
  fireEvent.change(screen.getByLabelText("Pertanyaan"), { target: { value: "   " } });
  fireEvent.click(screen.getByRole("button", { name: "Kirim pertanyaan" }));
  expect(screen.getByText("Tulis pertanyaan terlebih dahulu.")).toBeTruthy();
  expect(api.tanya).not.toHaveBeenCalled();
  const pending = deferred<QuestionResponse>(); vi.mocked(api.tanya).mockReturnValue(pending.promise);
  await submit(); fireEvent.click(screen.getByRole("button", { name: "Kirim pertanyaan" }));
  expect(api.tanya).toHaveBeenCalledTimes(1);
  expect(api.tanya).toHaveBeenCalledWith("SYNTHETIC pertanyaan", session);
  expect(screen.getByText("Pertanyaan sedang diproses.")).toBeTruthy();
  await act(async () => { pending.resolve(result()); });
});
it("shows all numeric rows, unit and actual period without inventing provenance", async () => {
  await start(); await submit();
  await screen.findByRole("heading", { name: "JAWAB" });
  expect(screen.getByText("5,25")).toBeTruthy();
  expect(screen.getByText("1.234,5")).toBeTruthy();
  expect(screen.getByText("Nilai tidak tersedia")).toBeTruthy();
  expect(screen.getByText("2025-09")).toBeTruthy();
  expect(screen.getByText("Sumber rinci belum tersedia pada respons ini.")).toBeTruthy();
  expect(screen.getByText("Cakupan wilayah belum tersedia pada respons ini.")).toBeTruthy();
  expect(screen.getByRole("table").querySelectorAll("tbody tr")).toHaveLength(3);
});
it("shows three candidates, no default choice, confirmation and cancellation", async () => {
  vi.mocked(api.tanya).mockResolvedValue(result("TANYA"));
  await start(); await submit();
  const radios = await screen.findAllByRole("radio");
  expect(radios).toHaveLength(3);
  expect(radios.every((r) => !(r as HTMLInputElement).checked)).toBe(true);
  const confirm = screen.getByRole("button", { name: "Gunakan pilihan" });
  expect(confirm.hasAttribute("disabled")).toBe(true);
  fireEvent.click(radios[1]); fireEvent.click(radios[2]);
  expect((radios[2] as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Batalkan pilihan" }));
  expect(confirm.hasAttribute("disabled")).toBe(true);
  expect(api.klarifikasi).not.toHaveBeenCalled();
});
it("locks clarification, posts original identifiers and keeps original evidence after success", async () => {
  vi.mocked(api.tanya).mockResolvedValue(result("TANYA"));
  const pending = deferred<QuestionResponse>(); vi.mocked(api.klarifikasi).mockReturnValue(pending.promise);
  await start(); await submit(); fireEvent.click((await screen.findAllByRole("radio"))[1]);
  const confirm = screen.getByRole("button", { name: "Gunakan pilihan" });
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(api.klarifikasi).toHaveBeenCalledTimes(1);
  expect(api.klarifikasi).toHaveBeenCalledWith(session, idLog, "B", "2025-09", items[1]);
  expect(screen.getByText("Pilihan sedang diproses.")).toBeTruthy();
  const chosen = result(); chosen.decision.answer = items[1];
  await act(async () => { pending.resolve(chosen); });
  await screen.findByRole("heading", { name: "JAWAB" });
  fireEvent.click(screen.getByText("Lihat bukti klarifikasi asal"));
  expect(within(screen.getByLabelText("Bukti klarifikasi asal")).getAllByRole("table")).toHaveLength(3);
});
it("preserves draft and evidence on conflict, with no automatic retry", async () => {
  vi.mocked(api.tanya).mockResolvedValue(result("TANYA"));
  vi.mocked(api.klarifikasi).mockRejectedValue(new ApiError(409, "HTTP_409", "Pilihan sudah tersimpan."));
  await start(); await submit(); fireEvent.click((await screen.findAllByRole("radio"))[0]);
  fireEvent.click(screen.getByRole("button", { name: "Gunakan pilihan" }));
  await screen.findByRole("alert");
  expect(screen.getAllByRole("radio")).toHaveLength(3);
  expect((screen.getByLabelText("Pertanyaan") as HTMLTextAreaElement).value).toBe("SYNTHETIC pertanyaan");
  expect(api.klarifikasi).toHaveBeenCalledTimes(1);
});
it.each(["T0", "T1", "T2", "T3", "T4", "T5"] as const)("renders %s TAHAN as a domain decision", async (code) => {
  const data = result("TAHAN"); data.decision.reason_code = code;
  vi.mocked(api.tanya).mockResolvedValue(data);
  await start(); await submit();
  await screen.findByRole("heading", { name: "TAHAN" });
  expect(screen.getByText(code)).toBeTruthy();
  expect(screen.getByText("SYNTHETIC saran")).toBeTruthy();
  expect(screen.queryByText("2025-09")).toBeNull();
});
it("keeps UNKNOWN distinct, manual recovery never auto-submits", async () => {
  vi.mocked(api.kesehatan).mockResolvedValueOnce({ ...ready, model: { status: "UNKNOWN", checked_at: null, diagnostic_code: null } });
  render(<PrismaPanel />);
  await screen.findByRole("heading", { name: "Masuk sebagai tamu" });
  fireEvent.click(screen.getByRole("button", { name: "Lewati" }));
  await screen.findByText("Status layanan belum dapat dipastikan.");
  expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Periksa lagi" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(false));
  expect(api.tanya).not.toHaveBeenCalled();
});
it("ignores a stale response after starting a new question", async () => {
  const pending = deferred<QuestionResponse>(); vi.mocked(api.tanya).mockReturnValue(pending.promise);
  await start(); await submit();
  fireEvent.click(screen.getByRole("button", { name: "Pertanyaan baru" }));
  await act(async () => { pending.resolve(result()); });
  expect(screen.queryByRole("heading", { name: "JAWAB" })).toBeNull();
});
it("loads protected log into a keyboard-dismissable dialog and restores focus", async () => {
  vi.mocked(api.log).mockRejectedValue(new ApiError(404, "HTTP_404", "Log tidak ditemukan."));
  await start(); await submit(); await screen.findByRole("heading", { name: "JAWAB" });
  const button = screen.getByRole("button", { name: "Lihat rincian proses" });
  const user = userEvent.setup(); await user.click(button);
  await screen.findByRole("dialog");
  expect(api.log).toHaveBeenCalledWith(idLog, session);
  await screen.findByText("Log tidak ditemukan.");
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(button);
  expect(screen.getByRole("heading", { name: "JAWAB" })).toBeTruthy();
});
it("uses real catalog metadata and searches without fabricated domain mappings", async () => {
  vi.mocked(api.katalog).mockResolvedValue({ indikator: [{ kode: "SYNTHETIC", nama_kanonik: "SYNTHETIC metadata", definisi_resmi: "SYNTHETIC definition",
    satuan: "%", sumber: "SYNTHETIC source", periode_tersedia: ["2025"], cakupan_wilayah: ["SYNTHETIC region"] }] });
  await start(); fireEvent.click(screen.getByRole("button", { name: "Katalog Data" }));
  await screen.findByText("SYNTHETIC metadata");
  fireEvent.change(screen.getByLabelText("Cari indikator"), { target: { value: "no match" } });
  expect(screen.getByText("Belum ada indikator yang cocok.")).toBeTruthy();
});
it("formats full original precision without percentage multiplication", () => {
  expect(formatCell(1234.5)).toBe("1.234,5");
  expect(formatCell(5.25)).toBe("5,25");
  expect(formatCell(1.23456789012345)).toBe("1,23456789012345");
  expect(formatCell(null)).toBe("Nilai tidak tersedia");
});

it("requires a fresh health check after service failure while preserving the draft", async () => {
  vi.mocked(api.tanya).mockRejectedValue(new ApiError(503, "HTTP_503", "Layanan belum tersedia."));
  await start(); await submit(); await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(true);
  expect((screen.getByLabelText("Pertanyaan") as HTMLTextAreaElement).value).toBe("SYNTHETIC pertanyaan");
  fireEvent.click(screen.getByRole("button", { name: "Periksa lagi" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(false));
  expect(api.tanya).toHaveBeenCalledTimes(1);
});
it("renders recorded log fields without invented timings, preserving the result", async () => {
  vi.mocked(api.log).mockResolvedValue({ id_log: idLog, record: { run_id: "synthetic-run", session_id: session,
    question: "SYNTHETIC pertanyaan", extraction: null, k: ["A"], k_prime: ["A"], skeletons: [],
    votes: [], decision: result().decision, mode: "K3", latency_ms: {}, model_name: "SYNTHETIC model",
    prompt_version: null, dictionary_hash: null } });
  await start(); await submit(); await screen.findByRole("heading", { name: "JAWAB" });
  fireEvent.click(screen.getByRole("button", { name: "Lihat rincian proses" }));
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText("SYNTHETIC model");
  expect(within(dialog).getAllByText("Tidak tercatat.").length).toBeGreaterThan(0);
  expect(within(dialog).queryByText("0 ms")).toBeNull();
  expect(screen.getByRole("heading", { name: "JAWAB" })).toBeTruthy();
});


it("restores the guest entry and keeps local profile fields out of API requests", async () => {
  render(<PrismaPanel />);
  await screen.findByRole("heading", { name: "Masuk sebagai tamu" });
  fireEvent.change(screen.getByLabelText(/Nama panggilan/), { target: { value: "SYNTHETIC guest" } });
  fireEvent.change(screen.getByLabelText(/Kode peserta studi/), { target: { value: "SYNTHETIC participant" } });
  fireEvent.click(screen.getByRole("button", { name: "Pendidikan" }));
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Mulai bertanya" }));
  await screen.findByRole("heading", { name: "Halo, SYNTHETIC guest!" });
  expect(screen.getByText("Minatmu")).toBeTruthy();
  await waitFor(() => expect(screen.getByRole("button", { name: "Kirim pertanyaan" }).hasAttribute("disabled")).toBe(false));
  await submit();
  expect(api.tanya).toHaveBeenCalledWith("SYNTHETIC pertanyaan", session);
  expect(JSON.stringify(vi.mocked(api.tanya).mock.calls)).not.toContain("SYNTHETIC participant");
});
it("restores the original about layout and accurately explains mandatory local logging", async () => {
  await start();
  fireEvent.click(screen.getByRole("button", { name: "Tentang" }));
  expect(screen.getByRole("heading", { name: /Satu pertanyaan, semua tafsir/ })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Tujuh langkah di balik setiap jawaban" })).toBeTruthy();
  expect(screen.queryByText("Log anonim hanya dicatat jika kamu menyetujuinya di awal.")).toBeNull();
});
