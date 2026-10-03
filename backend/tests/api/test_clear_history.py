"""Tests that "clear history" also removes finished job rows.

A failed job never produces an output file, so clearing the converted/compressed
files alone used to leave its row behind on the Jobs page forever.
"""
from unittest.mock import MagicMock, patch

from api.routes.compressions import delete_all_compressions
from api.routes.conversions import delete_all_conversions


USER = {"uuid": "user-a"}


@patch("api.routes.conversions.delete_file_and_metadata")
def test_clear_conversions_deletes_terminal_jobs(mock_delete):
    conversion_db = MagicMock()
    conversion_db.list_files.return_value = [{"id": "conv-1"}]
    job_db = MagicMock()

    delete_all_conversions(
        conversion_db=conversion_db,
        conversion_relations_db=MagicMock(),
        job_db=job_db,
        current_user=USER,
    )

    mock_delete.assert_called_once_with("conv-1", conversion_db)
    job_db.delete_terminal_jobs_for_user.assert_called_once_with("user-a")


@patch("api.routes.conversions.delete_file_and_metadata")
def test_clear_conversions_clears_jobs_without_converted_files(mock_delete):
    """The reported case: nothing converted succeeded, only failed jobs remain."""
    conversion_db = MagicMock()
    conversion_db.list_files.return_value = []
    job_db = MagicMock()

    delete_all_conversions(
        conversion_db=conversion_db,
        conversion_relations_db=MagicMock(),
        job_db=job_db,
        current_user=USER,
    )

    mock_delete.assert_not_called()
    job_db.delete_terminal_jobs_for_user.assert_called_once_with("user-a")


@patch("api.routes.compressions.delete_file_and_metadata")
def test_clear_compressions_deletes_terminal_jobs(mock_delete):
    compression_db = MagicMock()
    compression_db.list_files.return_value = []
    job_db = MagicMock()

    delete_all_compressions(
        compression_db=compression_db,
        compression_relations_db=MagicMock(),
        job_db=job_db,
        current_user=USER,
    )

    job_db.delete_terminal_jobs_for_user.assert_called_once_with("user-a")
