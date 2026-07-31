import pytest

from app.services.job_service import JobNotFoundError, JobService

pytestmark = pytest.mark.integration


@pytest.fixture
def job_service(job_queue):
    return JobService(job_queue)


class TestEnqueue:
    def test_returns_a_job_id(
        self, job_service, worker_db, fake_structured_llm, db_user,
        connected_account_for_db_user,
    ):
        job_id = job_service.enqueue_report_generation(db_user.id, "weekly")
        assert job_id

    def test_job_runs_and_produces_a_real_report(
        self, job_service, worker_db, fake_structured_llm, db_user,
        connected_account_for_db_user,
    ):
        """The queue runs jobs inline here, so by the time enqueue returns
        the work is done and the stored result can be inspected."""
        job_id = job_service.enqueue_report_generation(db_user.id, "weekly")
        status = job_service.get_job_status(job_id, db_user.id)

        assert status.status == "finished"
        assert status.result["period"] == "weekly"
        assert status.result["top_performing_content"][0]["media_id"] == "media_1"

    def test_failed_job_reports_an_error(
        self, job_service, worker_db, db_user, monkeypatch
    ):
        """No connected account means the job raises; the failure must be
        recorded rather than silently swallowed."""
        job_id = job_service.enqueue_report_generation(db_user.id, "weekly")
        status = job_service.get_job_status(job_id, db_user.id)

        assert status.status == "failed"
        assert status.error is not None


class TestJobOwnership:
    def test_owner_can_read_their_job(
        self, job_service, worker_db, fake_structured_llm, db_user,
        connected_account_for_db_user,
    ):
        job_id = job_service.enqueue_report_generation(db_user.id, "weekly")
        assert job_service.get_job_status(job_id, db_user.id).job_id == job_id

    def test_another_user_cannot_read_it(
        self, job_service, worker_db, fake_structured_llm, db, db_user,
        connected_account_for_db_user,
    ):
        """Job IDs are unguessable UUIDs, but ownership is still checked -
        a leaked ID must not expose another user's analytics."""
        from app.models.user import User

        intruder = User(
            username="intruder", full_name="Intruder",
            email="intruder@example.com", hashed_password="x",
        )
        db.add(intruder)
        db.commit()

        job_id = job_service.enqueue_report_generation(db_user.id, "weekly")
        with pytest.raises(JobNotFoundError):
            job_service.get_job_status(job_id, intruder.id)

    def test_unknown_job_id_raises_not_found(self, job_service, db_user):
        with pytest.raises(JobNotFoundError):
            job_service.get_job_status("no-such-job", db_user.id)
