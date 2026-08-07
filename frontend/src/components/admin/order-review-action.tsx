"use client"

import { useActionState, useId, useState } from "react"

import type { OrderReviewActionState } from "@/app/actions/admin"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

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
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)
  const uid = useId()
  const confirmFormId = `${uid}-confirm`
  const rejectFormId = `${uid}-reject`
  const reasonInputId = `${uid}-reason`

  const formError = confirmState.formError ?? rejectState.formError

  return (
    <div className="flex flex-wrap items-center gap-2">
      <form action={confirmFormAction} id={confirmFormId}>
        <input name="order_id" type="hidden" value={orderId} />
      </form>
      <form action={rejectFormAction} id={rejectFormId}>
        <input name="order_id" type="hidden" value={orderId} />
      </form>

      <AlertDialog onOpenChange={setConfirmOpen} open={confirmOpen}>
        <AlertDialogTrigger render={<Button disabled={confirmPending} size="sm" />}>
          确认付款
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认付款</AlertDialogTitle>
            <AlertDialogDescription>
              确定要确认该订单的付款吗？确认后将开通或续订订阅。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              form={confirmFormId}
              onClick={() => setConfirmOpen(false)}
              type="submit"
            >
              确认付款
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog onOpenChange={setRejectOpen} open={rejectOpen}>
        <AlertDialogTrigger
          render={<Button disabled={rejectPending} size="sm" variant="secondary" />}
        >
          拒绝
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>拒绝订单</AlertDialogTitle>
            <AlertDialogDescription>
              确定要拒绝该订单吗？拒绝后订阅不会开通或续订。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor={reasonInputId}>拒绝理由（可选）</Label>
            <Input
              form={rejectFormId}
              id={reasonInputId}
              name="reason"
              placeholder="请输入拒绝理由（可选）："
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              form={rejectFormId}
              onClick={() => setRejectOpen(false)}
              type="submit"
              variant="secondary"
            >
              拒绝
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {formError ? (
        <p className="w-full text-sm text-destructive" role="alert">
          {formError}
        </p>
      ) : null}
    </div>
  )
}
