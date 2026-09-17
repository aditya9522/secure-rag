import type { LucideIcon } from "lucide-react";

export type View = "overview" | "chat" | "knowledge" | "members" | "audit" | "settings";
export type Role = "Admin" | "Organization" | "User";
export type Theme = "light" | "dark";

export interface OrganizationOption {
  id?: string;
  name: string;
  detail: string;
  initials: string;
  color: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  mode?: "grounded" | "conversational" | "refused";
  citations?: Array<{ document_id: string; document_title: string; chunk_id: string; score: number }>;
  streaming?: boolean;
}

export interface NavItem {
  id: View;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}
