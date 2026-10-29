/** What a staff action reports back, so the screen can show a toast. */
export interface ActionResult {
  ok: boolean;
  message: string;
}

export function refused(message: string): ActionResult {
  return { ok: false, message };
}
