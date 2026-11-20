import { mockBooks } from '../data/mockBooks';
import type { Book } from '../types';

// Firebase is the normal catalog source.  Mocks remain available only while
// configuring a project, or when VITE_CATALOG_SOURCE=mock is explicitly set.
const source = import.meta.env.VITE_CATALOG_SOURCE ?? 'firebase';

type FirestoreField = {
  stringValue?: string;
  integerValue?: string;
  doubleValue?: number;
  booleanValue?: boolean;
};
type FirestoreValue = Record<string, FirestoreField>;

function mapFirestoreBook(name: string, fields: FirestoreValue): Book {
  const getString = (key: string) => fields[key]?.stringValue ?? '';
  const getNumber = (key: string) => Number(fields[key]?.integerValue ?? fields[key]?.doubleValue ?? 0);
  return {
    id: getString('id') || name.split('/').at(-1) || crypto.randomUUID(),
    title: getString('title') || getString('titulo'),
    author: getString('author') || getString('autor') || 'Autor no disponible',
    price: getNumber('price') || getNumber('precio'),
    description: getString('description') || getString('descripcion') || 'Descripción no disponible.',
    category: getString('category') || 'Catálogo', format: getString('format') || 'No disponible',
    pages: getNumber('pages') || getNumber('num_paginas'), isbn: getString('isbn'), stock: getNumber('stock') || 1,
    delivery: getString('delivery') || getString('tiempo_entrega') || 'Consulta disponibilidad',
    coverTone: getString('coverTone') || 'midnight', badge: getString('badge') || undefined,
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
  if (source === 'mock') return mockBooks;
  // Allows a new local checkout to remain usable until the Firebase project is
  // supplied, while production reads the shared Firestore collection.
  if (!import.meta.env.VITE_FIREBASE_PROJECT_ID) return mockBooks;
  return fetchFirebaseCatalog();
}
