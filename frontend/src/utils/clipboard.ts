export async function copyResponseToClipboard(text: string, imageUrls: string[]): Promise<void> {
  const clipboardItems: ClipboardItem[] = [];
  const backendOrigin = 'http://localhost:8000';

  // Add text content
  clipboardItems.push(
    new ClipboardItem({
      'text/plain': new Blob([text], { type: 'text/plain' }),
    })
  );

  // Fetch and add each image
  for (const url of imageUrls) {
    try {
      const fullUrl = url.startsWith('http') ? url : `${backendOrigin}${url}`;
      const response = await fetch(fullUrl, { mode: 'cors' });
      if (!response.ok) continue;
      const blob = await response.blob();
      clipboardItems.push(new ClipboardItem({ [blob.type]: blob }));
    } catch (e) {
      console.warn('Failed to load image for clipboard:', url, e);
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

export async function copyImagesToClipboard(imageUrls: string[]): Promise<void> {
  const clipboardItems: ClipboardItem[] = [];
  const backendOrigin = 'http://localhost:8000';

  for (const url of imageUrls) {
    try {
      // Use full backend URL to avoid CORS issues with relative paths
      const fullUrl = url.startsWith('http') ? url : `${backendOrigin}${url}`;
      const response = await fetch(fullUrl, { mode: 'cors' });
      if (!response.ok) continue;
      const blob = await response.blob();
      clipboardItems.push(new ClipboardItem({ [blob.type]: blob }));
    } catch (e) {
      console.warn('Failed to load image for clipboard:', url, e);
    }
  }

  if (clipboardItems.length > 0) {
    await navigator.clipboard.write(clipboardItems);
  }
}