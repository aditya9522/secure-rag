import type { NavItem } from "../types";
import { Activity, Database, LayoutDashboard, MessageSquare, MessageSquarePlus, Users } from "lucide-react";

export const navItems: NavItem[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "chat", label: "Ask workspace", icon: MessageSquare },
  { id: "feedback", label: "Feedback", icon: MessageSquarePlus },
  { id: "knowledge", label: "Knowledge base", icon: Database },
  { id: "members", label: "Members & access", icon: Users, adminOnly: true },
  { id: "audit", label: "Audit & monitoring", icon: Activity, adminOnly: true },
];
