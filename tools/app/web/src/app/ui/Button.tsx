type Variant = 'default' | 'primary' | 'ghost'

// No `disabled` prop, by design: the app never greys a control out to pre-empt a
// refusal. Let the command run and let the CLI refuse.
export function Button({
  variant = 'default', onClick, children,
}: { variant?: Variant; onClick?: () => void; children: React.ReactNode }) {
  const cls = variant === 'default' ? 'btn' : `btn ${variant}`
  return <button className={cls} onClick={onClick}>{children}</button>
}
