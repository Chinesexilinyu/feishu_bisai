import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

class TraceManager:
    @staticmethod
    def generate_trace_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def set_trace_id(trace_id: str) -> None:
        trace_id_var.set(trace_id)

    @staticmethod
    def get_trace_id() -> str:
        return trace_id_var.get()

    @staticmethod
    def new_trace() -> str:
        trace_id = TraceManager.generate_trace_id()
        TraceManager.set_trace_id(trace_id)
        return trace_id
