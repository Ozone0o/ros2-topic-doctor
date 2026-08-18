"""Run Roscope's diagnostic engine against deterministic observations.

This demo does not need a ROS 2 installation. It is useful for understanding
the finding model and for trying the terminal reporter before connecting to a
robot.

    PYTHONPATH=src python examples/demo.py
"""

from __future__ import annotations

from roscope.core.engine import DiagnosticEngine
from roscope.core.models import EndpointInfo, QoSInfo, TopicDiagnosis
from roscope.reporters.terminal import format_diagnosis_text


def main() -> None:
    publisher = EndpointInfo(
        node_name="camera_driver",
        node_namespace="/robot",
        topic_type="sensor_msgs/msg/Image",
        qos=QoSInfo(reliability="BEST_EFFORT", durability="VOLATILE"),
    )
    observations = [
        TopicDiagnosis(
            topic_name="/camera/image_raw",
            msg_type="sensor_msgs/msg/Image",
            topic_exists=True,
            pub_count=1,
            sub_count=2,
            publishers=[publisher],
            rate=0.0,
            message_count=0,
            sample_duration_sec=3.0,
        ),
        TopicDiagnosis(
            topic_name="/joint_states",
            msg_type="sensor_msgs/msg/JointState",
            topic_exists=True,
            pub_count=1,
            sub_count=1,
            publishers=[
                EndpointInfo(
                    node_name="robot_state_publisher",
                    topic_type="sensor_msgs/msg/JointState",
                )
            ],
            rate=49.5,
            expected_rate=50.0,
            message_count=148,
            sample_duration_sec=3.0,
            last_message_seen=True,
            last_message_age_ms=12.0,
        ),
    ]

    engine = DiagnosticEngine()
    for diagnosis in observations:
        engine.analyze(diagnosis, expected_rate=diagnosis.expected_rate, stale_timeout_ms=5000)
        print(format_diagnosis_text(diagnosis, color=False))
        print()


if __name__ == "__main__":
    main()
