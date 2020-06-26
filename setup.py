"""Setup landsat-mosaic-tiler."""

from setuptools import setup, find_packages


# Runtime requirements.
inst_reqs = [
    "Pillow",
    "cogeo-mosaic>=3.0a3",
    # For custom response headers
    "lambda-proxy @ git+https://github.com/kylebarron/lambda-proxy@dev#egg=lambda-proxy",
    "landsat-cogeo-mosaic==0.1.1",
    "loguru",
    "mercantile",
    "rio-color",
    "rio-tiler>=2.0a6",
    "rio_tiler_mosaic>=0.0.1dev3",
]
extra_reqs = {
    "test": ["pytest", "pytest-cov", "mock"],
    "dev": ["pytest", "pytest-cov", "pre-commit", "mock"],
}

setup(
    name="landsat-mosaic-tiler",
    version="0.1.0",
    description=u"Serverless Landsat Image tiles from mosaics of Cloud Optimized GeoTIFFs.",
    long_description=u"Serverless Landsat Image tiles from mosaics of Cloud Optimized GeoTIFFs.",
    python_requires=">=3",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="COG GIS Landsat",
    author=u"Kyle Barron",
    author_email="kylebarron2@gmail.com",
    url="",
    license="BSD",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points={"console_scripts": ["landsat-mosaic = landsat_mosaic_tiler.scripts.cli:run"]},
)
