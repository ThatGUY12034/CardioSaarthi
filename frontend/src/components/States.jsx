/**
 * The three things a screen shows when it has no content.
 *
 * <p>Every async page needs all three and they were being written by hand each
 * time, so a failure looked different on the review queue than on the case
 * list, and some screens showed nothing at all while they loaded. One set of
 * components means a student or a reviewer learns the pattern once.
 *
 * <p>The distinction that matters is between empty and broken. "No cases are
 * waiting" is good news; "the case list could not be loaded" is a fault. A
 * screen that renders the same grey box for both teaches people to ignore it.
 */

/** A block the shape of what is coming, so the layout does not jump. */
export function Skeleton({ className = "", ...rest }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" {...rest} />;
}

/**
 * A card-shaped placeholder.
 *
 * <p>`aria-busy` and a live message rather than silence: a screen reader user
 * otherwise hears nothing at all until the content arrives, which is
 * indistinguishable from a page that has finished and is empty.
 */
export function SkeletonCard({ lines = 3, className = "" }) {
  return (
    <div className={`card p-5 ${className}`} aria-busy="true">
      <Skeleton className="h-4 w-1/3" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton
            key={index}
            className="h-3"
            style={{ width: `${100 - index * 12}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/** A grid of them, for a page that loads a list of cards. */
export function SkeletonGrid({ count = 6, className = "" }) {
  return (
    <div
      className={`grid sm:grid-cols-2 lg:grid-cols-3 gap-6 ${className}`}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

/** Rows, for a page that loads a table. */
export function SkeletonRows({ count = 5, className = "" }) {
  return (
    <div className={`card p-5 space-y-3 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}

/**
 * Nothing here, and that is fine.
 *
 * <p>Says what would appear and, where there is one, what to do about it.
 * "No results" on its own leaves the person guessing whether they filtered
 * everything out or the system is empty.
 */
export function EmptyState({ icon = "◌", title, description, action, className = "" }) {
  return (
    <div className={`card p-10 text-center ${className}`}>
      <div className="text-3xl text-brand-muted/50" aria-hidden="true">
        {icon}
      </div>
      <h2 className="font-semibold mt-3">{title}</h2>
      {description && (
        <p className="text-sm text-brand-muted mt-2 max-w-md mx-auto leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/**
 * Something went wrong, said plainly.
 *
 * <p>`role="alert"` so it is announced rather than sitting silently on a page
 * the person is still reading. The retry is offered where the caller has one,
 * because "try again" with no way to try again is not help.
 */
export function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <div
      className="card p-8 text-center border border-brand-danger/30"
      role="alert"
    >
      <div className="text-2xl text-brand-danger" aria-hidden="true">
        {"⚠"}
      </div>
      <h2 className="font-semibold mt-3">{title}</h2>
      {message && (
        <p className="text-sm text-brand-muted mt-2 max-w-md mx-auto leading-relaxed">
          {message}
        </p>
      )}
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-sm mt-5">
          Try again
        </button>
      )}
    </div>
  );
}

/** The same thing inline, for a strip above a form rather than a whole page. */
export function InlineError({ message }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-lg border border-brand-danger/40 bg-brand-danger/10 px-4 py-3 text-sm text-brand-danger"
    >
      {message}
    </p>
  );
}
