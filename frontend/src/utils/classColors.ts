/**
 * Detection class color utilities.
 * Returns a hex color for a given class label, using profile overrides if available.
 */

const DEFAULT_COLORS: Record<string, string> = {
  drone: "var(--uav-class-drone)",
  bird: "var(--uav-class-bird)",
  person: "var(--uav-class-person)",
  vehicle: "var(--uav-class-vehicle)",
};

// Fallback palette for unknown classes
const PALETTE = [
  "#3b82f6", "#8b5cf6", "#06b6d4", "#10b981",
  "#f59e0b", "#ef4444", "#ec4899", "#84cc16",
];

const _assignedColors: Record<string, string> = {};
let _paletteIndex = 0;

export function getClassColor(
  label: string,
  profileColors?: Record<string, string>
): string {
  if (profileColors?.[label]) return profileColors[label];
  if (DEFAULT_COLORS[label]) return DEFAULT_COLORS[label];
  if (!_assignedColors[label]) {
    _assignedColors[label] = PALETTE[_paletteIndex % PALETTE.length];
    _paletteIndex++;
  }
  return _assignedColors[label];
}
