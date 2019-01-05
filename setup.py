import pathlib
from setuptools import setup

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()


setup(name='limepy',
    version='0.0.0',
    description='Download and process LimeSurvey data',
    long_description=README,
    long_description_content_type="text/markdown",
    author='dirkmjk',
    author_email='info@dirkmjk.nl',
    license="MIT",
    packages=['limepy'],
    include_package_data=True,
    install_requires=['pandas', 'numpy', 'requests', 'xmltodict'],
    zip_safe=False)
