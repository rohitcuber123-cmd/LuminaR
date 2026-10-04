export interface NavLink {
  label: string;
  to: string;
}

export function getRoleNavLinks(role?: string): NavLink[] {
  const links: NavLink[] = [];
  if (role === "GENERAL_USER") {
    links.push({ label: "My Library", to: "/profile" });
  }
  if (role === "ADMIN") {
    links.push({ label: "Admin Dashboard", to: "/admin" });
  }
  if (role === "LIBRARIAN" || role === "ADMIN") {
    links.push({ label: "Librarian Dashboard", to: "/librarian" });
  }
  return links;
}
