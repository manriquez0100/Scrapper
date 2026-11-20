# La Página Siguiente

Tienda React para una librería: catálogo, buscador, detalle de producto y opciones de compra por PayPal u OXXO.

## Ejecutar

```bash
npm install
npm run dev
```

La aplicación quedará disponible en `http://localhost:5174`.

## Pagos

1. Copie `.env.example` a `.env`.
2. Establezca `VITE_PAYPAL_PAYMENT_URL` con el enlace de pago seguro de la cuenta comercial de PayPal. El frontend no contiene ni debe contener claves secretas, datos bancarios ni lógica de cobro.
3. El pago por depósito en OXXO muestra las instrucciones y abre WhatsApp en el número configurado (`477 137 6775`) para que el cliente envíe su comprobante manualmente.

## Firebase / Firestore

El backend guarda automáticamente todos los resultados reales de BuscaLibre y Mercado Libre en la colección `books`: usa el URL del producto para hacer *upsert* y evitar duplicados. Configure el backend antes de reiniciarlo:

```env
FIREBASE_CATALOG_ENABLED=true
FIREBASE_PROJECT_ID=tu-proyecto-firebase
FIREBASE_CATALOG_COLLECTION=books
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=firebase-credentials.json
```

Descargue la cuenta de servicio desde Firebase Console y guárdela como `firebase-credentials.json` en la carpeta raíz de `Scrapper`; nunca la agregue a Git.

La plataforma web consume la misma colección Firestore mediante su API REST. Configure:

```env
VITE_CATALOG_SOURCE=firebase
VITE_FIREBASE_PROJECT_ID=tu-proyecto-firebase
VITE_FIRESTORE_COLLECTION=books
```

La colección se llena con documentos que incluyen `id`, `title`, `author`, `price`, `imageUrl`, `description`, `editorial`, `pages`, `delivery`, `source` y `searchTerms`. Para que el navegador pueda leer el catálogo público, cree reglas de Firestore de sólo lectura pública para `books`; mantenga las escrituras bloqueadas al cliente, porque únicamente el backend usa la cuenta de servicio para escribir. Para una base privada, sustituya `fetchFirebaseCatalog` por el SDK de Firebase y reglas de autenticación; nunca exponga credenciales de administración en React.
