import { FetchError, type ErrorResponseBody } from "@/lib/fetcher";
import {
  defaultExportFilename,
  filenameFromContentDisposition,
} from "@/lib/chat-insights/utils";
import type { ExportFormat } from "@/lib/chat-insights/types";

async function readErrorBody(res: Response): Promise<ErrorResponseBody | null> {
  try {
    const body: unknown = await res.json();
    return typeof body === "object" && body !== null ? body : null;
  } catch {
    // Non-JSON error body: the status code alone describes the failure.
    return null;
  }
}

/**
 * Fetches an export endpoint and saves the response as a file. Throws a
 * `FetchError` with the HTTP status when the server refuses the export.
 */
export async function downloadExport(
  url: string,
  format: ExportFormat
): Promise<void> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    const info = await readErrorBody(res);
    throw new FetchError(
      info?.detail ?? `Export failed with status ${res.status}`,
      res.status,
      info
    );
  }

  const blob = await res.blob();
  const filename = filenameFromContentDisposition(
    res.headers.get("Content-Disposition"),
    defaultExportFilename(format)
  );

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
