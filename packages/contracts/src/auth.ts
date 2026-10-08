export type Id = string;

export type Role = "platform_admin" | "organization_admin" | "teacher" | "student";

export interface TenantContext {
  platformId: Id;
  organizationId: Id;
  userId: Id;
  role: Role;
}
