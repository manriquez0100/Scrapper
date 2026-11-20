import { mockBooks } from '../data/mockBooks';
import type { Book } from '../types';

const source = import.meta.env.VITE_CATALOG_SOURCE ?? 'mock';

type FirestoreValue = Record<string, { stringValue?: string; integerValue?: string; doubleValue?: number }>;

function mapFirestoreBook(name: string, fields: FirestoreValue): Book {
  const getString = (key: string) => fields[key]?.stringValue ?? '';
  const getNumber = (key: string) => Number(fields[key]?.integerValue ?? fields[key]?.doubleValue ?? 0);
  return {
    id: getString('id') || name.split('/').at(-1) || crypto.randomUUID(),
    title: getString('title'), author: getString('author'), price: getNumber('price'),
    description: getString('description'), category: getString('category'), format: getString('format'),
    pages: getNumber('pages'), isbn: getString('isbn'), stock: getNumber('stock'),
    delivery: getString('delivery'), coverTone: getString('coverTone') || 'midnight', badge: getString('badge') || undefined,
  };
}

async function fetchFirebaseCatalog(): Promise<Book[]> {
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
  const collection = import.meta.env.VITE_FIRESTORE_COLLECTION ?? 'books';
  if (!projectId) throw new Error('Falta VITE_FIREBASE_PROJECT_ID para consultar Firestore.');

  const endpoint = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/${collection}`;
  const response = await fetch(endpoint);
  if (!response.ok) throw new Error('No fue posible consultar el catálogo de Firebase.');
  const data = await response.json() as { documents?: Array<{ name: string; fields: FirestoreValue }> };
  return (data.documents ?? []).map(({ name, fields }) => mapFirestoreBook(name, fields));
}

export async function getCatalog(): Promise<Book[]> {
  return source === 'firebase' ? fetchFirebaseCatalog() : mockBooks;
}
