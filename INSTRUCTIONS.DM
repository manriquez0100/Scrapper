Implementa fastApi para hacer procesar una consulta de lenguaje natural sobre la búsqueda de un libro. Ej. "hola, estoy buscando el primer libro e harry potter". Este texto se envía a LM studio donde obtine el texto de búsqueda( harry potter 1) y hace la búsqueda con busalibre_too.py. Despues de obtener el json de respuesta con informaci´pn del libro, se envía a lm studio para procesar y acomodar en una respuesta natural. Ej. "Claro. tenemos harry potter y la piedra filosofal en 399 pesos. "
La estructura es la siguiente
pregunta llega a fastApi ej. "hola, busco el libro de harry potter 2. lo tendrá?"
se envía a LM studio para obtener solo el nombre del libro "harry potter 2"
este texto se envía a buscalibre_tool.py para iniciar su búsqueda y el json obtenido
se envía de nuevo a LM studio para procesar a una respuesta natural. ej. Sí, encontramos harry potter y la cámara secreta en 399 pesos.
LM studio tiene el modelo google/gemma-4-e4b