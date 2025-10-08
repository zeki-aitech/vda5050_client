#!/usr/bin/env python
"""
Setup script for vda5050-client package.
This file provides backward compatibility for older pip versions.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="vda5050-client",
    version="0.1.0",
    description="Python client library for VDA5050 AGV communication protocol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Nguyen Ha Trung (Zekki)",
    author_email="trungnh.aitech@gmail.com",
    license="MIT",
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "vda5050": ["validation/schemas/*.json"],
    },
    install_requires=[
        "paho-mqtt>=2.0.0,<3.0.0",
        "pydantic>=2.0.0,<3.0.0",
        "jsonschema>=4.0.0,<5.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "ruff>=0.1.0",
        ],
    },
)
