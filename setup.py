from setuptools import setup, find_packages

setup(
    name="kubeflow-mini",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "kopf>=1.35.6",
        "kubernetes>=28.1.0",
        "click>=8.1.3",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "kubeflow-mini=kubeflow_mini.cli:main",
        ],
    },
    python_requires=">=3.8",
) 