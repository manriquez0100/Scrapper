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

El catálogo usa mocks de inicio. Para leer Firestore mediante su API REST, configure:

```env
VITE_CATALOG_SOURCE=firebase
VITE_FIREBASE_PROJECT_ID=tu-proyecto-firebase
VITE_FIRESTORE_COLLECTION=books
```

La colección debe contener documentos con: `id`, `title`, `author`, `price`, `description`, `category`, `format`, `pages`, `isbn`, `stock`, `delivery` y `coverTone`. Para una base privada, sustituya `fetchFirebaseCatalog` por el SDK de Firebase y reglas de autenticación; nunca exponga credenciales de administración en React.
