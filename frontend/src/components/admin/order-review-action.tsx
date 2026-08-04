"use client"

import { useActionState, useRef } from "react"

import type { OrderReviewActionState } from "@/app/actions/admin"
import { Button } from "@/components/ui/button"

type OrderReviewActionProps = {
  readonly confirmAction: (
    state: OrderReviewActionState,
    formData: FormData,
  ) => Promise<OrderReviewActionState>
  readonly rejectAction: (
    state: OrderReviewActionState,
    formData: FormData,
  ) => Promise<OrderReviewActionState>
  readonly orderId: string
}

export function OrderReviewAction({
  confirmAction,
  orderId,
  rejectAction,
}: OrderReviewActionProps) {
  const [confirmState, confirmFormAction, confirmPending] = useActionState(confirmAction, {
    formError: null,
  })
  const [rejectState, rejectFormAction, rejectPending] = useActionState(rejectAction, {
    formError: null,
  })
  const reasonRef = useRef<HTMLInputElement>(null)

  const formError = confirmState.formError ?? rejectState.formError

  return (
    <div className="table-actions">
      <form
        action={confirmFormAction}
        onSubmit={(event) => {
          if (!window.confirm("确定要确认该订单的付款吗？确认后将开通或续订订阅。")) {
            event.preventDefault()
          }
        }}
      >
        <input name="order_id" type="hidden" value={orderId} />
        <Button className="btn-small" type="submit" disabled={confirmPending}>
          确认付款
        </Button>
      </form>
      <form
        action={rejectFormAction}
        onSubmit={(event) => {
          const reason = window.prompt("请输入拒绝理由（可选）：")
          if (reason === null) {
            event.preventDefault()
            return
          }
          if (reasonRef.current) {
            reasonRef.current.value = reason
          }
        }}
      >
        <input name="order_id" type="hidden" value={orderId} />
        <input defaultValue="" name="reason" ref={reasonRef} type="hidden" />
        <Button className="btn-small" mode="secondary" type="submit" disabled={rejectPending}>
          拒绝
        </Button>
      </form>
      {formError ? (
        <p className="form-error" role="alert">
          {formError}
        </p>
      ) : null}
    </div>
  )
}
