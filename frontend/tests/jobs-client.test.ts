import { expect, test } from "vitest"

import {
  activateJob,
  archiveJob,
  closeJob,
  createJob,
  type JobsTransport,
  JobsTransportError,
  type JobsTransportResponse,
  loadJobDetail,
  loadJobs,
  updateJob,
  uploadJobMaterial,
} from "../src/lib/jobs-client"

const jobBody = {
  id: "job-1",
  company_id: "company-1",
  title: "高级后端工程师",
  description: "负责 API",
  status: "draft",
  created_at: "2026-08-06T12:00:00+00:00",
  updated_at: "2026-08-06T12:00:00+00:00",
  archived_at: null,
} as const

const materialBody = {
  id: "material-1",
  job_id: "job-1",
  original_filename: "jd.txt",
  content_type: "text/plain",
  byte_size: 12,
  sha256: "0".repeat(64),
  extracted_text: "职位描述",
  scan_status: "content_checked",
  uploaded_by: null,
  created_at: "2026-08-06T12:00:00+00:00",
} as const

class ScriptedJobsTransport implements JobsTransport {
  readonly #handler: () => Promise<JobsTransportResponse>

  constructor(handler: () => Promise<JobsTransportResponse>) {
    this.#handler = handler
  }

  list(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  get(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  create(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  update(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  activate(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  close(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  archive(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  listMaterials(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  uploadMaterial(): Promise<JobsTransportResponse> {
    return this.#handler()
  }

  listEvents(): Promise<JobsTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: JobsTransportResponse): JobsTransport {
  return new ScriptedJobsTransport(() => Promise.resolve(response))
}

test("parses the job list on success", async () => {
  const result = await loadJobs(fixedTransport({ body: [jobBody], status: 200 }), "s", {})
  expect(result).toEqual({ kind: "ok", jobs: [jobBody] })
})

test("parses job detail with materials and events", async () => {
  const responses = [
    { body: jobBody, status: 200 },
    { body: [materialBody], status: 200 },
    { body: [], status: 200 },
  ]
  let index = 0
  const transport = new ScriptedJobsTransport(() => {
    const response = responses[index] ?? { body: null, status: 500 }
    index += 1
    return Promise.resolve(response)
  })
  const result = await loadJobDetail(transport, "s", "job-1")
  expect(result).toEqual({ kind: "ok", job: jobBody, materials: [materialBody], events: [] })
})

test("maps create conflict when company archived", async () => {
  const result = await createJob(
    fixedTransport({ body: { detail: "company_archived" }, status: 409 }),
    "s",
    { company_id: "company-1", title: "新职位" },
  )
  expect(result).toEqual({ kind: "companyArchived" })
})

test("maps activation quota exceeded", async () => {
  const result = await activateJob(
    fixedTransport({ body: { detail: "job_quota_exceeded" }, status: 409 }),
    "s",
    "job-1",
  )
  expect(result).toEqual({ kind: "quotaExceeded" })
})

test("maps activation status conflict", async () => {
  const result = await activateJob(
    fixedTransport({ body: { detail: "job_status_conflict" }, status: 409 }),
    "s",
    "job-1",
  )
  expect(result).toEqual({ kind: "statusConflict" })
})

test("maps update on non-draft job", async () => {
  const result = await updateJob(
    fixedTransport({ body: { detail: "job_not_draft" }, status: 409 }),
    "s",
    "job-1",
    { title: "改名" },
  )
  expect(result).toEqual({ kind: "notDraft" })
})

test("maps close on archived job", async () => {
  const result = await closeJob(
    fixedTransport({ body: { detail: "job_status_conflict" }, status: 409 }),
    "s",
    "job-1",
  )
  expect(result).toEqual({ kind: "statusConflict" })
})

test("maps not found on archive", async () => {
  const result = await archiveJob(fixedTransport({ body: null, status: 404 }), "s", "job-1")
  expect(result).toEqual({ kind: "notFound" })
})

test("parses uploaded material on success", async () => {
  const result = await uploadJobMaterial(
    fixedTransport({ body: materialBody, status: 201 }),
    "s",
    "job-1",
    new Blob(["jd"]),
    "jd.txt",
  )
  expect(result).toEqual({ kind: "ok", material: materialBody })
})

test("maps material validation failure", async () => {
  const result = await uploadJobMaterial(
    fixedTransport({ body: { detail: "invalid_document" }, status: 400 }),
    "s",
    "job-1",
    new Blob(["x"]),
    "jd.exe",
  )
  expect(result).toEqual({ kind: "invalidDocument" })
})

test("maps oversized material", async () => {
  const result = await uploadJobMaterial(
    fixedTransport({ body: { detail: "document_too_large" }, status: 413 }),
    "s",
    "job-1",
    new Blob(["x"]),
    "big.txt",
  )
  expect(result).toEqual({ kind: "tooLarge" })
})

test("maps read only subscription", async () => {
  const result = await loadJobs(
    fixedTransport({ body: { detail: "subscription_read_only" }, status: 403 }),
    "s",
    {},
  )
  expect(result).toEqual({ kind: "readOnly" })
})

test("maps anonymous access", async () => {
  const result = await loadJobs(fixedTransport({ body: null, status: 401 }), "s", {})
  expect(result).toEqual({ kind: "anonymous" })
})

test("returns unreachable when transport fails", async () => {
  const transport = new ScriptedJobsTransport(() => Promise.reject(new JobsTransportError("down")))
  const result = await loadJobs(transport, "s", {})
  expect(result).toEqual({ kind: "unreachable" })
})

test("returns unreachable when body fails schema validation", async () => {
  const result = await loadJobs(fixedTransport({ body: { nope: true }, status: 200 }), "s", {})
  expect(result).toEqual({ kind: "unreachable" })
})
