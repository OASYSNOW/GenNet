from setuptools import find_packages, setup

setup(
    package_dir={"gennet": "gennet"},
    packages=find_packages(
        where=".",
        include=[
            "*",
        ],
        exclude=["tests", "tests.*"],
    ),
)
