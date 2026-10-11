// Convert an age in years to a date_of_birth string relative to a fixed application date.
export function ageToDob(age: number, appDate: string): string {
  const app = new Date(appDate + "T00:00:00Z");
  const dob = new Date(app.getTime() - Math.round(age * 365.25) * 86400000);
  return dob.toISOString().slice(0, 10);
}

// Inverse: approximate age in years from a date_of_birth string.
export function dobToAge(dob: string, appDate: string): number {
  const d = new Date(dob + "T00:00:00Z");
  const app = new Date(appDate + "T00:00:00Z");
  return (app.getTime() - d.getTime()) / 86400000 / 365.25;
}

export function rupees(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return "\u20B9" + Math.round(n).toLocaleString("en-IN");
}

export function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return n + "%";
}
