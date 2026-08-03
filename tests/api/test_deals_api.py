import pytest

from tests.conftest import seed_deal

pytestmark = pytest.mark.api


class TestCreateDeal:
    def test_creates_a_deal_with_defaults(self, client, auth_headers):
        response = client.post(
            "/api/v1/deals",
            headers=auth_headers,
            json={"title": "Reel Campaign", "brand_name": "Acme"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Reel Campaign"
        assert body["currency"] == "INR"
        assert body["deal_status"] == "negotiating"
        assert body["payment_status"] == "unpaid"

    def test_rejects_a_missing_title(self, client, auth_headers):
        response = client.post(
            "/api/v1/deals", headers=auth_headers, json={"brand_name": "Acme"}
        )
        assert response.status_code == 422

    def test_rejects_a_negative_payment_amount(self, client, auth_headers):
        response = client.post(
            "/api/v1/deals",
            headers=auth_headers,
            json={"title": "Reel", "brand_name": "Acme", "payment_amount": -100},
        )
        assert response.status_code == 422


class TestListDeals:
    def test_lists_the_users_deals(self, client, auth_headers, db):
        seed_deal(db, user_id=1, title="A")
        seed_deal(db, user_id=1, title="B")
        response = client.get("/api/v1/deals", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_filters_by_deal_status(self, client, auth_headers, db):
        seed_deal(db, user_id=1, title="A", deal_status="negotiating")
        seed_deal(db, user_id=1, title="B", deal_status="completed")
        response = client.get("/api/v1/deals?deal_status=completed", headers=auth_headers)
        assert [d["title"] for d in response.json()] == ["B"]

    def test_filters_by_payment_status(self, client, auth_headers, db):
        seed_deal(db, user_id=1, title="A", payment_status="paid")
        seed_deal(db, user_id=1, title="B", payment_status="unpaid")
        response = client.get("/api/v1/deals?payment_status=paid", headers=auth_headers)
        assert [d["title"] for d in response.json()] == ["A"]

    def test_only_returns_the_callers_own_deals(
        self, client, auth_headers, other_auth_headers, db
    ):
        seed_deal(db, user_id=1, title="Mine")
        response = client.get("/api/v1/deals", headers=other_auth_headers)
        assert response.json() == []


class TestGetUpdateDeleteDeal:
    def test_gets_a_deal_by_id(self, client, auth_headers, db):
        deal = seed_deal(db, user_id=1, title="Reel")
        response = client.get(f"/api/v1/deals/{deal.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Reel"

    def test_is_404_for_a_missing_deal(self, client, auth_headers):
        response = client.get("/api/v1/deals/999", headers=auth_headers)
        assert response.status_code == 404

    def test_is_404_for_another_users_deal(self, client, other_auth_headers, db):
        deal = seed_deal(db, user_id=1, title="Reel")
        response = client.get(f"/api/v1/deals/{deal.id}", headers=other_auth_headers)
        assert response.status_code == 404

    def test_updates_a_deal(self, client, auth_headers, db):
        deal = seed_deal(db, user_id=1, title="Reel")
        response = client.put(
            f"/api/v1/deals/{deal.id}",
            headers=auth_headers,
            json={
                "title": "Updated Reel",
                "brand_name": "Acme",
                "deal_status": "completed",
                "payment_status": "paid",
            },
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Reel"
        assert response.json()["deal_status"] == "completed"

    def test_deletes_a_deal(self, client, auth_headers, db):
        deal = seed_deal(db, user_id=1, title="Reel")
        response = client.delete(f"/api/v1/deals/{deal.id}", headers=auth_headers)
        assert response.status_code == 204
        assert client.get(f"/api/v1/deals/{deal.id}", headers=auth_headers).status_code == 404


class TestEarningsSummary:
    @pytest.mark.parametrize("period", ["weekly", "monthly", "yearly"])
    def test_accepts_each_period(self, client, auth_headers, db, period):
        seed_deal(db, user_id=1)
        response = client.get(f"/api/v1/deals/earnings-summary?period={period}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["period"] == period

    def test_defaults_to_monthly(self, client, auth_headers, db):
        seed_deal(db, user_id=1)
        response = client.get("/api/v1/deals/earnings-summary", headers=auth_headers)
        assert response.json()["period"] == "monthly"

    def test_rejects_an_unknown_period(self, client, auth_headers):
        response = client.get("/api/v1/deals/earnings-summary?period=daily", headers=auth_headers)
        assert response.status_code == 422


class TestDealIcsDownload:
    def test_returns_a_calendar_file(self, client, auth_headers, db):
        from datetime import datetime, timezone

        deal = seed_deal(db, user_id=1, shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))
        response = client.get(f"/api/v1/deals/{deal.id}/ics", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/calendar")
        assert f'deal-{deal.id}.ics' in response.headers["content-disposition"]
        assert "BEGIN:VCALENDAR" in response.text

    def test_is_422_when_the_deal_has_no_dates(self, client, auth_headers, db):
        deal = seed_deal(db, user_id=1, shoot_at=None, payment_due_date=None)
        response = client.get(f"/api/v1/deals/{deal.id}/ics", headers=auth_headers)
        assert response.status_code == 422

    def test_is_404_for_another_users_deal(self, client, other_auth_headers, db):
        deal = seed_deal(db, user_id=1)
        response = client.get(f"/api/v1/deals/{deal.id}/ics", headers=other_auth_headers)
        assert response.status_code == 404
