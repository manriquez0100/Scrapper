"""Regression tests for Spanish book-request routing."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import main


class NoBookQueryLLM:
    """Forces the deterministic fallback path used when the model misses a query."""

    async def generate(self, messages, **kwargs):
        return "NO_BOOK_QUERY"


class BookQueryRoutingTests(unittest.TestCase):
    def test_extracts_title_and_author_after_estoy_buscando(self):
        query = main.extract_query_fallback(
            "Estoy buscando el hombre en busca de sentido, de viktor frank. lo tendrás?"
        )
        self.assertEqual(query, "el hombre en busca de sentido, de viktor frank")

    def test_removes_sender_prefix_and_extracts_search_request(self):
        query = main.extract_query_fallback(
            "Jesus dice: estoy buscando el evangelio de judas."
        )
        self.assertEqual(query, "el evangelio de judas")

    def test_routes_availability_and_bare_title_requests(self):
        self.assertEqual(
            main.extract_query_fallback("Tiene historia del violín?"),
            "historia del violín",
        )
        self.assertEqual(main.extract_query_fallback("El evangelio de Judas"), "El evangelio de Judas")

    def test_purchase_response_explains_payment_and_delivery_steps(self):
        behavior = main.load_behavior_config()
        response = main.purchase_selected_result_response(
            {
                "title": "Segunda Fundación",
                "author": "Isaac Asimov",
                "price": "$ 289",
                "delivery_estimate": "Envío Rápido",
            },
            behavior["purchase_and_shipping_response"],
        )
        self.assertIn("nombre completo, teléfono, domicilio, código postal", response)
        self.assertIn("transferencia, PayPal o depósito en OXXO o banco", response)
        self.assertIn("envíenos su comprobante", response)

    def test_missed_llm_extraction_still_searches_buscalibre(self):
        async def run_test():
            agent = main.Agent(NoBookQueryLLM(), behavior=main.load_behavior_config())
            result = {
                "results": [{
                    "title": "El evangelio de Judas",
                    "author": "Rodolfo Gil",
                    "price": "$ 399",
                    "availability": True,
                }]
            }
            with patch("main.search_buscalibre", new=AsyncMock(return_value=result)) as buscalibre, \
                 patch("main.search_mercadolibre", new=AsyncMock(return_value={"results": []})), \
                 patch("main.persist_catalog_books", return_value=1), \
                 patch.object(main.Agent, "generate_response", new=AsyncMock(return_value="Encontré esta opción:")), \
                 patch("main.generate_catalog_images", return_value=[]):
                response, _, _, results = await agent.handle_message(
                    "Jesus dice: estoy buscando el evangelio de judas."
                )

            buscalibre.assert_awaited_once()
            self.assertEqual(
                buscalibre.await_args.args[0],
                "el evangelio de judas",
            )
            self.assertEqual(
                buscalibre.await_args.kwargs["max_results"], 3,
            )
            self.assertEqual(response, "Encontré esta opción:")
            self.assertEqual(results[0]["title"], "El evangelio de Judas")
            self.assertEqual(results[0]["author"], "Rodolfo Gil")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
