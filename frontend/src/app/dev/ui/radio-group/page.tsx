import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

import { PreviewPage, PreviewSection } from "../_preview"

export default function RadioGroupPreviewPage() {
  return (
    <PreviewPage
      description="单选组使用 Base UI 的互斥选择和表单合同，并映射 radio.css 的尺寸、方向和状态。"
      title="RadioGroup"
    >
      <PreviewSection title="垂直选择">
        <FieldSet>
          <FieldLegend variant="label">成员角色</FieldLegend>
          <RadioGroup defaultValue="member" name="role-preview">
            <Field orientation="horizontal">
              <RadioGroupItem id="role-member" value="member" />
              <FieldContent>
                <FieldLabel htmlFor="role-member">成员</FieldLabel>
                <FieldDescription>可以查看与维护企业和职位。</FieldDescription>
              </FieldContent>
            </Field>
            <Field orientation="horizontal">
              <RadioGroupItem id="role-admin" value="admin" />
              <FieldContent>
                <FieldLabel htmlFor="role-admin">管理员</FieldLabel>
                <FieldDescription>可以管理成员与租户设置。</FieldDescription>
              </FieldContent>
            </Field>
            <Field data-disabled orientation="horizontal">
              <RadioGroupItem disabled id="role-owner" value="owner" />
              <FieldLabel htmlFor="role-owner">所有者不可转移</FieldLabel>
            </Field>
          </RadioGroup>
        </FieldSet>
      </PreviewSection>

      <PreviewSection title="水平、尺寸与错误">
        <RadioGroup defaultValue="default" name="density-preview" orientation="horizontal">
          <RadioGroupItem aria-label="小尺寸" size="sm" value="sm" />
          <RadioGroupItem aria-label="默认尺寸" value="default" />
          <RadioGroupItem aria-label="大尺寸" size="lg" value="lg" />
          <RadioGroupItem aria-invalid aria-label="错误状态" value="invalid" />
          <RadioGroupItem aria-label="焦点镜像" data-state="focus-visible" value="focus" />
        </RadioGroup>
      </PreviewSection>
    </PreviewPage>
  )
}
