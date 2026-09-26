/** Sidebar starts collapsed (icons only) on phone-width screens. */
export function initialSidebarCollapsed(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(max-width: 767px)").matches
    : false;
}
