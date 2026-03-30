import numpy as np
import pytest

from src.tracker import JobTracker


def _make_image(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestJobTracker:
    def test_store_and_get_best_frames(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={"a": 1})
        tracker.store_candidate(job_id, track_id=1, confidence=0.9, bbox=(10, 10, 50, 20), image=img, frame_timestamp=2.0, message={"a": 2})
        tracker.store_candidate(job_id, track_id=1, confidence=0.8, bbox=(10, 10, 50, 20), image=img, frame_timestamp=3.0, message={"a": 3})

        best = tracker.get_best_frames(job_id)
        assert len(best) == 1
        assert best[0]["confidence"] == 0.9
        assert best[0]["frame_timestamp"] == 2.0

    def test_multiple_tracks(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        tracker.store_candidate(job_id, track_id=2, confidence=0.8, bbox=(60, 10, 50, 20), image=img, frame_timestamp=1.0, message={})

        best = tracker.get_best_frames(job_id)
        assert len(best) == 2

    def test_cleanup_removes_job(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        tracker.cleanup(job_id)

        best = tracker.get_best_frames(job_id)
        assert len(best) == 0

    def test_unknown_job_returns_empty(self):
        tracker = JobTracker()
        best = tracker.get_best_frames("nonexistent")
        assert best == []

    def test_has_pending_data(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        assert not tracker.has_pending_data(job_id)
        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        assert tracker.has_pending_data(job_id)

    def test_get_last_activity(self):
        tracker = JobTracker()
        job_id = "job-1"
        img = _make_image()

        assert tracker.get_last_activity(job_id) == 0.0
        tracker.store_candidate(job_id, track_id=1, confidence=0.7, bbox=(10, 10, 50, 20), image=img, frame_timestamp=1.0, message={})
        assert tracker.get_last_activity(job_id) > 0
