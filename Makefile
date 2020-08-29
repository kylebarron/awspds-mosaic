
SHELL = /bin/bash

all: package deploy

package:
	docker build --tag landsat-mosaic-tiler:latest . --no-cache
	docker run --name landsat-mosaic-tiler --volume $(shell pwd)/:/local -itd landsat-mosaic-tiler:latest bash
	docker exec -it landsat-mosaic-tiler bash '/local/bin/package.sh'
	docker stop landsat-mosaic-tiler
	docker rm landsat-mosaic-tiler

STAGENAME=production
BUCKET=MYBUCKET
MAPBOX_TOKEN=pk.....
deploy:
	cd services/landsat && sls deploy --stage ${STAGENAME} --bucket ${BUCKET} --token ${MAPBOX_TOKEN}
