from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.core.config import settings
from app.services import embedding_service
from app.services.embedding_service import EmbeddingError


def vector(value: object = 0.25, *, dimension: int | None = None) -> list[object]:
    return [value] * (dimension if dimension is not None else settings.EMBEDDING_DIMENSION)


class EmbeddingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        embedding_service.get_embedding_model.cache_clear()

    def tearDown(self) -> None:
        embedding_service.get_embedding_model.cache_clear()

    def test_empty_document_list_returns_without_loading_model(self) -> None:
        with patch.object(embedding_service, "get_embedding_model") as factory:
            self.assertEqual(embedding_service.embed_documents([]), [])
        factory.assert_not_called()

    def test_blank_document_text_and_query_are_rejected(self) -> None:
        with self.assertRaises(EmbeddingError):
            embedding_service.embed_documents(["valid", "  "])
        with self.assertRaises(EmbeddingError):
            embedding_service.embed_query("\n\t")

    def test_document_embeddings_preserve_order_and_return_plain_floats(self) -> None:
        model = Mock()
        model.embed_documents.return_value = [vector("0.1"), vector("0.2")]
        with patch.object(embedding_service, "get_embedding_model", return_value=model):
            vectors = embedding_service.embed_documents(["first", "second"])

        model.embed_documents.assert_called_once_with(["first", "second"])
        self.assertEqual([item[0] for item in vectors], [0.1, 0.2])
        self.assertTrue(all(isinstance(value, float) for item in vectors for value in item))

    def test_query_embedding_is_returned_as_plain_floats(self) -> None:
        model = Mock()
        model.embed_query.return_value = vector("0.5")
        with patch.object(embedding_service, "get_embedding_model", return_value=model):
            result = embedding_service.embed_query("authentication requirements")

        model.embed_query.assert_called_once_with("authentication requirements")
        self.assertEqual(result[0], 0.5)
        self.assertTrue(all(isinstance(value, float) for value in result))

    def test_wrong_document_and_query_dimensions_raise_controlled_errors(self) -> None:
        document_model = Mock()
        document_model.embed_documents.return_value = [vector(dimension=12)]
        with patch.object(embedding_service, "get_embedding_model", return_value=document_model):
            with self.assertRaises(EmbeddingError):
                embedding_service.embed_documents(["requirements"])

        query_model = Mock()
        query_model.embed_query.return_value = vector(dimension=12)
        with patch.object(embedding_service, "get_embedding_model", return_value=query_model):
            with self.assertRaises(EmbeddingError):
                embedding_service.embed_query("requirements")

    def test_inference_failures_are_wrapped(self) -> None:
        model = Mock()
        model.embed_documents.side_effect = RuntimeError("synthetic transformer failure")
        with patch.object(embedding_service, "get_embedding_model", return_value=model):
            with self.assertRaises(EmbeddingError) as error:
                embedding_service.embed_documents(["requirements"])

        self.assertIsInstance(error.exception.__cause__, RuntimeError)

    def test_cached_model_factory_reuses_one_instance_with_configured_arguments(self) -> None:
        instance = Mock()
        with patch.object(
            embedding_service, "HuggingFaceEmbeddings", return_value=instance
        ) as embedding_class:
            first = embedding_service.get_embedding_model()
            second = embedding_service.get_embedding_model()

        self.assertIs(first, second)
        embedding_class.assert_called_once_with(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": settings.EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": settings.EMBEDDING_NORMALIZE},
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
