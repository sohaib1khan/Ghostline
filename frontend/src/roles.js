/** Studio access — only the super admin. Former "admin" role was removed. */
export function isStaff(role) {
  return role === "super_admin";
}

export function isSuperAdmin(role) {
  return role === "super_admin";
}
