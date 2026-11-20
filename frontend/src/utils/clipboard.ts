const MAX_IMAGE_WIDTH = 1000;
const IMAGE_GAP = 16;

function requireClipboard(): Clipboard {
  if (!navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
    throw new Error('El navegador no permite copiar imágenes en esta página.');
  }
  return navigator.clipboard;
}

async function imageFromUrl(url: string): Promise<ImageBitmap> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`No se pudo cargar la imagen (${response.status}).`);
  return createImageBitmap(await response.blob());
}

async function makeImageSheet(imageUrls: string[]): Promise<Blob | null> {
  if (!imageUrls.length) return null;

  const images = await Promise.all(imageUrls.map(imageFromUrl));
  const dimensions = images.map(image => {
    const scale = Math.min(1, MAX_IMAGE_WIDTH / image.width);
    return { width: Math.round(image.width * scale), height: Math.round(image.height * scale) };
  });
  const width = Math.max(...dimensions.map(image => image.width));
  const height = dimensions.reduce((total, image) => total + image.height, 0) + IMAGE_GAP * (images.length - 1);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('No se pudo preparar las imágenes para copiar.');

  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, width, height);
  let y = 0;
  images.forEach((image, index) => {
    const { width: imageWidth, height: imageHeight } = dimensions[index];
    context.drawImage(image, 0, y, imageWidth, imageHeight);
    y += imageHeight + IMAGE_GAP;
    image.close();
  });

  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('No se pudo convertir las imágenes.')), 'image/png');
  });
}

export async function copyResponseToClipboard(text: string): Promise<void> {
  if (!navigator.clipboard?.writeText) throw new Error('El portapapeles no está disponible.');
  await navigator.clipboard.writeText(text);
}

export async function copyImagesFromDOM(imageUrls: string[]): Promise<void> {
  const imageSheet = await makeImageSheet(imageUrls);
  if (!imageSheet) throw new Error('No hay imágenes para copiar.');
  await requireClipboard().write([
    new ClipboardItem({ 'image/png': imageSheet }),
  ]);
}

export async function copyAllFromDOM(text: string, imageUrls: string[]): Promise<void> {
  const imageSheet = await makeImageSheet(imageUrls);
  if (!imageSheet) {
    await copyResponseToClipboard(text);
    return;
  }

  await requireClipboard().write([
    new ClipboardItem({
      'text/plain': new Blob([text], { type: 'text/plain' }),
      'image/png': imageSheet,
    }),
  ]);
}
