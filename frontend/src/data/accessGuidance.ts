import type { Classification } from "../lib/api";

export interface ClassificationGuide {
  value: Classification;
  label: string;
  summary: string;
  useCase: string;
  example: string;
}

export const classificationGuidance: ClassificationGuide[] = [
  {
    value: "public",
    label: "Public",
    summary: "Safe for every active member of the organization.",
    useCase: "Use for material that is intentionally broad, such as public product documentation or an organization-wide handbook.",
    example: "Product overview, public FAQ, company-wide onboarding guide.",
  },
  {
    value: "internal",
    label: "Internal",
    summary: "Default working level for normal organization information.",
    useCase: "Use for routine operational knowledge that should not be exposed outside the organization.",
    example: "Team runbooks, internal processes, support playbooks.",
  },
  {
    value: "confidential",
    label: "Confidential",
    summary: "Requires members to have confidential clearance.",
    useCase: "Use for sensitive business information that should be limited to appropriately cleared members and, when needed, a group.",
    example: "Customer plans, commercial analysis, unreleased project documents.",
  },
  {
    value: "restricted",
    label: "Restricted",
    summary: "Highest clearance level for tightly controlled information.",
    useCase: "Use only for material with a clear need-to-know boundary and confirm the intended members have restricted clearance.",
    example: "Security response plans, legal strategy, highly sensitive personnel or financial records.",
  },
];

export const groupGuidance = {
  summary: "Groups add a second, team-specific boundary on top of classification.",
  useCase: "Use groups when only selected teams should retrieve a source. A member must satisfy both the classification clearance and the group rule.",
  examples: ["engineering", "support", "finance", "leadership"],
  empty: "Leave groups empty only when every active member with sufficient classification clearance should be able to use the source.",
};

export const roleGuidance = {
  member: "Can use authorized sources and chat, but cannot administer organization access.",
  admin: "Can manage organization sources and member access. Grant only to trusted operators.",
};

export function getClassificationGuide(value: Classification) {
  return classificationGuidance.find((item) => item.value === value) ?? classificationGuidance[1];
}
