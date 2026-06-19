/** [Meeting]32 brand mark — a chat bubble with a check ("conversation → done").
 * Stroke-based to match the app's lucide icon set; renders in currentColor so it inherits the
 * surrounding tile's text color (e.g. primary-foreground on a bg-primary tile). */

export function Logo({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="m8 10 2.5 2.5L16 7" />
    </svg>
  )
}
