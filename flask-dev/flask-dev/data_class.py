from dataclasses import dataclass

@dataclass
class PipelineOutput:
    title: str
    summary: str
    html: str
