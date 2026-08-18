"""ament_python entry point for ROS 2/colcon workspaces."""

from setuptools import find_packages, setup


setup(
    name="roscope",
    version="0.2.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/roscope"]),
        ("share/roscope", ["package.xml"]),
    ],
    install_requires=[],
    entry_points={
        "console_scripts": [
            "roscope = roscope.cli:main",
        ],
    },
)
