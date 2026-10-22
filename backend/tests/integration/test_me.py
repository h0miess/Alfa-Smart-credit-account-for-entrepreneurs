import httpx


async def test_me_returns_representative_and_company(
    client: httpx.AsyncClient, mock_user_id: str
) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["uuid"] == mock_user_id
    assert body["roles"] == ["client"]
    assert body["representative"]["can_sign"] is True
    assert body["company"]["name"] == "ИП Иванов Иван Иванович"
    assert body["company"]["inn"] == "772814539067"
