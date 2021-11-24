import setuptools

if __name__ == "__main__":
    setuptools.setup(
        name="smpp_gateway",  # without the name the package is installed as UNKNOWN
        packages=["smpp_gateway"],
        package_dir={"": "src"},
    )
