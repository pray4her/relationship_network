import { Checkbox } from "@/components/ui/checkbox"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"

import { PreviewPage, PreviewSection } from "../_preview"

export default function CheckboxPreviewPage() {
  return (
    <PreviewPage
      description="Base UI 保留表单与键盘语义，视觉层覆盖默认、选中、不确定、错误、禁用和尺寸状态。"
      title="Checkbox"
    >
      <PreviewSection title="表单状态">
        <FieldGroup>
          <Field orientation="horizontal">
            <Checkbox id="checkbox-default" />
            <FieldContent>
              <FieldLabel htmlFor="checkbox-default">接收邀请通知</FieldLabel>
              <FieldDescription>新成员接受邀请后通过邮件通知。</FieldDescription>
            </FieldContent>
          </Field>
          <Field orientation="horizontal">
            <Checkbox defaultChecked id="checkbox-checked" />
            <FieldLabel htmlFor="checkbox-checked">已选中</FieldLabel>
          </Field>
          <Field orientation="horizontal">
            <Checkbox id="checkbox-indeterminate" indeterminate />
            <FieldLabel htmlFor="checkbox-indeterminate">部分成员已选择</FieldLabel>
          </Field>
          <Field data-invalid orientation="horizontal">
            <Checkbox aria-invalid id="checkbox-invalid" />
            <FieldLabel htmlFor="checkbox-invalid">需要确认数据处理条款</FieldLabel>
          </Field>
          <Field data-disabled orientation="horizontal">
            <Checkbox defaultChecked disabled id="checkbox-disabled" />
            <FieldLabel htmlFor="checkbox-disabled">租户只读时不可修改</FieldLabel>
          </Field>
        </FieldGroup>
      </PreviewSection>

      <PreviewSection title="尺寸与静态状态镜像">
        <div className="flex flex-wrap items-center gap-[var(--space-6)]">
          <Checkbox aria-label="小尺寸" size="sm" />
          <Checkbox aria-label="默认尺寸" defaultChecked />
          <Checkbox aria-label="大尺寸" size="lg" />
          <Checkbox aria-label="悬停镜像" data-state="hover" />
          <Checkbox aria-label="焦点镜像" data-state="focus-visible" />
        </div>
      </PreviewSection>
    </PreviewPage>
  )
}
