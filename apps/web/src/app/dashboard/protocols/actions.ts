"use server";

import type { Protocol, ProtocolInput } from "@prefix/shared";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/server/api";

export interface ActionResult {
  error: string | null;
}

function failure(error: unknown): ActionResult {
  if (error instanceof ApiError) {
    if (error.status === 401) redirect("/login");
    return { error: error.message };
  }
  return { error: "Something went wrong. Please try again." };
}

/**
 * Create a protocol (protocolId null) or edit one. Editing an approved version makes the API
 * create a new draft, so we always navigate to the id the API returns.
 */
export async function saveProtocol(
  protocolId: string | null,
  input: ProtocolInput,
): Promise<ActionResult> {
  let saved: Protocol;
  try {
    saved = await api<Protocol>(
      protocolId === null
        ? "/protocols"
        : `/protocols/${encodeURIComponent(protocolId)}`,
      { method: protocolId === null ? "POST" : "PUT", body: input },
    );
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/dashboard/protocols");
  redirect(`/dashboard/protocols/${saved.id}`);
}

export async function approveProtocol(
  protocolId: string,
  _previous: ActionResult,
  formData: FormData,
): Promise<ActionResult> {
  try {
    await api<Protocol>(
      `/protocols/${encodeURIComponent(protocolId)}/approve`,
      {
        method: "POST",
        body: {
          acknowledge_sample: formData.get("acknowledge_sample") === "on",
        },
      },
    );
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/dashboard/protocols");
  revalidatePath(`/dashboard/protocols/${protocolId}`);
  return { error: null };
}
