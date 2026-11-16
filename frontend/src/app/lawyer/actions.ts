"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  createClient,
  createMatter,
  type CreateClientState,
} from "@/lib/api/lawyer";

export async function createMatterAction(formData: FormData) {
  const matter = createMatter({
    title: String(formData.get("title") ?? ""),
    court: String(formData.get("court") ?? ""),
    caseType: String(formData.get("caseType") ?? ""),
    clientId: String(formData.get("clientId") ?? ""),
  });

  if (!matter) redirect("/lawyer/matters/new?error=1");

  revalidatePath("/lawyer/matters");
  revalidatePath("/lawyer/dashboard");
  redirect("/lawyer/matters");
}

export async function createClientAction(
  _state: CreateClientState,
  formData: FormData,
): Promise<CreateClientState> {
  const client = createClient({
    name: String(formData.get("name") ?? ""),
    phone: String(formData.get("phone") ?? ""),
    email: String(formData.get("email") ?? ""),
  });

  if (!client) return { status: "error" };

  revalidatePath("/lawyer/clients");
  revalidatePath("/lawyer/dashboard");

  return { status: "ok", ...client };
}
