export const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024;

const ALLOWED_EXTENSION = /\.(pdf|png|jpe?g|gif|webp|bmp|tiff?)$/i;

export function isAllowedDocument(name: string, mimeType: string) {
  if (mimeType === "application/pdf" || mimeType.startsWith("image/")) {
    return true;
  }

  return !mimeType && ALLOWED_EXTENSION.test(name);
}
