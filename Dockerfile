FROM lambgeo/lambda:gdal2.4-py3.7-geolayer

WORKDIR /tmp

ENV PYTHONUSERBASE=/var/task

COPY setup.py setup.py
COPY landsat_mosaic_tiler/ landsat_mosaic_tiler/
# Need to copy MANIFEST.in so that it correctly includes package data
COPY MANIFEST.in MANIFEST.in

RUN pip install . --user
RUN rm -rf landsat_mosaic_tiler setup.py