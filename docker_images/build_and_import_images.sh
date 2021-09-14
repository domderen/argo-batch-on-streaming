#!/bin/bash

DIR=$( cd -P -- "$(dirname -- "$(command -v -- "$0")")" && pwd -P )

docker buildx build $DIR/with-argo-events --tag with-argo-events:1 --load
k3d image import with-argo-events:1
docker buildx build $DIR/without-argo-events --tag without-argo-events:1 --load
k3d image import without-argo-events:1