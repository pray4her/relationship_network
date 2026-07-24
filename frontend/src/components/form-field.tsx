import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

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
    <div className="form-field">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        invalid={Boolean(error)}
        name={id}
        type={type}
        {...(autoComplete === undefined ? {} : { autoComplete })}
      />
      {hint ? <p className="field-hint">{hint}</p> : null}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
