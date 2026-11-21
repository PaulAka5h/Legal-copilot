import { signOut } from "@/app/actions";
import { Icon } from "@/components/Icon";

/** A full sign-out button; pages that may be dead ends render it so users can always leave. */
export function SignOutButton({ label }: { label: string }) {
  return (
    <form action={signOut}>
      <button className="ghost-button" type="submit">
        <Icon name="logout" size={17} />
        {label}
      </button>
    </form>
  );
}
