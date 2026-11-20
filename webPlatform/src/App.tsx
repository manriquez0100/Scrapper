import { useEffect, useMemo, useState } from 'react';
import { getCatalog } from './services/catalogRepository';
import type { Book } from './types';

const WHATSAPP_NUMBER = '524771376775';
const paypalPaymentUrl = import.meta.env.VITE_PAYPAL_PAYMENT_URL ?? 'https://www.paypal.com/';

function money(amount: number) {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(amount);
}

function Cover({ book, featured = false }: { book: Book; featured?: boolean }) {
  return <div className={`book-cover ${book.coverTone} ${featured ? 'featured-cover' : ''}`} aria-label={`Portada de ${book.title}`}>
    <span className="cover-mark">LBM</span>
    <span className="cover-author">{book.author}</span>
    <strong>{book.title}</strong>
    <span className="cover-line" />
    <small>buena memoria</small>
  </div>;
}

function App() {
  const [books, setBooks] = useState<Book[]>([]);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(() => location.hash.replace('#/libro/', '') || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCatalog().then(setBooks).catch((cause: Error) => setError(cause.message)).finally(() => setLoading(false));
    const onHashChange = () => setSelectedId(location.hash.replace('#/libro/', '') || null);
    addEventListener('hashchange', onHashChange);
    return () => removeEventListener('hashchange', onHashChange);
  }, []);

  const selectedBook = books.find((book) => book.id === selectedId);
  const visibleBooks = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('es-MX');
    return normalized ? books.filter((book) => `${book.title} ${book.author} ${book.category}`.toLocaleLowerCase('es-MX').includes(normalized)) : books;
  }, [books, query]);

  const openBook = (id: string) => { location.hash = `/libro/${id}`; window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const goHome = () => { location.hash = ''; setQuery(''); };

  if (selectedId && selectedBook) return <BookDetail book={selectedBook} onBack={goHome} />;

  return <main>
    <header className="site-header">
      <button className="brand" onClick={goHome} aria-label="Ir al inicio"><span>LBM</span> Los libros de la buena memoria</button>
      <a href="#catalogo">Catálogo</a>
    </header>
    <section className="hero">
      <p className="eyebrow">Librería independiente · México</p>
      <h1>Un libro puede<br /><em>cambiarle el día.</em></h1>
      <p className="hero-copy">Somos una librería especializada en encontrar el libro que no has encontrado y entregarlo en la puerta de tu casa.</p>
      <label className="search" htmlFor="book-search"><span>⌕</span><input id="book-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Busque por título, autor o tema" /></label>
    </section>
    <section className="catalog" id="catalogo">
      <div className="section-heading"><div><p className="eyebrow">Selección de la casa</p><h2>{query ? 'Resultados de búsqueda' : 'Libros para empezar'}</h2></div><p>{visibleBooks.length} títulos</p></div>
      {loading && <p className="status">Cargando catálogo…</p>}
      {error && <p className="status error">{error}</p>}
      {!loading && !error && <div className="book-grid">{visibleBooks.map((book) => <article className="book-card" key={book.id}><button className="cover-button" onClick={() => openBook(book.id)}><Cover book={book} /></button><div className="book-card-info">{book.badge && <span className="tag">{book.badge}</span>}<p>{book.author}</p><h3>{book.title}</h3><div><strong>{money(book.price)}</strong><button onClick={() => openBook(book.id)}>Ver libro <span>→</span></button></div></div></article>)}</div>}
      {!loading && !error && visibleBooks.length === 0 && <p className="status">No encontramos ese título. Pruebe con el autor o una palabra distinta.</p>}
    </section>
    <section className="trust-strip"><span>✦ Pago seguro</span><span>✦ Envíos a todo México</span><span>✦ Atención por WhatsApp</span></section>
    <footer>Los libros de la buena memoria <span>·</span> Libros que vuelven a encontrarte</footer>
  </main>;
}

function BookDetail({ book, onBack }: { book: Book; onBack: () => void }) {
  const whatsappMessage = encodeURIComponent(`Hola, quiero enviar mi comprobante para comprar “${book.title}” por ${money(book.price)}.`);
  return <main>
    <header className="site-header"><button className="brand" onClick={onBack}><span>LBM</span> Los libros de la buena memoria</button><button className="back-link" onClick={onBack}>← Volver al catálogo</button></header>
    <section className="detail-layout">
      <div className="detail-cover"><Cover book={book} featured /></div>
      <article className="detail-copy"><p className="eyebrow">{book.category}</p><h1>{book.title}</h1><h2>{book.author}</h2><p className="description">{book.description}</p><dl><div><dt>Formato</dt><dd>{book.format}</dd></div><div><dt>Páginas</dt><dd>{book.pages}</dd></div><div><dt>ISBN</dt><dd>{book.isbn}</dd></div></dl></article>
      <aside className="purchase-card"><p className="stock">● {book.stock > 0 ? `${book.stock} disponibles` : 'Sin existencias'}</p><strong className="price">{money(book.price)}</strong><p className="delivery">⌁ {book.delivery}</p><a className="paypal-button" href={paypalPaymentUrl} target="_blank" rel="noreferrer">Pagar con <b>PayPal</b></a><div className="divider"><span>o</span></div><a className="oxxo-button" href={`https://wa.me/${WHATSAPP_NUMBER}?text=${whatsappMessage}`} target="_blank" rel="noreferrer">Comprar por depósito en OXXO</a><p className="payment-note">Al realizar su depósito, envíe una foto del comprobante por WhatsApp al <strong>477 137 6775</strong>. Le confirmaremos los datos de envío personalmente.</p></aside>
    </section>
    <section className="purchase-steps"><p className="eyebrow">Comprar es sencillo</p><div><span>01</span><p>Elija su forma de pago.</p><span>02</span><p>Comparta sus datos de envío.</p><span>03</span><p>Reciba confirmación y seguimiento.</p></div></section>
  </main>;
}

export default App;
