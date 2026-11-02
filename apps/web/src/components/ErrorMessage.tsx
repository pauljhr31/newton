export function ErrorMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  );
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : "Une erreur inattendue est survenue.";
}
