"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { z } from "zod"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { cancelSubscription, createOrdersTransport, submitOrder } from "@/lib/orders-client"

const orderFormFields = [
  "plan_code",
  "amount",
  "payment_reference",
  "payer_note",
  "idempotency_key",
] as const

export type OrderFormField = (typeof orderFormFields)[number]

export type SubmitOrderFormState = {
  readonly fieldErrors: Readonly<Partial<Record<OrderFormField, string>>>
  readonly formError: string | null
  readonly submitted: boolean
}

export type CancelSubscriptionActionState = {
  readonly formError: string | null
}

const orderFormSchema = z.object({
  plan_code: z.string().trim().min(1, "请选择套餐"),
  amount: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, "金额需为数字，最多两位小数")
    .refine((value) => Number(value) > 0, "金额必须大于 0"),
  payment_reference: z.string().trim().min(1, "请输入付款凭证号"),
  payer_note: z.string().trim(),
  idempotency_key: z.string().uuid("订单标识无效，请刷新页面后重试"),
})

const idleSubmitState: SubmitOrderFormState = {
  fieldErrors: {},
  formError: null,
  submitted: false,
}

function isOrderFormField(value: unknown): value is OrderFormField {
  return typeof value === "string" && (orderFormFields as readonly string[]).includes(value)
}

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

async function requireSession(): Promise<string> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    redirect("/login")
  }
  return session
}

export async function submitOrderAction(
  _previous: SubmitOrderFormState,
  formData: FormData,
): Promise<SubmitOrderFormState> {
  const parsed = orderFormSchema.safeParse({
    amount: formString(formData, "amount"),
    idempotency_key: formString(formData, "idempotency_key"),
    payer_note: formString(formData, "payer_note"),
    payment_reference: formString(formData, "payment_reference"),
    plan_code: formString(formData, "plan_code"),
  })
  if (!parsed.success) {
    const fieldErrors: Partial<Record<OrderFormField, string>> = {}
    for (const issue of parsed.error.issues) {
      const field = issue.path[0]
      if (isOrderFormField(field) && fieldErrors[field] === undefined) {
        fieldErrors[field] = issue.message
      }
    }
    return { ...idleSubmitState, fieldErrors }
  }

  const session = await requireSession()
  const result = await submitOrder(createOrdersTransport(), session, {
    amount_cents: Math.round(Number(parsed.data.amount) * 100),
    idempotency_key: parsed.data.idempotency_key,
    payment_reference: parsed.data.payment_reference,
    plan_code: parsed.data.plan_code,
    ...(parsed.data.payer_note === "" ? {} : { payer_note: parsed.data.payer_note }),
  })
  revalidatePath("/usage")

  if (result.kind === "ok") {
    return { fieldErrors: {}, formError: null, submitted: true }
  }
  if (result.kind === "notFound") {
    return { ...idleSubmitState, formError: "套餐不存在，请联系管理员" }
  }
  if (result.kind === "conflict") {
    return { ...idleSubmitState, formError: "订单提交发生冲突，请刷新页面后重试" }
  }
  if (result.kind === "readOnly") {
    return { ...idleSubmitState, formError: "当前订阅已到期进入只读模式，请联系管理员恢复后再申请" }
  }
  if (result.kind === "mfaRequired") {
    return { ...idleSubmitState, formError: "请先完成两步验证设置，再执行该操作" }
  }
  if (result.kind === "anonymous") {
    return { ...idleSubmitState, formError: "登录已过期，请重新登录" }
  }
  if (result.kind === "forbidden") {
    return { ...idleSubmitState, formError: "没有执行该操作的权限" }
  }
  return { ...idleSubmitState, formError: "服务暂时不可用，请稍后再试" }
}

export async function cancelSubscriptionAction(
  _previous: CancelSubscriptionActionState,
  _formData: FormData,
): Promise<CancelSubscriptionActionState> {
  const session = await requireSession()
  const result = await cancelSubscription(createOrdersTransport(), session)
  revalidatePath("/usage")

  if (result.kind === "ok") {
    return { formError: null }
  }
  if (result.kind === "notFound") {
    return { formError: "当前租户暂无订阅" }
  }
  if (result.kind === "readOnly") {
    return { formError: "订阅已到期进入只读模式，无需取消" }
  }
  if (result.kind === "mfaRequired") {
    return { formError: "请先完成两步验证设置，再执行该操作" }
  }
  if (result.kind === "anonymous") {
    return { formError: "登录已过期，请重新登录" }
  }
  if (result.kind === "forbidden") {
    return { formError: "没有执行该操作的权限" }
  }
  return { formError: "服务暂时不可用，请稍后再试" }
}
