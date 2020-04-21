FROM remotepixel/amazonlinux:gdal2.4-py3.7-cogeo

WORKDIR /tmp

ENV PYTHONUSERBASE=/var/task

COPY setup.py setup.py
COPY awspds_mosaic/ awspds_mosaic/

RUN pip install . --user
RUN rm -rf awspds_mosaic setup.py