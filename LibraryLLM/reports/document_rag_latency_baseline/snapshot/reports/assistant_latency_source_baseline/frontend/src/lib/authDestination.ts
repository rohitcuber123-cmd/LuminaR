export function destination(role: string, from?: string): string {
  const home =
    role === "ADMIN"
      ? "/admin"
      : role === "LIBRARIAN"
        ? "/librarian"
        : "/profile";
  if (
    !from ||
    from === "/login" ||
    from === "/dashboard" ||
    from.startsWith("/staff/") ||
    !from.startsWith("/") ||
    from.startsWith("//")
  )
    return home;
  if (from.startsWith("/admin") && role !== "ADMIN") return home;
  if (from.startsWith("/librarian") && !["ADMIN", "LIBRARIAN"].includes(role))
    return home;
  return from;
}
