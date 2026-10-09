export async function copyResponseToClipboard(text: string, imageUrls: string[]): Promise<void> {
  const clipboardItems: ClipboardItem[] = [];

  // Add text content
  clipboardItems.push(
    new ClipboardItem({
      'text/plain': new Blob([text], { type: 'text/plain' }),
    })
  );

  // Fetch and add each image
  for (const url of imageUrls) {
    try {
      const response = await fetch(url);
      if (!response.ok) continue;
      const blob = await response.blob();
      clipboardItems.push(new ClipboardItem({ [blob.type]: blob }));
    } catch (e) {
      console.warn('Failed to load image for clipboard:', url);
    }
  }

  if (clipboardItems.length > 0) {
    try {
      await navigator.clipboard.write(clipboardItems);
    } catch (e) {
      // Fallback: copy text only
      await navigator.clipboard.writeText(text);
    }
  }
}