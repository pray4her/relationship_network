import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type FormFieldProps = {
  readonly id: string
  readonly label: string
  readonly type: "email" | "password" | "text"
  readonly autoComplete?: string
  readonly error?: string | undefined
  readonly hint?: string
}

export function FormField({ autoComplete, error, hint, id, label, type }: FormFieldProps) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        aria-invalid={error ? true : undefined}
        id={id}
        name={id}
        type={type}
        {...(autoComplete === undefined ? {} : { autoComplete })}
      />
      {hint ? <FieldDescription>{hint}</FieldDescription> : null}
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}
