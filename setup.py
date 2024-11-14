import os

import setuptools


def read_file(filename):
    """Read a file into a string"""
    path = os.path.abspath(os.path.dirname(__file__))
    filepath = os.path.join(path, filename)
    with open(filepath) as f:
        return f.read()


if __name__ == "__main__":
    setuptools.setup(
        name="smpp_gateway",
        version="1.4.0",
        license="MIT",
        install_requires=[
            "RapidSMS>=2.0",
            "smpplib>=2.2",
            "psycopg2>=2.8",
            "django>=4.2,<5.2",
        ],
        packages=setuptools.find_packages(where="src"),
        package_dir={"": "src"},
        include_package_data=True,
        exclude_package_data={"": ["*.pyc"]},
        author="Caktus Group",
        author_email="team@caktusgroup.com",
        description="SMPP gateway for RapidSMS projects; based on python-smpplib.",
        long_description=read_file("README.md"),
        url="https://github.com/caktus/rapidsms-smpp-gateway",
        classifiers=[
            "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Framework :: Django",
            "Framework :: Django :: 4.2",
            "Framework :: Django :: 5.0",
            "Framework :: Django :: 5.1",
            "Development Status :: 5 - Production/Stable",
            "Operating System :: OS Independent",
        ],
    )
