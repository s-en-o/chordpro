from app.adapters.base import SourceAdapter
from app.ir import LayoutDoc


class FakeAdapter:
    def to_layout(self, data: bytes) -> LayoutDoc:
        return LayoutDoc(metadata={"source": "fake"})


def test_protocol_is_satisfied_structurally() -> None:
    adapter: SourceAdapter = FakeAdapter()
    layout = adapter.to_layout(b"anything")
    assert layout.metadata == {"source": "fake"}
