import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type FormFieldProps = {
  readonly id: string
  readonly label: string
  readonly type: "email" | "password" | "text"
  readonly autoComplete?: string
  readonly inputMode?: "decimal" | "numeric" | "text"
  readonly maxLength?: number
  readonly error?: string | undefined
  readonly hint?: string
}

export function FormField({
  autoComplete,
  error,
  hint,
  id,
  inputMode,
  label,
  maxLength,
  type,
}: FormFieldProps) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        aria-invalid={error ? true : undefined}
        id={id}
        name={id}
        type={type}
        {...(autoComplete === undefined ? {} : { autoComplete })}
        {...(inputMode === undefined ? {} : { inputMode })}
        {...(maxLength === undefined ? {} : { maxLength })}
      />
      {hint ? <FieldDescription>{hint}</FieldDescription> : null}
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}
