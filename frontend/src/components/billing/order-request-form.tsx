"use client"

import { useActionState } from "react"

import type { SubmitOrderFormState } from "@/app/actions/orders"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldTitle } from "@/components/ui/field"

type OrderRequestFormProps = {
  readonly action: (
    state: SubmitOrderFormState,
    formData: FormData,
  ) => Promise<SubmitOrderFormState>
  readonly idempotencyKey: string
}

export function OrderRequestForm({ action, idempotencyKey }: OrderRequestFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
    submitted: false,
  })

  return (
    <div className="flex flex-col gap-4">
      {state.submitted ? (
        <Alert role="status">
          <AlertDescription>
            订单已提交，请等待管理员确认付款；确认后订阅将自动开通或续订。
          </AlertDescription>
        </Alert>
      ) : null}

      <form action={formAction} className="flex flex-col gap-4" noValidate>
        {state.formError ? (
          <Alert variant="destructive">
            <AlertDescription>{state.formError}</AlertDescription>
          </Alert>
        ) : null}

        <Field>
          <FieldTitle>套餐</FieldTitle>
          <FieldDescription>标准版（按月订阅）</FieldDescription>
          <input name="plan_code" type="hidden" value="standard" />
          <input name="idempotency_key" type="hidden" value={idempotencyKey} />
        </Field>
        <FormField
          error={state.fieldErrors.amount}
          hint="单位：元，例如 199"
          id="amount"
          label="付款金额（元）"
          type="text"
        />
        <FormField
          error={state.fieldErrors.payment_reference}
          hint="线下转账的回单号或交易流水号"
          id="payment_reference"
          label="付款凭证号"
          type="text"
        />
        <FormField
          error={state.fieldErrors.payer_note}
          hint="可选，补充说明付款信息"
          id="payer_note"
          label="备注"
          type="text"
        />

        <div>
          <Button type="submit" disabled={isPending}>
            {isPending ? "提交中…" : "提交订单申请"}
          </Button>
        </div>
      </form>
    </div>
  )
}
