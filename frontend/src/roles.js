export function isStaff(role) {
  return role === "admin" || role === "super_admin";
}

export function isSuperAdmin(role) {
  return role === "super_admin";
}
