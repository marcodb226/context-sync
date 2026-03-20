"""Tests for refresh-cursor signature computation."""

from __future__ import annotations

from context_sync._gateway import RefreshCommentMeta, RefreshThreadMeta, RelationData
from context_sync._signatures import (
    SIGNATURE_PREFIX,
    compute_comments_signature,
    compute_relations_signature,
)

# SHA-256 of the empty string — the expected digest when no records exist.
_EMPTY_SHA256: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ---------------------------------------------------------------------------
# Comments signature
# ---------------------------------------------------------------------------


class TestComputeCommentsSignature:
    def test_empty_inputs(self) -> None:
        sig: str = compute_comments_signature([], [])
        assert sig == f"v1:{_EMPTY_SHA256}"

    def test_single_thread_and_comment(self) -> None:
        thread: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="thread-1",
            resolved=False,
        )
        comment: RefreshCommentMeta = RefreshCommentMeta(
            comment_id="comment-1",
            root_comment_id="thread-1",
            parent_comment_id=None,
            updated_at="2025-01-15T10:00:00Z",
            deleted=False,
        )
        sig: str = compute_comments_signature([comment], [thread])
        assert sig == ("v1:615dcef3f71477db79b172ee19fc7be8ea6a1648b9b4f86e282da898952c3063")

    def test_multiple_threads_sorted_by_root_comment_id(self) -> None:
        t_bbb: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="bbb",
            resolved=True,
        )
        t_aaa: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="aaa",
            resolved=False,
        )
        sig: str = compute_comments_signature([], [t_bbb, t_aaa])
        assert sig == ("v1:0867cbba7ef969c706b97130b38e7c753d43a197509423d6efb0212175e85e8a")

    def test_comment_with_none_updated_at_and_none_deleted(self) -> None:
        thread: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="thread-1",
            resolved=False,
        )
        comment: RefreshCommentMeta = RefreshCommentMeta(
            comment_id="comment-2",
            root_comment_id="thread-1",
            parent_comment_id=None,
            updated_at=None,
            deleted=None,
        )
        sig: str = compute_comments_signature([comment], [thread])
        assert sig == ("v1:ed566f1eea3c5fe87ef825a89d6430a16de9a58407752ad2adf1c562ba2d030c")

    def test_determinism(self) -> None:
        thread: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="thread-1",
            resolved=False,
        )
        comment: RefreshCommentMeta = RefreshCommentMeta(
            comment_id="comment-1",
            root_comment_id="thread-1",
            parent_comment_id=None,
            updated_at="2025-01-15T10:00:00Z",
            deleted=False,
        )
        sig_a: str = compute_comments_signature([comment], [thread])
        sig_b: str = compute_comments_signature([comment], [thread])
        assert sig_a == sig_b

    def test_different_inputs_produce_different_output(self) -> None:
        thread: RefreshThreadMeta = RefreshThreadMeta(
            root_comment_id="thread-1",
            resolved=False,
        )
        comment_a: RefreshCommentMeta = RefreshCommentMeta(
            comment_id="comment-1",
            root_comment_id="thread-1",
            parent_comment_id=None,
            updated_at="2025-01-15T10:00:00Z",
            deleted=False,
        )
        comment_b: RefreshCommentMeta = RefreshCommentMeta(
            comment_id="comment-99",
            root_comment_id="thread-1",
            parent_comment_id=None,
            updated_at="2025-01-15T10:00:00Z",
            deleted=False,
        )
        sig_a: str = compute_comments_signature([comment_a], [thread])
        sig_b: str = compute_comments_signature([comment_b], [thread])
        assert sig_a != sig_b

    def test_uses_v1_prefix(self) -> None:
        sig: str = compute_comments_signature([], [])
        assert sig.startswith(SIGNATURE_PREFIX)


# ---------------------------------------------------------------------------
# Relations signature
# ---------------------------------------------------------------------------


class TestComputeRelationsSignature:
    def test_empty_relations(self) -> None:
        sig: str = compute_relations_signature([])
        assert sig == f"v1:{_EMPTY_SHA256}"

    def test_single_relation(self) -> None:
        relation: RelationData = RelationData(
            dimension="hierarchy",
            relation_type="blocks",
            target_issue_id="issue-100",
            target_issue_key="PROJ-100",
        )
        sig: str = compute_relations_signature([relation])
        assert sig == ("v1:e66c46dcdcdec0d166ac9d7b04734ac384301b60ba05b6af3b7e6e5c03add353")

    def test_multiple_relations_sorted_by_canonical_tuple(self) -> None:
        r_hierarchy: RelationData = RelationData(
            dimension="hierarchy",
            relation_type="blocks",
            target_issue_id="id-1",
            target_issue_key="KEY-1",
        )
        r_dependency: RelationData = RelationData(
            dimension="dependency",
            relation_type="depends_on",
            target_issue_id="id-2",
            target_issue_key="KEY-2",
        )
        sig: str = compute_relations_signature([r_hierarchy, r_dependency])
        assert sig == ("v1:c39284bcc863f4edd3e5e138c97352a899c9708b19fac16454d9dc479e84b857")

    def test_determinism(self) -> None:
        relation: RelationData = RelationData(
            dimension="hierarchy",
            relation_type="blocks",
            target_issue_id="issue-100",
            target_issue_key="PROJ-100",
        )
        sig_a: str = compute_relations_signature([relation])
        sig_b: str = compute_relations_signature([relation])
        assert sig_a == sig_b

    def test_reordered_inputs_produce_identical_output(self) -> None:
        r_hierarchy: RelationData = RelationData(
            dimension="hierarchy",
            relation_type="blocks",
            target_issue_id="id-1",
            target_issue_key="KEY-1",
        )
        r_dependency: RelationData = RelationData(
            dimension="dependency",
            relation_type="depends_on",
            target_issue_id="id-2",
            target_issue_key="KEY-2",
        )
        sig_original: str = compute_relations_signature([r_hierarchy, r_dependency])
        sig_swapped: str = compute_relations_signature([r_dependency, r_hierarchy])
        assert sig_original == sig_swapped

    def test_uses_v1_prefix(self) -> None:
        sig: str = compute_relations_signature([])
        assert sig.startswith(SIGNATURE_PREFIX)
