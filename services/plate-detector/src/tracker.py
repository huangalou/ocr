import time
from collections import defaultdict


class JobTracker:
    """Track detected plates across frames for a video job.

    For each tracked plate (identified by track_id), stores candidate frames
    and selects the one with the highest YOLO confidence as the best frame.
    """

    def __init__(self):
        self._tracks: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
        self._last_activity: dict[str, float] = {}

    def store_candidate(
        self,
        job_id: str,
        track_id: int,
        confidence: float,
        bbox: tuple[int, int, int, int],
        image,
        frame_timestamp: float,
        message: dict,
    ):
        """Store a detection candidate for a tracked plate."""
        self._tracks[job_id][track_id].append({
            "confidence": confidence,
            "bbox": bbox,
            "image": image,
            "frame_timestamp": frame_timestamp,
            "message": message,
        })
        self._last_activity[job_id] = time.monotonic()

    def get_best_frames(self, job_id: str) -> list[dict]:
        """Return the best candidate (highest confidence) for each track in a job."""
        if job_id not in self._tracks:
            return []
        best = []
        for track_id, candidates in self._tracks[job_id].items():
            winner = max(candidates, key=lambda c: c["confidence"])
            best.append({
                "track_id": track_id,
                "confidence": winner["confidence"],
                "bbox": winner["bbox"],
                "image": winner["image"],
                "frame_timestamp": winner["frame_timestamp"],
                "message": winner["message"],
            })
        return best

    def cleanup(self, job_id: str):
        """Remove all data for a completed job."""
        self._tracks.pop(job_id, None)
        self._last_activity.pop(job_id, None)

    def has_pending_data(self, job_id: str) -> bool:
        """Check if there is any tracked data for a job."""
        return job_id in self._tracks and len(self._tracks[job_id]) > 0

    def get_last_activity(self, job_id: str) -> float:
        """Return the monotonic timestamp of the last activity for a job."""
        return self._last_activity.get(job_id, 0.0)
