import pathlib
from setuptools import setup

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()


setup(name='limepy',
    version='0.1.4',
    description='Download, summarise and process LimeSurvey data',
    long_description=README,
    long_description_content_type="text/markdown",
    author='dirkmjk',
    author_email='info@dirkmjk.nl',
    url='https://github.com/DIRKMJK/limepy',
    license="MIT",
    packages=['limepy'],
    install_requires=['pandas', 'numpy', 'requests', 'xmltodict'],
    zip_safe=False)
