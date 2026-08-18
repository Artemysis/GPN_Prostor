"""Интеграционные тесты семантического поиска и поиска аналогичных заявок."""

import uuid

import pytest

pytestmark = pytest.mark.integration


class TestSemanticSearch:
    async def test_finds_products_contractors_and_similar(self, client, seed_search_corpus):
        # Arrange
        corpus = seed_search_corpus
        payload = {"query": "гидравлический разрыв пласта", "top_k": 5}

        # Act
        response = await client.post("/search/semantic", json=payload)

        # Assert
        assert response.status_code == 200
        body = response.json()
        product_ids = [p["product_id"] for p in body["products"]]
        assert corpus["product_burn"].product_id in product_ids
        assert body["products"][0]["product_id"] == corpus["product_burn"].product_id
        assert body["contractors"][0]["company_id"] == corpus["company"].company_id
        assert body["similar_requests"][0]["request_id"] == str(corpus["request"].id)
        assert body["related_services"]  # products[1:] -> 3D-геомодель

    async def test_filters_narrow_results(self, client, seed_search_corpus):
        # Arrange
        corpus = seed_search_corpus
        payload = {
            "query": "гидравлический разрыв пласта",
            "filters": {
                "company_id": "NO-SUCH-COMPANY",
                "product_id": corpus["product_burn"].product_id,
            },
        }

        # Act
        response = await client.post("/search/semantic", json=payload)

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["contractors"] == []
        assert [p["product_id"] for p in body["products"]] == [corpus["product_burn"].product_id]

    async def test_query_required(self, client):
        # Arrange / Act
        response = await client.post("/search/semantic", json={})

        # Assert
        assert response.status_code == 400


class TestSimilarRequests:
    async def test_search_by_text_query(self, client, seed_search_corpus):
        # Arrange
        corpus = seed_search_corpus

        # Act
        response = await client.post(
            "/search/similar-requests", json={"query": "ГРП на скважине 1234 гидравлический разрыв пласта", "top_k": 3}
        )

        # Assert
        assert response.status_code == 200
        matches = response.json()
        assert matches[0]["request_id"] == str(corpus["request"].id)
        assert matches[0]["similarity"] > 0.5  # текст запроса почти совпадает с заявкой

    async def test_search_by_request_id_derives_query(self, client, seed_search_corpus):
        # Arrange
        corpus = seed_search_corpus

        # Act
        response = await client.post("/search/similar-requests", json={"request_id": str(corpus["request"].id)})

        # Assert
        assert response.status_code == 200
        assert any(m["request_id"] == str(corpus["request"].id) for m in response.json())

    async def test_missing_query_and_request_id_is_400(self, client):
        # Arrange / Act
        response = await client.post("/search/similar-requests", json={})

        # Assert
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION"

    async def test_unknown_request_id_is_404(self, client):
        # Arrange / Act
        response = await client.post("/search/similar-requests", json={"request_id": str(uuid.uuid4())})

        # Assert
        assert response.status_code == 404


class TestRecommendContractors:
    async def test_recommend_by_query(self, client, seed_search_corpus):
        # Arrange
        corpus = seed_search_corpus

        # Act
        response = await client.post("/search/recommend-contractors", json={"query": "ГРП нефтесервис"})

        # Assert
        assert response.status_code == 200
        assert response.json()[0]["company_id"] == corpus["company"].company_id

    async def test_empty_query_is_400(self, client):
        # Arrange / Act
        response = await client.post("/search/recommend-contractors", json={})

        # Assert
        assert response.status_code == 400
