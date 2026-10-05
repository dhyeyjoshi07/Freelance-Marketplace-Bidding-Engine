"""
Ranked Bid Queue — heapq-based priority queue for bid ranking.

Uses Python's heapq module (a min-heap) with the BidRanked dataclass whose
__lt__ operator is INVERTED, so the heap root is always the highest-scoring
bid.  This gives O(log n) push and O(n log n) full ranking.

Container choice rationale:
- heapq over sorted list: push is O(log n) vs O(n) for bisect.insort
- heapq over dict/set: we need ordered access, not just lookup
- We wrap bids in BidRanked dataclass to decouple the ranking comparator
  from the ORM model
"""

from __future__ import annotations

import heapq
from typing import Optional

from backend.models.bid import BidRanked


class RankedBidQueue:
    """
    Live-sorted priority queue of bids, ordered by match_score (highest first).

    Usage:
        queue = RankedBidQueue()
        queue.push(BidRanked(bid_id=1, match_score=0.85, ...))
        queue.push(BidRanked(bid_id=2, match_score=0.92, ...))
        top = queue.peek()          # BidRanked with score 0.92
        all_ranked = queue.ranked_list()  # [0.92, 0.85]
    """

    def __init__(self):
        self._heap: list[BidRanked] = []
        # Secondary index for O(1) lookup by bid_id
        self._index: dict[int, BidRanked] = {}

    def push(self, bid_ranked: BidRanked) -> None:
        """
        Add a bid to the queue.  O(log n) via heapq.

        If a bid with the same bid_id already exists, it's replaced
        (the old entry becomes a stale ghost that's skipped on pop).
        """
        self._index[bid_ranked.bid_id] = bid_ranked
        heapq.heappush(self._heap, bid_ranked)

    def peek(self) -> Optional[BidRanked]:
        """
        Return the highest-scoring bid without removing it.

        Skips stale entries (bids that were replaced via push).
        """
        self._clean_stale()
        return self._heap[0] if self._heap else None

    def pop(self) -> Optional[BidRanked]:
        """
        Remove and return the highest-scoring bid.  O(log n).
        """
        while self._heap:
            item = heapq.heappop(self._heap)
            # Check if this entry is still current (not replaced)
            if item.bid_id in self._index and self._index[item.bid_id] is item:
                del self._index[item.bid_id]
                return item
        return None

    def ranked_list(self) -> list[BidRanked]:
        """
        Return all bids sorted by match_score, highest first.

        Uses sorted() which leverages BidRanked.__lt__ (inverted comparison).
        O(n log n) but only called when the full ranking is needed.
        """
        # Filter out stale entries
        active = [
            br for br in self._heap
            if br.bid_id in self._index and self._index[br.bid_id] is br
        ]
        return sorted(active)

    def remove(self, bid_id: int) -> bool:
        """
        Lazily remove a bid by marking it stale.  O(1).

        The actual heap entry is cleaned up on the next peek/pop/ranked_list.
        Returns True if the bid was found and removed.
        """
        if bid_id in self._index:
            del self._index[bid_id]
            return True
        return False

    def __len__(self) -> int:
        """Return the number of active (non-stale) bids."""
        return len(self._index)

    def __bool__(self) -> bool:
        return len(self._index) > 0

    def _clean_stale(self) -> None:
        """Remove stale entries from the front of the heap."""
        while self._heap:
            top = self._heap[0]
            if top.bid_id in self._index and self._index[top.bid_id] is top:
                break
            heapq.heappop(self._heap)

    @classmethod
    def from_bids(cls, bid_ranked_list: list[BidRanked]) -> RankedBidQueue:
        """
        Factory: build a queue from an existing list of ranked bids.

        Uses heapq.heapify for O(n) construction instead of n × O(log n) pushes.
        """
        queue = cls()
        queue._heap = list(bid_ranked_list)
        heapq.heapify(queue._heap)
        queue._index = {br.bid_id: br for br in bid_ranked_list}
        return queue
