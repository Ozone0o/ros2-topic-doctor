"""ros2_topic_doctor - ROS2 Topic 诊断工具。"""

__all__ = [
    "main",
    "TopicDiagnosis",
    "TopicStatus",
    "QoSInfo",
    "SampleResult",
    "inspect",
    "Sampler",
    "diagnose",
    "evaluate",
    "format_text",
    "format_json",
    "print_diagnosis",
]


def __getattr__(name: str):
    """懒加载：仅在首次访问时导入，避免无 ROS2 环境时报错。"""
    if name == "main":
        from .cli import main
        return main
    if name == "TopicDiagnosis":
        from .models import TopicDiagnosis
        return TopicDiagnosis
    if name == "TopicStatus":
        from .models import TopicStatus
        return TopicStatus
    if name == "QoSInfo":
        from .models import QoSInfo
        return QoSInfo
    if name == "SampleResult":
        from .models import SampleResult
        return SampleResult
    if name == "inspect":
        from .inspector import inspect
        return inspect
    if name == "Sampler":
        from .sampler import Sampler
        return Sampler
    if name == "diagnose":
        from .rules import diagnose
        return diagnose
    if name == "evaluate":
        from .rules import evaluate
        return evaluate
    if name == "format_text":
        from .formatter import format_text
        return format_text
    if name == "format_json":
        from .formatter import format_json
        return format_json
    if name == "print_diagnosis":
        from .formatter import print_diagnosis
        return print_diagnosis
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
